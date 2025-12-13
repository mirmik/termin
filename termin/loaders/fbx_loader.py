# termin/loaders/fbx_loader.py
"""FBX loader using ufbx library."""

import numpy as np
import ufbx


class FBXMeshData:
    def __init__(self, name, vertices, normals, uvs, indices, material_index):
        self.name = name
        self.vertices = vertices
        self.normals = normals
        self.uvs = uvs
        self.indices = indices
        self.material_index = material_index


class FBXMaterialData:
    def __init__(self, name, diffuse_color=None, diffuse_texture=None):
        self.name = name
        self.diffuse_color = diffuse_color
        self.diffuse_texture = diffuse_texture


class FBXNodeData:
    def __init__(self, name, children=None, mesh_indices=None, transform=None):
        self.name = name
        self.children = children or []
        self.mesh_indices = mesh_indices or []
        self.transform = transform


class FBXAnimationChannel:
    def __init__(self, node_name, pos_keys, rot_keys, scale_keys):
        self.node_name = node_name
        self.pos_keys = pos_keys
        self.rot_keys = rot_keys
        self.scale_keys = scale_keys


class FBXAnimationClip:
    def __init__(self, name, duration, tps, channels):
        self.name = name
        self.duration = duration
        self.ticks_per_second = tps
        self.channels = channels


class FBXSceneData:
    def __init__(self):
        self.meshes = []
        self.materials = []
        self.root = None
        self.animations = []


# ---------- PARSER HELPERS ----------

def _parse_materials(scene, out):
    for mat in scene.materials:
        name = mat.name if mat.name else "Material"

        diffuse_color = None
        if mat.pbr.base_color.has_value:
            c = mat.pbr.base_color.value_vec4
            diffuse_color = np.array([c.x, c.y, c.z, c.w], dtype=np.float32)

        diffuse_texture = None
        if mat.pbr.base_color.texture:
            tex = mat.pbr.base_color.texture
            if tex.filename:
                diffuse_texture = tex.filename

        out.materials.append(
            FBXMaterialData(
                name=name,
                diffuse_color=diffuse_color,
                diffuse_texture=diffuse_texture
            )
        )


def _parse_meshes(scene, out):
    for mesh in scene.meshes:
        # Get triangulated mesh for easier processing
        try:
            tri_mesh = mesh.as_triangles()
        except Exception:
            tri_mesh = mesh

        num_indices = len(tri_mesh.indices)
        if num_indices == 0:
            continue

        # Build vertex arrays from triangulated indices
        vertices = []
        normals = []
        uvs = []

        has_normals = len(mesh.vertex_normal.values) > 0
        has_uvs = len(mesh.uv_sets) > 0 and len(mesh.uv_sets[0].values) > 0

        for idx in tri_mesh.indices:
            # Position
            v = mesh.vertices[idx]
            vertices.append((v.x, v.y, v.z))

            # Normal
            if has_normals:
                n_idx = mesh.vertex_normal.indices[idx]
                n = mesh.vertex_normal.values[n_idx]
                normals.append((n.x, n.y, n.z))

            # UV
            if has_uvs:
                uv_set = mesh.uv_sets[0]
                uv_idx = uv_set.indices[idx]
                uv = uv_set.values[uv_idx]
                uvs.append((uv.x, uv.y))

        vertices_np = np.array(vertices, dtype=np.float32)
        normals_np = np.array(normals, dtype=np.float32) if normals else None
        uvs_np = np.array(uvs, dtype=np.float32) if uvs else None
        indices_np = np.arange(len(vertices), dtype=np.uint32)

        # Material index
        mat_idx = 0
        if mesh.materials:
            mat_idx = scene.materials.index(mesh.materials[0]) if mesh.materials[0] in scene.materials else 0

        out.meshes.append(
            FBXMeshData(
                name=mesh.name if mesh.name else "Mesh",
                vertices=vertices_np,
                normals=normals_np,
                uvs=uvs_np,
                indices=indices_np,
                material_index=mat_idx
            )
        )


