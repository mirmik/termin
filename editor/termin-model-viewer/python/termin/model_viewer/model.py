"""GLB-to-retained-scene composition for the standalone model viewer."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path

import numpy as np


_LOG = logging.getLogger("termin.model_viewer.model")

_DEFAULT_MATERIAL_COLOR = (0.34, 0.72, 0.95, 1.0)
# Fallback for a composed model before a viewer camera is attached.  It
# matches OrbitCamera's default 45-degree azimuth and 30-degree elevation;
# the application derives the actual initial direction from its fitted camera.
_DEFAULT_LIGHT_DIRECTION = (
    0.6123724356957945,
    -0.6123724356957946,
    0.49999999999999994,
)
_DEFAULT_LIGHT_AMBIENT = 0.28
_DEFAULT_LIGHT_DIFFUSE = 0.72


@dataclass(frozen=True)
class ModelBounds:
    minimum: tuple[float, float, float]
    maximum: tuple[float, float, float]

    def as_aabb(self):
        from termin.geombase import AABB, Vec3

        return AABB(Vec3(*self.minimum), Vec3(*self.maximum))


@dataclass(frozen=True)
class ModelGeometryStatistics:
    """Geometry stored by the decoded GLB, before scene instancing."""

    mesh_count: int
    primitive_count: int
    vertex_count: int
    triangle_count: int


class VisualModel:
    """Own a GLB-derived visual scene and the bounds used to frame it."""

    def __init__(
        self,
        scene,
        items: list,
        bounds: ModelBounds,
        statistics: ModelGeometryStatistics,
    ) -> None:
        self.scene = scene
        self.items = items
        self.bounds = bounds
        self.statistics = statistics

    def set_preview_light(self, direction: tuple[float, float, float]) -> None:
        """Apply the viewer's simple key light consistently to every mesh."""
        for item in self.items:
            item.set_flat_lighting(
                direction,
                _DEFAULT_LIGHT_AMBIENT,
                _DEFAULT_LIGHT_DIFFUSE,
            )

    def close(self) -> None:
        if not self.scene.valid:
            return
        from termin.visual_scene import tc_visual_scene3d_destroy

        tc_visual_scene3d_destroy(self.scene)
        self.items.clear()


def _geometry_statistics(scene_data) -> ModelGeometryStatistics:
    vertex_count = 0
    primitive_count = 0
    triangle_count = 0
    for mesh in scene_data.meshes:
        vertex_count += len(mesh.vertices)
        for submesh in mesh.submeshes:
            index_count = int(submesh.index_count)
            if index_count < 0 or index_count % 3 != 0:
                raise ValueError(
                    f"mesh '{mesh.name}' submesh '{submesh.name}' has "
                    f"a non-triangle index count of {index_count}"
                )
            primitive_count += 1
            triangle_count += index_count // 3
    return ModelGeometryStatistics(
        mesh_count=len(scene_data.meshes),
        primitive_count=primitive_count,
        vertex_count=vertex_count,
        triangle_count=triangle_count,
    )


def _node_transform(node):
    from termin.geombase import Affine3d, Quat, Vec3

    return Affine3d.trs(
        Vec3(*(float(value) for value in node.translation)),
        Quat(*(float(value) for value in node.rotation)),
        Vec3(*(float(value) for value in node.scale)),
    )


