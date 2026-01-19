"""
NavMeshBuilderComponent — component for building NavMesh from mesh geometry.

Voxelization is an internal step, voxels are not saved to file.
Supports agent type selection for future NavMesh erosion.

Uses SceneCache for persistent storage and NavMeshRegistry for runtime access.
"""

from __future__ import annotations

from enum import IntEnum
from typing import TYPE_CHECKING, Optional, List, Set

import numpy as np

from termin.visualization.core.python_component import PythonComponent
from termin.visualization.core.material import Material
from termin.mesh import TcMesh
from termin.mesh.mesh import Mesh3
from termin.voxels.voxel_mesh import create_voxel_mesh
from termin.visualization.render.drawable import GeometryDrawCall
from termin.editor.inspect_field import InspectField
from termin.navmesh.settings import NavigationSettingsManager

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene
    from termin.visualization.render.render_context import RenderContext
    from termin.voxels.grid import VoxelGrid
    from termin.navmesh.types import NavMesh
    from termin.navmesh.polygon_builder import PolygonBuilder


class VoxelizeSource(IntEnum):
    """Source meshes for voxelization."""
    CURRENT_MESH = 0      # Only current entity mesh
    ALL_DESCENDANTS = 1   # All descendant meshes (including current entity)


def _build_navmesh_action(component: "NavMeshBuilderComponent") -> None:
    """Build NavMesh button action."""
    component.build()