def _parse_node(node, scene, mesh_index_map):
    """Recursively parse node hierarchy."""
    name = node.name if node.name else "Node"

    # Get local transform as 4x4 matrix
    t = node.local_transform
    transform = np.array([
        [t.m00, t.m01, t.m02, t.m03],
        [t.m10, t.m11, t.m12, t.m13],
        [t.m20, t.m21, t.m22, t.m23],
        [0, 0, 0, 1],
    ], dtype=np.float32)

    # Mesh indices
    mesh_indices = []
    if node.mesh:
        idx = mesh_index_map.get(id(node.mesh))
        if idx is not None:
            mesh_indices.append(idx)

    # Recursively parse children
    children = [_parse_node(child, scene, mesh_index_map) for child in node.children]

    return FBXNodeData(name, children, mesh_indices, transform)


def _parse_animations(scene, out):
    for anim_stack in scene.anim_stacks:
        name = anim_stack.name if anim_stack.name else "Anim"

        # Get duration from layers
        duration = 0.0
        tps = 30.0  # Default ticks per second

        if anim_stack.layers:
            layer = anim_stack.layers[0]
            for anim_value in layer.anim_values:
                for curve in [anim_value.curves_x, anim_value.curves_y, anim_value.curves_z]:
                    if curve and curve.keyframes:
                        last_time = curve.keyframes[-1].time
                        if last_time > duration:
                            duration = last_time

        # Parse channels
        channels = []
        if anim_stack.layers:
            layer = anim_stack.layers[0]
            node_channels = {}

            for anim_prop in layer.anim_props:
                node = anim_prop.element
                if not node or not hasattr(node, 'name'):
                    continue

                node_name = node.name
                if node_name not in node_channels:
                    node_channels[node_name] = {
                        'pos_keys': [],
                        'rot_keys': [],
                        'scale_keys': []
                    }

                # Determine property type and extract keys
                prop_name = anim_prop.prop_name if hasattr(anim_prop, 'prop_name') else ""
                anim_value = anim_prop.anim_value

                if anim_value:
                    keys = _extract_keys(anim_value)
                    if 'translation' in prop_name.lower() or 'lcl translation' in prop_name.lower():
                        node_channels[node_name]['pos_keys'] = keys
                    elif 'rotation' in prop_name.lower() or 'lcl rotation' in prop_name.lower():
                        node_channels[node_name]['rot_keys'] = keys
                    elif 'scaling' in prop_name.lower() or 'lcl scaling' in prop_name.lower():
                        node_channels[node_name]['scale_keys'] = keys

            for node_name, ch_data in node_channels.items():
                channels.append(
                    FBXAnimationChannel(
                        node_name=node_name,
                        pos_keys=ch_data['pos_keys'],
                        rot_keys=ch_data['rot_keys'],
                        scale_keys=ch_data['scale_keys']
                    )
                )

        out.animations.append(
            FBXAnimationClip(
                name=name,
                duration=duration,
                tps=tps,
                channels=channels
            )
        )


def _extract_keys(anim_value):
    """Extract keyframes from anim value."""
    keys = []
    curves = [anim_value.curves_x, anim_value.curves_y, anim_value.curves_z]

    # Find all unique times
    times = set()
    for curve in curves:
        if curve:
            for kf in curve.keyframes:
                times.add(kf.time)

    for t in sorted(times):
        values = []
        for curve in curves:
            if curve:
                # Find value at time t (simple linear search)
                val = curve.keyframes[0].value if curve.keyframes else 0.0
                for kf in curve.keyframes:
                    if kf.time <= t:
                        val = kf.value
                values.append(val)
            else:
                values.append(0.0)
        keys.append((t, np.array(values, dtype=np.float32)))

    return keys


# ---------- PUBLIC API ----------

def load_fbx_file(path) -> FBXSceneData:
    """Load FBX file using ufbx."""
    scene_data = FBXSceneData()

    scene = ufbx.load_file(path)
    if not scene:
        raise RuntimeError(f"Failed to load FBX: {path}")

    # Build mesh index map for node parsing
    mesh_index_map = {id(mesh): i for i, mesh in enumerate(scene.meshes)}

    _parse_materials(scene, scene_data)
    _parse_meshes(scene, scene_data)

    if scene.root_node:
        scene_data.root = _parse_node(scene.root_node, scene, mesh_index_map)

    _parse_animations(scene, scene_data)

    return scene_data