def _submesh_geometry(mesh, submesh):
    first_index = int(submesh.first_index)
    index_count = int(submesh.index_count)
    last_index = first_index + index_count
    flat_indices = np.asarray(mesh.indices, dtype=np.uint32).reshape(-1)
    if first_index < 0 or index_count <= 0 or index_count % 3 != 0:
        raise ValueError(f"mesh '{mesh.name}' has an invalid triangle range [{first_index}, {last_index})")
    if last_index > flat_indices.size:
        raise ValueError(f"mesh '{mesh.name}' submesh range ends at {last_index}, past {flat_indices.size} indices")

    source_indices = flat_indices[first_index:last_index]
    source_vertices = np.asarray(mesh.vertices, dtype=np.float32)
    if source_indices.size and int(np.max(source_indices)) >= len(source_vertices):
        raise ValueError(f"mesh '{mesh.name}' contains an index outside its {len(source_vertices)} vertices")

    # A GLB with one submesh already has exactly the indexed representation
    # consumed by Mesh3. Keep it intact: np.unique over tens of millions of
    # indices is expensive and only saves unused vertices, which are uncommon.
    if first_index == 0 and index_count == flat_indices.size:
        vertices = np.ascontiguousarray(source_vertices, dtype=np.float32)
        triangles = np.ascontiguousarray(source_indices.reshape((-1, 3)), dtype=np.uint32)
        uvs = (
            np.ascontiguousarray(np.asarray(mesh.uvs, dtype=np.float32), dtype=np.float32)
            if mesh.uvs is not None
            else None
        )
        normals = (
            np.ascontiguousarray(np.asarray(mesh.normals, dtype=np.float32), dtype=np.float32)
            if mesh.normals is not None
            else None
        )
        return vertices, triangles, uvs, normals

    unique_indices, compact_indices = np.unique(source_indices, return_inverse=True)
    vertices = np.ascontiguousarray(
        source_vertices[unique_indices],
        dtype=np.float32,
    )
    triangles = np.ascontiguousarray(
        compact_indices.reshape((-1, 3)),
        dtype=np.uint32,
    )
    uvs = None
    if mesh.uvs is not None:
        uvs = np.ascontiguousarray(
            np.asarray(mesh.uvs, dtype=np.float32)[unique_indices],
            dtype=np.float32,
        )
    normals = None
    if mesh.normals is not None:
        normals = np.ascontiguousarray(
            np.asarray(mesh.normals, dtype=np.float32)[unique_indices],
            dtype=np.float32,
        )
    return vertices, triangles, uvs, normals


def _material_for(scene_data, material_index: int):
    if material_index < 0:
        return None
    if material_index >= len(scene_data.materials):
        raise ValueError(f"GLB references missing material {material_index}")
    return scene_data.materials[material_index]


def _texture_by_index(scene_data) -> dict[int, object]:
    result: dict[int, object] = {}
    for texture in scene_data.textures:
        if texture.index in result:
            raise ValueError(f"GLB contains duplicate texture index {texture.index}")
        result[texture.index] = texture
    return result


def _apply_material(item, mesh, material, textures, decoded_textures) -> None:
    from tcbase._geom_native import LinearColor
    from termin.image import decode_rgba8

    if material is None:
        base_color = _DEFAULT_MATERIAL_COLOR
    elif material.base_color is None:
        base_color = (1.0, 1.0, 1.0, 1.0)
    else:
        color = np.asarray(material.base_color, dtype=np.float64).reshape(-1)
        if color.size != 4 or not np.all(np.isfinite(color)):
            raise ValueError(f"material '{material.name}' has an invalid base color")
        base_color = tuple(float(value) for value in color)
    item.set_base_color_factor(LinearColor(*base_color))

    if material is not None and material.base_color_texture is not None and mesh.uvs is None:
        _LOG.warning(
            "Material '%s' references a base-color texture, but mesh '%s' has no UVs; showing the factor color only",
            material.name,
            mesh.name,
        )
    elif material is not None and material.base_color_texture is not None:
        texture_index = int(material.base_color_texture)
        texture = textures.get(texture_index)
        if texture is None:
            raise ValueError(f"material '{material.name}' references missing texture {texture_index}")
        decoded = decoded_textures.get(texture_index)
        if decoded is None:
            decoded = decode_rgba8(texture.data, texture.name)
            decoded_textures[texture_index] = decoded
        item.set_base_color_texture_rgba8(decoded.width, decoded.height, decoded.data)

    # The standalone viewer presents every material under the same simple key
    # light. This is a viewport policy rather than an attempt at glTF PBR.
    item.set_flat_lighting(
        _DEFAULT_LIGHT_DIRECTION,
        _DEFAULT_LIGHT_AMBIENT,
        _DEFAULT_LIGHT_DIFFUSE,
    )