class NavMeshBuilderComponent(PythonComponent):
    """
    Component for building NavMesh from entity mesh.

    Combines voxelization and NavMesh building in one step.
    Voxels are not saved to file - they are intermediate data.
    """

    is_drawable = True

    inspect_fields = {
        "navmesh_name": InspectField(
            path="navmesh_name",
            label="NavMesh Name",
            kind="string",
        ),
        "agent_type_name": InspectField(
            path="agent_type_name",
            label="Agent Type",
            kind="agent_type",
        ),
        "cell_size": InspectField(
            path="cell_size",
            label="Cell Size",
            kind="float",
            min=0.001,
            max=10.0,
            step=0.001,
        ),
        "voxelize_source": InspectField(
            path="voxelize_source",
            label="Source",
            kind="enum",
            choices=[
                (VoxelizeSource.CURRENT_MESH, "Current Mesh"),
                (VoxelizeSource.ALL_DESCENDANTS, "All Descendants"),
            ],
        ),
        # --- NavMesh parameters ---
        "normal_angle": InspectField(
            path="normal_angle",
            label="Region Merge Angle (°)",
            kind="float",
            min=0.0,
            max=90.0,
            step=1.0,
        ),
        "contour_simplify": InspectField(
            path="contour_simplify",
            label="Contour Simplify",
            kind="float",
            min=0.0,
            max=10.0,
            step=0.1,
        ),
        "max_edge_length": InspectField(
            path="max_edge_length",
            label="Max Edge Length",
            kind="float",
            min=0.0,
            max=10.0,
            step=0.1,
        ),
        "min_edge_length": InspectField(
            path="min_edge_length",
            label="Min Edge Length",
            kind="float",
            min=0.0,
            max=5.0,
            step=0.05,
        ),
        "min_contour_edge_length": InspectField(
            path="min_contour_edge_length",
            label="Min Contour Edge",
            kind="float",
            min=0.0,
            max=5.0,
            step=0.05,
        ),
        "max_vertex_valence": InspectField(
            path="max_vertex_valence",
            label="Max Vertex Valence",
            kind="int",
            min=0,
            max=20,
            step=1,
        ),
        "use_delaunay_flip": InspectField(
            path="use_delaunay_flip",
            label="Delaunay Flip",
            kind="bool",
        ),
        "use_valence_flip": InspectField(
            path="use_valence_flip",
            label="Valence Flip",
            kind="bool",
        ),
        "use_angle_flip": InspectField(
            path="use_angle_flip",
            label="Angle Flip",
            kind="bool",
        ),
        "use_cvt_smoothing": InspectField(
            path="use_cvt_smoothing",
            label="CVT Smoothing",
            kind="bool",
        ),
        "use_edge_collapse": InspectField(
            path="use_edge_collapse",
            label="Edge Collapse",
            kind="bool",
        ),
        "use_second_pass": InspectField(
            path="use_second_pass",
            label="Second Pass",
            kind="bool",
        ),
        "use_watershed": InspectField(
            path="use_watershed",
            label="Watershed Split",
            kind="bool",
        ),
        "watershed_smoothing": InspectField(
            path="watershed_smoothing",
            label="Smoothing",
            kind="int",
            min=0,
            max=10,
            step=1,
        ),
        "build_btn": InspectField(
            label="Build NavMesh",
            kind="button",
            action=_build_navmesh_action,
            is_serializable=False,
        ),
        # --- Debug ---
        "show_region_voxels": InspectField(
            path="show_region_voxels",
            label="Show Regions",
            kind="bool",
        ),
        "show_simplified_contours": InspectField(
            path="show_simplified_contours",
            label="Show Simplified Contours",
            kind="bool",
        ),
        "show_triangulated": InspectField(
            path="show_triangulated",
            label="Show Triangulated",
            kind="bool",
        ),
        "show_distance_field": InspectField(
            path="show_distance_field",
            label="Show Distance Field",
            kind="bool",
        ),
        "show_local_maxima": InspectField(
            path="show_local_maxima",
            label="Show Local Maxima",
            kind="bool",
        ),
        "show_peaks": InspectField(
            path="show_peaks",
            label="Show Peaks (after plateau)",
            kind="bool",
        ),
        "show_watershed_regions": InspectField(
            path="show_watershed_regions",
            label="Show Watershed",
            kind="bool",
        ),
        "color_seed": InspectField(
            path="color_seed",
            label="Color Seed",
            kind="int",
            min=0,
            max=1000,
            step=1,
        ),
    }

    serializable_fields = [
        "navmesh_name", "agent_type_name", "cell_size", "voxelize_source",
        "normal_angle", "contour_simplify", "max_edge_length",
        "min_edge_length", "min_contour_edge_length", "max_vertex_valence",
        "use_delaunay_flip", "use_valence_flip", "use_angle_flip", "use_cvt_smoothing",
        "use_edge_collapse", "use_second_pass", "use_watershed", "watershed_smoothing",
        "show_region_voxels", "show_simplified_contours", "show_triangulated",
        "show_distance_field", "show_local_maxima", "show_peaks", "show_watershed_regions",
        "color_seed",
    ]

    def __init__(
        self,
        navmesh_name: str = "",
        agent_type_name: str = "Human",
        cell_size: float = 0.25,
        voxelize_source: VoxelizeSource = VoxelizeSource.CURRENT_MESH,
        normal_angle: float = 25.0,
        contour_simplify: float = 0.0,
        max_edge_length: float = 0.0,
        min_edge_length: float = 0.0,
        min_contour_edge_length: float = 0.0,
        max_vertex_valence: int = 0,
        use_delaunay_flip: bool = True,
        use_valence_flip: bool = False,
        use_angle_flip: bool = False,
        use_cvt_smoothing: bool = False,
        use_edge_collapse: bool = False,
        use_second_pass: bool = False,
        use_watershed: bool = False,
        watershed_smoothing: int = 0,
        show_region_voxels: bool = False,
        show_simplified_contours: bool = False,
        show_triangulated: bool = False,
        show_distance_field: bool = False,
        show_local_maxima: bool = False,
        show_peaks: bool = False,
        show_watershed_regions: bool = False,
        color_seed: int = 42,
    ) -> None:
        super().__init__()
        self.navmesh_name = navmesh_name
        self.agent_type_name = agent_type_name
        self.cell_size = cell_size
        self.voxelize_source = voxelize_source
        self.normal_angle = normal_angle
        self.contour_simplify = contour_simplify
        self.max_edge_length = max_edge_length
        self.min_edge_length = min_edge_length
        self.min_contour_edge_length = min_contour_edge_length
        self.max_vertex_valence = max_vertex_valence
        self.use_delaunay_flip = use_delaunay_flip
        self.use_valence_flip = use_valence_flip
        self.use_angle_flip = use_angle_flip
        self.use_cvt_smoothing = use_cvt_smoothing
        self.use_edge_collapse = use_edge_collapse
        self.use_second_pass = use_second_pass
        self.use_watershed = use_watershed
        self.watershed_smoothing = watershed_smoothing

        # Debug visualization
        self.show_region_voxels: bool = show_region_voxels
        self.show_simplified_contours: bool = show_simplified_contours
        self.show_triangulated: bool = show_triangulated
        self.show_distance_field: bool = show_distance_field
        self.show_local_maxima: bool = show_local_maxima
        self.show_peaks: bool = show_peaks
        self.show_watershed_regions: bool = show_watershed_regions
        self.color_seed: int = color_seed

        # Internal state
        self._debug_regions: list[tuple[list[tuple[int, int, int]], np.ndarray]] = []
        self._debug_watershed_regions: list[tuple[list[tuple[int, int, int]], np.ndarray]] = []
        self._debug_grid: Optional["VoxelGrid"] = None
        self._debug_builder: Optional["PolygonBuilder"] = None
        self._debug_region_voxels_mesh: Optional[TcMesh] = None
        self._debug_simplified_contours_mesh: Optional[TcMesh] = None
        self._debug_triangulated_mesh: Optional[TcMesh] = None
        self._debug_distance_field_mesh: Optional[TcMesh] = None
        self._debug_watershed_mesh: Optional[TcMesh] = None

        # Cached data for distance field visualization (to avoid recomputation)
        self._cached_local_maxima: set[tuple[int, int, int]] = set()
        self._cached_plateau_peaks: set[tuple[int, int, int]] = set()
        self._cached_eroded_voxels: set[tuple[int, int, int]] = set()
        self._cached_distance_fields: list[dict[tuple[int, int, int], float]] = []
        self._cached_show_local_maxima: bool = False
        self._cached_show_peaks: bool = False

        # GPU caches
        from termin._native.render import MeshGPU
        self._debug_region_voxels_gpu: Optional[MeshGPU] = None
        self._debug_simplified_contours_gpu: Optional[MeshGPU] = None
        self._debug_triangulated_gpu: Optional[MeshGPU] = None
        self._debug_distance_field_gpu: Optional[MeshGPU] = None
        self._debug_watershed_gpu: Optional[MeshGPU] = None
        self._debug_material: Optional[Material] = None
        self._debug_line_material: Optional[Material] = None
        self._debug_bounds_min: np.ndarray = np.zeros(3, dtype=np.float32)
        self._debug_bounds_max: np.ndarray = np.zeros(3, dtype=np.float32)

        # Cached NavMesh (loaded from cache or built)
        self._navmesh: Optional["NavMesh"] = None

    # --- Lifecycle ---

    def on_added(self, scene: "Scene") -> None:
        """Called when added to scene. Load from cache if available."""
        super().on_added(scene)
        self._try_load_from_cache()

    def on_removed(self) -> None:
        """Called when removed from scene. Unregister from NavMeshRegistry."""
        if self._scene is not None and self.entity is not None:
            from termin.navmesh.registry import NavMeshRegistry
            registry = NavMeshRegistry.for_scene(self._scene)
            registry.unregister_all(self.entity.uuid)
        super().on_removed()

    def _try_load_from_cache(self) -> bool:
        """
        Try to load NavMesh from cache.

        Returns:
            True if loaded successfully, False otherwise.
        """
        if self._scene is None or self.entity is None:
            return False

        # Scene must have name or uuid for cache
        if not self._scene.name and not self._scene.uuid:
            return False

        from termin.cache import SceneCache
        from termin.navmesh.persistence import NavMeshPersistence
        from termin.navmesh.registry import NavMeshRegistry

        cache = SceneCache.for_scene(self._scene)
        cache_key = f"navmesh_{self.agent_type_name}"

        data = cache.get(self.entity.uuid, type(self).__name__, cache_key)
        if data is None:
            return False

        try:
            navmesh = NavMeshPersistence.from_bytes(data)
            self._navmesh = navmesh

            # Register in NavMeshRegistry
            registry = NavMeshRegistry.for_scene(self._scene)
            registry.register(self.agent_type_name, navmesh, self.entity)

            print(f"NavMeshBuilderComponent: loaded from cache ({navmesh.polygon_count()} polygons)")
            return True
        except Exception as e:
            print(f"NavMeshBuilderComponent: failed to load from cache: {e}")
            return False

    def _save_to_cache(self, navmesh: "NavMesh") -> bool:
        """
        Save NavMesh to cache.

        Returns:
            True if saved successfully, False otherwise.
        """
        if self._scene is None or self.entity is None:
            return False

        # Scene must have name or uuid for cache
        if not self._scene.name and not self._scene.uuid:
            print("NavMeshBuilderComponent: cannot save to cache - scene has no name or uuid")
            return False

        from termin.cache import SceneCache
        from termin.navmesh.persistence import NavMeshPersistence

        cache = SceneCache.for_scene(self._scene)
        cache_key = f"navmesh_{self.agent_type_name}"

        try:
            data = NavMeshPersistence.to_bytes(navmesh)
            cache.put(self.entity.uuid, type(self).__name__, cache_key, data)
            print(f"NavMeshBuilderComponent: saved to cache ({len(data)} bytes)")
            return True
        except Exception as e:
            print(f"NavMeshBuilderComponent: failed to save to cache: {e}")
            return False

    # --- Drawable protocol ---

    GEOMETRY_REGIONS = 1
    GEOMETRY_SIMPLIFIED_CONTOURS = 2
    GEOMETRY_TRIANGULATED = 3
    GEOMETRY_DISTANCE_FIELD = 4
    GEOMETRY_WATERSHED = 5

    @property
    def phase_marks(self) -> Set[str]:
        """Render phases for debug visualization."""
        marks: Set[str] = set()
        if self.show_region_voxels:
            mat = self._get_or_create_debug_material()
            marks.update(p.phase_mark for p in mat.phases)
        if self.show_simplified_contours:
            mat = self._get_or_create_line_material()
            marks.update(p.phase_mark for p in mat.phases)
        if self.show_triangulated:
            mat = self._get_or_create_line_material()
            marks.update(p.phase_mark for p in mat.phases)
        if self.show_distance_field:
            mat = self._get_or_create_debug_material()
            marks.update(p.phase_mark for p in mat.phases)
        if self.show_watershed_regions:
            mat = self._get_or_create_debug_material()
            marks.update(p.phase_mark for p in mat.phases)
        return marks

    def draw_geometry(self, context: "RenderContext", geometry_id: int = 0) -> None:
        """Draw debug geometry."""
        if geometry_id == 0 or geometry_id == self.GEOMETRY_REGIONS:
            if self.show_region_voxels and self._debug_region_voxels_mesh is not None and self._debug_region_voxels_mesh.is_valid:
                if self._debug_region_voxels_gpu is None:
                    from termin._native.render import MeshGPU
                    self._debug_region_voxels_gpu = MeshGPU()
                self._debug_region_voxels_gpu.draw(context, self._debug_region_voxels_mesh.mesh, self._debug_region_voxels_mesh.version)

        if geometry_id == 0 or geometry_id == self.GEOMETRY_SIMPLIFIED_CONTOURS:
            if self.show_simplified_contours and self._debug_simplified_contours_mesh is not None and self._debug_simplified_contours_mesh.is_valid:
                if self._debug_simplified_contours_gpu is None:
                    from termin._native.render import MeshGPU
                    self._debug_simplified_contours_gpu = MeshGPU()
                self._debug_simplified_contours_gpu.draw(context, self._debug_simplified_contours_mesh.mesh, self._debug_simplified_contours_mesh.version)

        if geometry_id == 0 or geometry_id == self.GEOMETRY_TRIANGULATED:
            if self.show_triangulated and self._debug_triangulated_mesh is not None and self._debug_triangulated_mesh.is_valid:
                if self._debug_triangulated_gpu is None:
                    from termin._native.render import MeshGPU
                    self._debug_triangulated_gpu = MeshGPU()
                self._debug_triangulated_gpu.draw(context, self._debug_triangulated_mesh.mesh, self._debug_triangulated_mesh.version)

        if geometry_id == 0 or geometry_id == self.GEOMETRY_DISTANCE_FIELD:
            if self.show_distance_field and self._debug_distance_field_mesh is not None and self._debug_distance_field_mesh.is_valid:
                if self._debug_distance_field_gpu is None:
                    from termin._native.render import MeshGPU
                    self._debug_distance_field_gpu = MeshGPU()
                self._debug_distance_field_gpu.draw(context, self._debug_distance_field_mesh.mesh, self._debug_distance_field_mesh.version)

        if geometry_id == 0 or geometry_id == self.GEOMETRY_WATERSHED:
            if self.show_watershed_regions and self._debug_watershed_mesh is not None and self._debug_watershed_mesh.is_valid:
                if self._debug_watershed_gpu is None:
                    from termin._native.render import MeshGPU
                    self._debug_watershed_gpu = MeshGPU()
                self._debug_watershed_gpu.draw(context, self._debug_watershed_mesh.mesh, self._debug_watershed_mesh.version)

    def get_geometry_draws(self, phase_mark: str | None = None) -> List[GeometryDrawCall]:
        """Return GeometryDrawCalls for debug rendering."""
        result: List[GeometryDrawCall] = []

        # Region voxels
        if self.show_region_voxels and self._debug_region_voxels_mesh is not None and self._debug_region_voxels_mesh.is_valid:
            mat = self._get_or_create_debug_material()
            if phase_mark is None:
                phases = list(mat.phases)
            else:
                phases = [p for p in mat.phases if p.phase_mark == phase_mark]

            white_color = np.array([1.0, 1.0, 1.0, 1.0], dtype=np.float32)
            for phase in phases:
                phase.set_param("u_color_below", white_color)
                phase.set_param("u_color_above", white_color)
                phase.set_param("u_color_surface", white_color)
                phase.set_param("u_slice_axis", np.array([0.0, 0.0, 1.0], dtype=np.float32))
                phase.set_param("u_fill_percent", 1.0)
                phase.set_param("u_bounds_min", self._debug_bounds_min)
                phase.set_param("u_bounds_max", self._debug_bounds_max)
                phase.set_param("u_ambient_color", np.array([1.0, 1.0, 1.0], dtype=np.float32))
                phase.set_param("u_ambient_intensity", 0.5)

            phases.sort(key=lambda p: p.priority)
            result.extend(GeometryDrawCall(phase=p, geometry_id=self.GEOMETRY_REGIONS) for p in phases)

        # Simplified contours
        if self.show_simplified_contours and self._debug_simplified_contours_mesh is not None and self._debug_simplified_contours_mesh.is_valid:
            mat = self._get_or_create_line_material()
            if phase_mark is None:
                phases = list(mat.phases)
            else:
                phases = [p for p in mat.phases if p.phase_mark == phase_mark]

            phases.sort(key=lambda p: p.priority)
            result.extend(GeometryDrawCall(phase=p, geometry_id=self.GEOMETRY_SIMPLIFIED_CONTOURS) for p in phases)

        # Triangulated mesh
        if self.show_triangulated and self._debug_triangulated_mesh is not None and self._debug_triangulated_mesh.is_valid:
            mat = self._get_or_create_line_material()
            if phase_mark is None:
                phases = list(mat.phases)
            else:
                phases = [p for p in mat.phases if p.phase_mark == phase_mark]

            phases.sort(key=lambda p: p.priority)
            result.extend(GeometryDrawCall(phase=p, geometry_id=self.GEOMETRY_TRIANGULATED) for p in phases)

        # Distance field
        if self.show_distance_field:
            # Check if checkbox state changed - rebuild mesh from cached data
            if (self.show_local_maxima != self._cached_show_local_maxima or
                self.show_peaks != self._cached_show_peaks):
                self._rebuild_distance_field_from_cache()

        if self.show_distance_field and self._debug_distance_field_mesh is not None and self._debug_distance_field_mesh.is_valid:
            mat = self._get_or_create_debug_material()
            if phase_mark is None:
                phases = list(mat.phases)
            else:
                phases = [p for p in mat.phases if p.phase_mark == phase_mark]

            white_color = np.array([1.0, 1.0, 1.0, 1.0], dtype=np.float32)
            for phase in phases:
                phase.set_param("u_color_below", white_color)
                phase.set_param("u_color_above", white_color)
                phase.set_param("u_color_surface", white_color)
                phase.set_param("u_slice_axis", np.array([0.0, 0.0, 1.0], dtype=np.float32))
                phase.set_param("u_fill_percent", 1.0)
                phase.set_param("u_bounds_min", self._debug_bounds_min)
                phase.set_param("u_bounds_max", self._debug_bounds_max)
                phase.set_param("u_ambient_color", np.array([1.0, 1.0, 1.0], dtype=np.float32))
                phase.set_param("u_ambient_intensity", 0.5)

            phases.sort(key=lambda p: p.priority)
            result.extend(GeometryDrawCall(phase=p, geometry_id=self.GEOMETRY_DISTANCE_FIELD) for p in phases)

        # Watershed regions
        if self.show_watershed_regions and self._debug_watershed_mesh is not None and self._debug_watershed_mesh.is_valid:
            mat = self._get_or_create_debug_material()
            if phase_mark is None:
                phases = list(mat.phases)
            else:
                phases = [p for p in mat.phases if p.phase_mark == phase_mark]

            white_color = np.array([1.0, 1.0, 1.0, 1.0], dtype=np.float32)
            for phase in phases:
                phase.set_param("u_color_below", white_color)
                phase.set_param("u_color_above", white_color)
                phase.set_param("u_color_surface", white_color)
                phase.set_param("u_slice_axis", np.array([0.0, 0.0, 1.0], dtype=np.float32))
                phase.set_param("u_fill_percent", 1.0)
                phase.set_param("u_bounds_min", self._debug_bounds_min)
                phase.set_param("u_bounds_max", self._debug_bounds_max)
                phase.set_param("u_ambient_color", np.array([1.0, 1.0, 1.0], dtype=np.float32))
                phase.set_param("u_ambient_intensity", 0.5)

            phases.sort(key=lambda p: p.priority)
            result.extend(GeometryDrawCall(phase=p, geometry_id=self.GEOMETRY_WATERSHED) for p in phases)

        return result

    def _get_or_create_debug_material(self) -> Material:
        """Create material for debug visualization."""
        if self._debug_material is None:
            from termin.voxels.voxel_shader import voxel_display_shader
            from termin.visualization.render.renderpass import RenderState

            shader = voxel_display_shader()
            self._debug_material = Material(
                shader=shader,
                color=(1.0, 0.5, 0.0, 0.8),
                phase_mark="opaque",
                render_state=RenderState(
                    depth_test=True,
                    depth_write=True,
                    blend=True,
                    cull=True,
                ),
            )
        return self._debug_material

    def _get_or_create_line_material(self) -> Material:
        """Create material for contour lines."""
        if self._debug_line_material is None:
            from termin.visualization.render.renderpass import RenderState
            from termin._native.render import TcShader

            vertex_source = """
#version 330 core

layout(location = 0) in vec3 a_position;
layout(location = 5) in vec3 a_color;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

out vec3 v_color;

void main() {
    v_color = a_color;
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
}
"""
            fragment_source = """
#version 330 core

in vec3 v_color;

out vec4 FragColor;

void main() {
    FragColor = vec4(v_color, 1.0);
}
"""
            shader = TcShader.from_sources(
                vertex_source,
                fragment_source,
                "",
                "NavMeshBuilderLine",
            )

            self._debug_line_material = Material(
                shader=shader,
                color=(1.0, 1.0, 0.0, 1.0),
                phase_mark="opaque",
                render_state=RenderState(
                    depth_test=True,
                    depth_write=True,
                    blend=False,
                    cull=False,
                ),
            )
        return self._debug_line_material

    # --- Mesh collection ---

    def _collect_meshes_from_entity(
        self,
        entity,
        root_transform_inv: np.ndarray,
        recurse: bool = True,
    ) -> List[tuple["TcMesh", np.ndarray]]:
        """
        Collect meshes from entity (and optionally descendants).

        Args:
            entity: Entity to traverse
            root_transform_inv: Inverse transform of root entity
            recurse: If True — recursively traverse children

        Returns:
            List of (mesh, transform_matrix) for each found mesh
        """
        from termin.visualization.render.components import MeshRenderer

        result: List[tuple[TcMesh, np.ndarray]] = []

        for comp in entity.components:
            if isinstance(comp, MeshRenderer):
                mesh = comp.mesh
                if mesh is not None and mesh.is_valid:
                    world_matrix = entity.model_matrix()
                    local_matrix = root_transform_inv @ world_matrix
                    result.append((mesh, local_matrix))
                break

        if recurse:
            for child in entity.transform.children:
                if child.entity is not None:
                    result.extend(self._collect_meshes_from_entity(child.entity, root_transform_inv, recurse=True))

        return result

    def _create_combined_mesh(
        self,
        meshes: List[tuple["TcMesh", np.ndarray]],
    ) -> Optional["Mesh3"]:
        """
        Combine multiple meshes into one with applied transforms.

        Args:
            meshes: List of (mesh, transform_matrix)

        Returns:
            Combined mesh or None if no data
        """
        if not meshes:
            return None

        all_vertices = []
        all_indices = []
        all_normals = []
        vertex_offset = 0

        for mesh, transform in meshes:
            vertices = mesh.vertices
            triangles = mesh.triangles
            normals = mesh.vertex_normals

            if vertices is None or len(vertices) == 0:
                continue

            ones = np.ones((len(vertices), 1), dtype=np.float32)
            vertices_h = np.hstack([vertices, ones])
            transformed = (transform @ vertices_h.T).T[:, :3]
            all_vertices.append(transformed.astype(np.float32))

            if normals is not None and len(normals) > 0:
                rotation = transform[:3, :3]
                transformed_normals = (rotation @ normals.T).T
                norms = np.linalg.norm(transformed_normals, axis=1, keepdims=True)
                norms[norms == 0] = 1
                transformed_normals = transformed_normals / norms
                all_normals.append(transformed_normals.astype(np.float32))

            if triangles is not None and len(triangles) > 0:
                all_indices.append(triangles + vertex_offset)
                vertex_offset += len(vertices)

        if not all_vertices:
            return None

        combined_vertices = np.vstack(all_vertices)
        combined_triangles = np.vstack(all_indices) if all_indices else None
        combined_normals = np.vstack(all_normals) if all_normals else None

        return Mesh3(
            vertices=combined_vertices,
            triangles=combined_triangles.astype(np.uint32) if combined_triangles is not None else None,
            vertex_normals=combined_normals,
        )

    # --- Build ---

    def build(self) -> bool:
        """
        Build NavMesh from entity mesh.

        Performs voxelization and NavMesh building in one step.
        Voxels are not saved to file.

        Returns:
            True if successful, False on error.
        """
        from termin.voxels.grid import VoxelGrid
        from termin.voxels.native_voxelizer import voxelize_mesh_native
        from termin.navmesh import PolygonBuilder, NavMeshConfig
        import math

        print("NavMeshBuilderComponent: starting build")

        if self.entity is None:
            print("NavMeshBuilderComponent: no entity")
            return False

        # Get agent type info
        manager = NavigationSettingsManager.instance()
        agent_type = manager.settings.get_agent_type(self.agent_type_name)
        if agent_type is not None:
            print(f"NavMeshBuilderComponent: using agent type '{agent_type.name}' "
                  f"(radius={agent_type.radius}, height={agent_type.height}, max_slope={agent_type.max_slope}°)")
            max_slope_cos = math.cos(math.radians(agent_type.max_slope))
            agent_radius = agent_type.radius
        else:
            print(f"NavMeshBuilderComponent: agent type '{self.agent_type_name}' not found, using defaults")
            max_slope_cos = 0.0  # Без фильтрации по наклону
            agent_radius = 0.0  # Без эрозии

        # Collect meshes
        root_world = self.entity.model_matrix()
        root_inv = np.linalg.inv(root_world)

        recurse = (self.voxelize_source == VoxelizeSource.ALL_DESCENDANTS)
        meshes = self._collect_meshes_from_entity(self.entity, root_inv, recurse=recurse)

        if not meshes:
            print("NavMeshBuilderComponent: no meshes found")
            return False

        if len(meshes) > 1:
            print(f"NavMeshBuilderComponent: found {len(meshes)} meshes")

        mesh = self._create_combined_mesh(meshes)
        if mesh is None:
            print("NavMeshBuilderComponent: failed to create combined mesh")
            return False

        # Voxelize (with normals for NavMesh)
        print("NavMeshBuilderComponent: voxelizing...")
        grid = voxelize_mesh_native(
            mesh,
            cell_size=self.cell_size,
            fill_interior=True,
            mark_surface=True,
            clear_interior=True,
            compute_normals=True,
        )

        name = self.navmesh_name.strip()
        if not name:
            name = self.entity.name or "navmesh"

        grid.name = name
        self._debug_grid = grid

        print(f"NavMeshBuilderComponent: voxelized {grid.voxel_count} voxels")

        if not grid.surface_normals:
            print("NavMeshBuilderComponent: voxel grid has no surface normals")
            return False

        # Build NavMesh
        print("NavMeshBuilderComponent: building NavMesh...")
        normal_threshold = math.cos(math.radians(self.normal_angle))
        contour_epsilon = self.contour_simplify * grid.cell_size

        config = NavMeshConfig(
            max_slope_cos=max_slope_cos,
            agent_radius=agent_radius,
            normal_threshold=normal_threshold,
            contour_epsilon=contour_epsilon,
            max_edge_length=self.max_edge_length,
            min_edge_length=self.min_edge_length,
            min_contour_edge_length=self.min_contour_edge_length,
            max_vertex_valence=self.max_vertex_valence,
            use_delaunay_flip=self.use_delaunay_flip,
            use_valence_flip=self.use_valence_flip,
            use_angle_flip=self.use_angle_flip,
            use_cvt_smoothing=self.use_cvt_smoothing,
            use_edge_collapse=self.use_edge_collapse,
            use_second_pass=self.use_second_pass,
            use_watershed=self.use_watershed,
            watershed_smoothing=self.watershed_smoothing,
        )
        builder = PolygonBuilder(config)

        navmesh = builder.build(
            grid,
            do_expand_regions=False,
            share_boundary=False,
            project_contours=False,
            stitch_contours=False,
        )

        # Save debug data
        self._debug_regions = builder._last_regions
        self._debug_watershed_regions = builder._last_watershed_regions
        self._debug_builder = builder
        if self._debug_watershed_regions:
            print(f"NavMeshBuilderComponent: saved {len(self._debug_regions)} regions, {len(self._debug_watershed_regions)} watershed regions")
        else:
            print(f"NavMeshBuilderComponent: saved {len(self._debug_regions)} regions (watershed disabled)")

        # Rebuild debug meshes
        self._rebuild_debug_meshes()
        self._build_debug_mesh_from_navmesh(navmesh)

        print(f"NavMeshBuilderComponent: built NavMesh with {navmesh.polygon_count()} polygons, {navmesh.triangle_count()} triangles")

        # Set navmesh name
        navmesh.name = name
        self._navmesh = navmesh

        # Save to cache
        self._save_to_cache(navmesh)

        # Register in NavMeshRegistry
        if self._scene is not None:
            from termin.navmesh.registry import NavMeshRegistry
            registry = NavMeshRegistry.for_scene(self._scene)
            registry.register(self.agent_type_name, navmesh, self.entity)
            print(f"NavMeshBuilderComponent: registered in NavMeshRegistry for agent type '{self.agent_type_name}'")

        return True

    # --- Debug mesh building ---

    def _rebuild_debug_meshes(self) -> None:
        """Rebuild debug meshes for regions."""
        from termin.voxels.display_component import (
            _CUBE_VERTICES, _CUBE_TRIANGLES, _CUBE_NORMALS,
            VERTS_PER_CUBE, TRIS_PER_CUBE, CUBE_SCALE,
        )
        import random
        import colorsys

        self._debug_region_voxels_mesh = None
        self._debug_region_voxels_gpu = None
        self._debug_simplified_contours_mesh = None
        self._debug_simplified_contours_gpu = None
        self._debug_distance_field_mesh = None
        self._debug_distance_field_gpu = None
        self._debug_watershed_mesh = None
        self._debug_watershed_gpu = None

        if not self._debug_regions or self._debug_grid is None:
            return

        grid = self._debug_grid
        cell_size = grid.cell_size
        cube_size = cell_size * CUBE_SCALE

        # Generate region colors
        random.seed(self.color_seed)
        region_colors = []
        for _ in self._debug_regions:
            h = random.random()
            s = random.random() * 0.3 + 0.7
            v = random.random() * 0.2 + 0.8
            r, g, b = colorsys.hsv_to_rgb(h, s, v)
            region_colors.append((r, g, b))

        # Build region voxels mesh
        self._build_debug_region_voxels(grid, cube_size, _CUBE_VERTICES, _CUBE_TRIANGLES, _CUBE_NORMALS, VERTS_PER_CUBE, TRIS_PER_CUBE, region_colors)

        # Build simplified contours
        self._build_debug_simplified_contours(grid, region_colors)

        # Build distance field mesh
        self._build_debug_distance_field(grid, cube_size, _CUBE_VERTICES, _CUBE_TRIANGLES, _CUBE_NORMALS, VERTS_PER_CUBE, TRIS_PER_CUBE)

        # Build watershed regions mesh
        if self._debug_watershed_regions:
            random.seed(self.color_seed + 81)  # Different seed for watershed colors
            watershed_colors = []
            for _ in self._debug_watershed_regions:
                h = random.random()
                s = random.random() * 0.3 + 0.7
                v = random.random() * 0.2 + 0.8
                r, g, b = colorsys.hsv_to_rgb(h, s, v)
                watershed_colors.append((r, g, b))
            self._build_debug_watershed_voxels(grid, cube_size, _CUBE_VERTICES, _CUBE_TRIANGLES, _CUBE_NORMALS, VERTS_PER_CUBE, TRIS_PER_CUBE, watershed_colors)
        else:
            print("NavMeshBuilderComponent: no watershed regions (enable Watershed Split and rebuild)")

        total_voxels = sum(len(voxels) for voxels, _ in self._debug_regions)
        print(f"NavMeshBuilderComponent: debug mesh built for {len(self._debug_regions)} regions ({total_voxels} voxels)")

    def _build_debug_region_voxels(
        self,
        grid: "VoxelGrid",
        cube_size: float,
        cube_vertices: np.ndarray,
        cube_triangles: np.ndarray,
        cube_normals: np.ndarray,
        verts_per_cube: int,
        tris_per_cube: int,
        region_colors: list[tuple[float, float, float]],
    ) -> None:
        """Build mesh for region voxels with different colors."""
        if not self._debug_regions:
            return

        total_voxels = sum(len(voxels) for voxels, _ in self._debug_regions)
        if total_voxels == 0:
            return

        # Compute bounds
        min_world = np.array([float('inf'), float('inf'), float('inf')], dtype=np.float32)
        max_world = np.array([float('-inf'), float('-inf'), float('-inf')], dtype=np.float32)

        for region_voxels, _ in self._debug_regions:
            for vx, vy, vz in region_voxels:
                center = grid.voxel_to_world(vx, vy, vz)
                min_world = np.minimum(min_world, center)
                max_world = np.maximum(max_world, center)

        half_cube = cube_size * 0.5
        self._debug_bounds_min = min_world - half_cube
        self._debug_bounds_max = max_world + half_cube

        vertices = np.zeros((total_voxels * verts_per_cube, 3), dtype=np.float32)
        triangles = np.zeros((total_voxels * tris_per_cube, 3), dtype=np.int32)
        normals = np.zeros((total_voxels * verts_per_cube, 3), dtype=np.float32)
        uvs = np.zeros((total_voxels * verts_per_cube, 2), dtype=np.float32)
        colors = np.zeros((total_voxels * verts_per_cube, 3), dtype=np.float32)

        voxel_idx = 0
        for region_idx, (region_voxels, region_normal) in enumerate(self._debug_regions):
            region_color = region_colors[region_idx]

            for vx, vy, vz in region_voxels:
                center = grid.voxel_to_world(vx, vy, vz)

                v_offset = voxel_idx * verts_per_cube
                t_offset = voxel_idx * tris_per_cube

                vertices[v_offset:v_offset + verts_per_cube] = cube_vertices * cube_size + center
                triangles[t_offset:t_offset + tris_per_cube] = cube_triangles + v_offset
                normals[v_offset:v_offset + verts_per_cube] = cube_normals
                uvs[v_offset:v_offset + verts_per_cube, 0] = 2.0  # vertex color mode
                colors[v_offset:v_offset + verts_per_cube] = region_color

                voxel_idx += 1

        self._debug_region_voxels_mesh = create_voxel_mesh(
            vertices=vertices,
            triangles=triangles,
            uvs=uvs,
            vertex_colors=colors,
            vertex_normals=normals,
            name="navmesh_builder_debug_regions",
        )

    def _build_debug_watershed_voxels(
        self,
        grid: "VoxelGrid",
        cube_size: float,
        cube_vertices: np.ndarray,
        cube_triangles: np.ndarray,
        cube_normals: np.ndarray,
        verts_per_cube: int,
        tris_per_cube: int,
        region_colors: list[tuple[float, float, float]],
    ) -> None:
        """Build mesh for watershed region voxels with different colors."""
        if not self._debug_watershed_regions:
            return

        total_voxels = sum(len(voxels) for voxels, _ in self._debug_watershed_regions)
        if total_voxels == 0:
            return

        vertices = np.zeros((total_voxels * verts_per_cube, 3), dtype=np.float32)
        triangles = np.zeros((total_voxels * tris_per_cube, 3), dtype=np.int32)
        normals = np.zeros((total_voxels * verts_per_cube, 3), dtype=np.float32)
        uvs = np.zeros((total_voxels * verts_per_cube, 2), dtype=np.float32)
        colors = np.zeros((total_voxels * verts_per_cube, 3), dtype=np.float32)

        voxel_idx = 0
        for region_idx, (region_voxels, region_normal) in enumerate(self._debug_watershed_regions):
            region_color = region_colors[region_idx]

            for vx, vy, vz in region_voxels:
                center = grid.voxel_to_world(vx, vy, vz)

                v_offset = voxel_idx * verts_per_cube
                t_offset = voxel_idx * tris_per_cube

                vertices[v_offset:v_offset + verts_per_cube] = cube_vertices * cube_size + center
                triangles[t_offset:t_offset + tris_per_cube] = cube_triangles + v_offset
                normals[v_offset:v_offset + verts_per_cube] = cube_normals
                uvs[v_offset:v_offset + verts_per_cube, 0] = 2.0  # vertex color mode
                colors[v_offset:v_offset + verts_per_cube] = region_color

                voxel_idx += 1

        self._debug_watershed_mesh = create_voxel_mesh(
            vertices=vertices,
            triangles=triangles,
            uvs=uvs,
            vertex_colors=colors,
            vertex_normals=normals,
            name="navmesh_builder_debug_watershed",
        )

        print(f"NavMeshBuilderComponent: watershed mesh built ({len(self._debug_watershed_regions)} regions, {total_voxels} voxels)")

    def _build_debug_simplified_contours(
        self,
        grid: "VoxelGrid",
        region_colors: list[tuple[float, float, float]],
    ) -> None:
        """Build contour lines after Douglas-Peucker."""
        from termin.navmesh.polygon_builder import PolygonBuilder
        from termin.navmesh.display_component import _build_line_ribbon

        if not self._debug_regions:
            return

        builder = PolygonBuilder()
        line_width = grid.cell_size * 0.1
        simplify_epsilon = self.contour_simplify * grid.cell_size

        all_vertices: list[np.ndarray] = []
        all_triangles: list[np.ndarray] = []
        all_colors: list[np.ndarray] = []
        vertex_offset = 0

        normal_offset = 0.15

        for region_idx, (region_voxels, region_normal) in enumerate(self._debug_regions):
            region_color = region_colors[region_idx]
            up_hint = np.array(region_normal, dtype=np.float32)
            offset_vec = up_hint * normal_offset

            outer_3d, holes_3d = builder.get_region_contours(
                region_voxels,
                region_normal,
                grid.cell_size,
                np.array(grid.origin, dtype=np.float32),
                simplify_epsilon=simplify_epsilon,
                stage="simplified",
            )

            if len(outer_3d) >= 3:
                points = [tuple(v) for v in outer_3d]
                points.append(points[0])

                ribbon_verts, ribbon_tris = _build_line_ribbon(points, line_width, up_hint)

                if len(ribbon_tris) > 0:
                    ribbon_verts = ribbon_verts + offset_vec
                    all_vertices.append(ribbon_verts)
                    all_triangles.append(ribbon_tris + vertex_offset)
                    contour_colors = np.full((len(ribbon_verts), 3), region_color, dtype=np.float32)
                    all_colors.append(contour_colors)
                    vertex_offset += len(ribbon_verts)

            for hole_3d in holes_3d:
                if len(hole_3d) < 3:
                    continue

                hole_points = [tuple(v) for v in hole_3d]
                hole_points.append(hole_points[0])

                hole_ribbon_verts, hole_ribbon_tris = _build_line_ribbon(hole_points, line_width, up_hint)

                if len(hole_ribbon_tris) > 0:
                    hole_ribbon_verts = hole_ribbon_verts + offset_vec
                    all_vertices.append(hole_ribbon_verts)
                    all_triangles.append(hole_ribbon_tris + vertex_offset)
                    hole_colors = np.full((len(hole_ribbon_verts), 3), [c * 0.6 for c in region_color], dtype=np.float32)
                    all_colors.append(hole_colors)
                    vertex_offset += len(hole_ribbon_verts)

        if not all_vertices:
            self._debug_simplified_contours_mesh = None
            return

        vertices = np.vstack(all_vertices).astype(np.float32)
        triangles = np.vstack(all_triangles).astype(np.int32)
        colors = np.vstack(all_colors).astype(np.float32)

        self._debug_simplified_contours_mesh = create_voxel_mesh(
            vertices=vertices,
            triangles=triangles,
            uvs=np.zeros((len(vertices), 2), dtype=np.float32),
            vertex_colors=colors,
            vertex_normals=np.zeros_like(vertices),
            name="navmesh_builder_debug_simplified_contours",
        )

    def _build_debug_distance_field(
        self,
        grid: "VoxelGrid",
        cube_size: float,
        cube_vertices: np.ndarray,
        cube_triangles: np.ndarray,
        cube_normals: np.ndarray,
        verts_per_cube: int,
        tris_per_cube: int,
    ) -> None:
        """Build mesh for distance field visualization with color gradient."""
        self._debug_distance_field_mesh = None
        self._debug_distance_field_gpu = None

        if self._debug_builder is None:
            return

        distance_fields = self._debug_builder._last_distance_fields
        if not distance_fields:
            return

        # Используем данные из polygon_builder (вычислены в watershed)
        self._cached_distance_fields = distance_fields
        self._cached_local_maxima = self._debug_builder._last_all_local_maxima
        self._cached_plateau_peaks = self._debug_builder._last_peaks
        self._cached_eroded_voxels = self._debug_builder._last_eroded_voxels

        print(f"NavMeshBuilderComponent: using cached peaks: local_maxima={len(self._cached_local_maxima)}, peaks={len(self._cached_plateau_peaks)}, eroded={len(self._cached_eroded_voxels)}")

        # Build mesh using cached data
        self._rebuild_distance_field_from_cache()

    def _rebuild_distance_field_from_cache(self) -> None:
        """Rebuild distance field mesh from cached data (peaks, distance fields)."""
        from termin.voxels.display_component import (
            _CUBE_VERTICES, _CUBE_TRIANGLES, _CUBE_NORMALS,
            VERTS_PER_CUBE, TRIS_PER_CUBE, CUBE_SCALE,
        )

        self._debug_distance_field_mesh = None
        self._debug_distance_field_gpu = None

        if self._debug_grid is None:
            return

        # Нужны либо per-region distance fields, либо eroded voxels
        has_distance_fields = bool(self._cached_distance_fields)
        has_eroded = bool(self._cached_eroded_voxels)
        if not has_distance_fields and not has_eroded:
            return

        grid = self._debug_grid
        distance_fields = self._cached_distance_fields
        cube_size = grid.cell_size * CUBE_SCALE

        # Update cached checkbox state
        self._cached_show_local_maxima = self.show_local_maxima
        self._cached_show_peaks = self.show_peaks

        # Count total voxels (per-region + eroded)
        total_voxels = sum(len(df) for df in distance_fields) + len(self._cached_eroded_voxels)
        if total_voxels == 0:
            return

        # Find global max distance for normalization
        global_max_dist = 1.0
        for df in distance_fields:
            if df:
                max_dist = max(df.values())
                if max_dist > global_max_dist:
                    global_max_dist = max_dist

        verts_per_cube = VERTS_PER_CUBE
        tris_per_cube = TRIS_PER_CUBE
        cube_vertices = _CUBE_VERTICES
        cube_triangles = _CUBE_TRIANGLES
        cube_normals = _CUBE_NORMALS

        vertices = np.zeros((total_voxels * verts_per_cube, 3), dtype=np.float32)
        triangles = np.zeros((total_voxels * tris_per_cube, 3), dtype=np.int32)
        normals = np.zeros((total_voxels * verts_per_cube, 3), dtype=np.float32)
        uvs = np.zeros((total_voxels * verts_per_cube, 2), dtype=np.float32)
        colors = np.zeros((total_voxels * verts_per_cube, 3), dtype=np.float32)

        voxel_idx = 0

        # Рисуем воксели из per-region distance fields
        for df in distance_fields:
            for voxel, dist in df.items():
                vx, vy, vz = voxel
                center = grid.voxel_to_world(vx, vy, vz)

                v_offset = voxel_idx * verts_per_cube
                t_offset = voxel_idx * tris_per_cube

                vertices[v_offset:v_offset + verts_per_cube] = cube_vertices * cube_size + center
                triangles[t_offset:t_offset + tris_per_cube] = cube_triangles + v_offset
                normals[v_offset:v_offset + verts_per_cube] = cube_normals
                uvs[v_offset:v_offset + verts_per_cube, 0] = 2.0  # vertex color mode

                # Check voxel state
                is_plateau_peak = self.show_peaks and voxel in self._cached_plateau_peaks
                is_local_max = self.show_local_maxima and voxel in self._cached_local_maxima

                if is_plateau_peak:
                    r, g, b = 1.0, 1.0, 1.0
                elif is_local_max:
                    r, g, b = 1.0, 0.0, 1.0
                else:
                    # Color gradient: blue (boundary) -> green -> yellow -> red (center)
                    t = dist / global_max_dist if global_max_dist > 0 else 0.0
                    if t < 0.33:
                        r, g, b = 0.0, t * 3, 1.0
                    elif t < 0.66:
                        tt = (t - 0.33) * 3
                        r, g, b = tt, 1.0, 1.0 - tt
                    else:
                        tt = (t - 0.66) * 3
                        r, g, b = 1.0, 1.0 - tt, 0.0

                colors[v_offset:v_offset + verts_per_cube] = (r, g, b)
                voxel_idx += 1

        # Рисуем eroded воксели (из глобального distance field) чёрным
        for voxel in self._cached_eroded_voxels:
            vx, vy, vz = voxel
            center = grid.voxel_to_world(vx, vy, vz)

            v_offset = voxel_idx * verts_per_cube
            t_offset = voxel_idx * tris_per_cube

            vertices[v_offset:v_offset + verts_per_cube] = cube_vertices * cube_size + center
            triangles[t_offset:t_offset + tris_per_cube] = cube_triangles + v_offset
            normals[v_offset:v_offset + verts_per_cube] = cube_normals
            uvs[v_offset:v_offset + verts_per_cube, 0] = 2.0  # vertex color mode
            colors[v_offset:v_offset + verts_per_cube] = (0.0, 0.0, 0.0)  # Black for eroded
            voxel_idx += 1

        self._debug_distance_field_mesh = create_voxel_mesh(
            vertices=vertices,
            triangles=triangles,
            uvs=uvs,
            vertex_colors=colors,
            vertex_normals=normals,
            name="navmesh_builder_debug_distance_field",
        )

        print(f"NavMeshBuilderComponent: distance field mesh rebuilt ({total_voxels} voxels, max_dist={global_max_dist:.1f})")

    def _build_debug_mesh_from_navmesh(self, navmesh: "NavMesh") -> None:
        """Build debug mesh from finished NavMesh."""
        import colorsys

        self._debug_triangulated_mesh = None
        self._debug_triangulated_gpu = None

        all_vertices: list[np.ndarray] = []
        all_triangles: list[np.ndarray] = []
        all_colors: list[np.ndarray] = []
        vertex_offset = 0

        normal_offset = 0.15

        for poly_idx, polygon in enumerate(navmesh.polygons):
            if len(polygon.vertices) == 0 or len(polygon.triangles) == 0:
                continue

            hue = (poly_idx * 0.618033988749895) % 1.0
            region_color = colorsys.hsv_to_rgb(hue, 0.7, 0.9)

            offset_vertices = polygon.vertices + polygon.normal * normal_offset

            all_vertices.append(offset_vertices)
            all_triangles.append(polygon.triangles + vertex_offset)

            vertex_colors = np.full((len(polygon.vertices), 3), region_color, dtype=np.float32)
            all_colors.append(vertex_colors)

            vertex_offset += len(polygon.vertices)

        if not all_vertices:
            return

        vertices = np.vstack(all_vertices).astype(np.float32)
        triangles = np.vstack(all_triangles).astype(np.int32)
        colors = np.vstack(all_colors).astype(np.float32)

        # Compute normals
        normals = np.zeros_like(vertices)
        for tri in triangles:
            v0, v1, v2 = vertices[tri[0]], vertices[tri[1]], vertices[tri[2]]
            face_normal = np.cross(v1 - v0, v2 - v0)
            norm = np.linalg.norm(face_normal)
            if norm > 1e-10:
                face_normal = face_normal / norm
            normals[tri[0]] += face_normal
            normals[tri[1]] += face_normal
            normals[tri[2]] += face_normal

        for i in range(len(normals)):
            norm = np.linalg.norm(normals[i])
            if norm > 1e-10:
                normals[i] = normals[i] / norm

        self._debug_triangulated_mesh = create_voxel_mesh(
            vertices=vertices,
            triangles=triangles,
            uvs=np.full((len(vertices), 2), [2.0, 0.0], dtype=np.float32),
            vertex_colors=colors,
            vertex_normals=normals.astype(np.float32),
            name="navmesh_builder_debug_triangulated",
        )

        print(f"NavMeshBuilderComponent: triangulated mesh ({len(navmesh.polygons)} polygons, {len(vertices)} vertices, {len(triangles)} triangles)")