def _create_mesh_items(
    visual_scene,
    scene_data,
    source_mesh_index: int,
    parent,
    textures,
    decoded_textures,
) -> list:
    from tcbase._geom_native import SrgbColor
    from termin.mesh import Mesh3

    internal_indices = scene_data.mesh_index_map.get(source_mesh_index)
    if not internal_indices:
        raise ValueError(f"GLB node references missing mesh {source_mesh_index}")

    items = []
    for internal_index in internal_indices:
        if internal_index < 0 or internal_index >= len(scene_data.meshes):
            raise ValueError(f"GLB mesh map contains invalid mesh index {internal_index}")
        mesh = scene_data.meshes[internal_index]
        for submesh in mesh.submeshes:
            vertices, triangles, uvs, normals = _submesh_geometry(mesh, submesh)
            authored_mesh = Mesh3(
                vertices=vertices,
                triangles=triangles,
                uvs=uvs,
                vertex_normals=normals,
                name=submesh.name,
            )
            item = visual_scene.create_static_mesh(
                authored_mesh,
                SrgbColor(1.0, 1.0, 1.0, 1.0),
                parent=parent,
            )
            item.hit_test_enabled = False
            material = _material_for(scene_data, int(submesh.material_index))
            _apply_material(item, mesh, material, textures, decoded_textures)
            items.append(item)
    return items


def _scene_roots(scene_data) -> list[int]:
    if scene_data.root_nodes:
        return [int(index) for index in scene_data.root_nodes]
    child_indices = {int(child) for node in scene_data.nodes for child in node.children}
    return [index for index in range(len(scene_data.nodes)) if index not in child_indices]


def _model_bounds(items: list) -> ModelBounds:
    bounds = []
    for item in items:
        item_bounds = item.world_bounds
        if item_bounds is not None:
            bounds.append(tuple(float(value) for value in item_bounds))
    if not bounds:
        raise ValueError("GLB contains no visible triangle meshes")
    values = np.asarray(bounds, dtype=np.float64)
    if values.shape[1] != 6 or not np.all(np.isfinite(values)):
        raise ValueError("GLB produced invalid model bounds")
    minimum = tuple(float(value) for value in np.min(values[:, :3], axis=0))
    maximum = tuple(float(value) for value in np.max(values[:, 3:], axis=0))
    return ModelBounds(minimum, maximum)


def compose_visual_model(scene_data) -> VisualModel:
    """Compose decoded, Z-up GLB data into a retained 3D visual scene."""

    from termin.visual_scene import tc_visual_scene3d_create

    statistics = _geometry_statistics(scene_data)
    visual_scene = tc_visual_scene3d_create()
    items: list = []
    textures = _texture_by_index(scene_data)
    decoded_textures: dict[int, object] = {}
    visited: set[int] = set()
    active: set[int] = set()

    def add_node(node_index: int, parent=None) -> None:
        if node_index < 0 or node_index >= len(scene_data.nodes):
            raise ValueError(f"GLB hierarchy references missing node {node_index}")
        if node_index in active:
            raise ValueError(f"GLB hierarchy contains a cycle at node {node_index}")
        if node_index in visited:
            raise ValueError(f"GLB hierarchy references node {node_index} more than once")
        active.add(node_index)
        visited.add(node_index)
        node = scene_data.nodes[node_index]
        group = visual_scene.create_group(parent=parent)
        group.local_transform = _node_transform(node)
        if node.mesh_index is not None:
            items.extend(
                _create_mesh_items(
                    visual_scene,
                    scene_data,
                    int(node.mesh_index),
                    group,
                    textures,
                    decoded_textures,
                )
            )
        for child_index in node.children:
            add_node(int(child_index), group)
        active.remove(node_index)

    try:
        roots = _scene_roots(scene_data)
        for root_index in roots:
            add_node(root_index)

        if not scene_data.nodes:
            for source_mesh_index in sorted(scene_data.mesh_index_map):
                items.extend(
                    _create_mesh_items(
                        visual_scene,
                        scene_data,
                        int(source_mesh_index),
                        None,
                        textures,
                        decoded_textures,
                    )
                )

        bounds = _model_bounds(items)
        return VisualModel(visual_scene, items, bounds, statistics)
    except Exception:
        _LOG.exception("Failed to compose decoded GLB as a retained visual scene")
        VisualModel(
            visual_scene,
            items,
            ModelBounds((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
            statistics,
        ).close()
        raise


def load_visual_model(path: str | Path) -> VisualModel:
    from termin.glb import load_glb_file_normalized

    model_path = Path(path)
    scene_data = load_glb_file_normalized(model_path, convert_to_z_up=True)
    model = compose_visual_model(scene_data)
    _LOG.info(
        "Loaded model '%s': %d retained mesh item(s), %d material(s), %d texture(s)",
        model_path,
        len(model.items),
        len(scene_data.materials),
        len(scene_data.textures),
    )
    return model
