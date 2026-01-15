"""
NavMeshMaterialComponent - renders NavMesh using a material.

Simple component that displays NavMesh geometry with a user-selected material.
Implements Drawable protocol for integration with ColorPass.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Set

import numpy as np

from termin.visualization.core.python_component import PythonComponent
from termin.mesh import TcMesh
from termin.assets.navmesh_handle import NavMeshHandle
from termin._native.render import TcMaterial
from termin.visualization.render.drawable import GeometryDrawCall
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.render.render_context import RenderContext
    from termin.navmesh.types import NavMesh
    from termin._native.render import MeshGPU, TcMaterialPhase


class NavMeshMaterialComponent(PythonComponent):
    """
    Component for rendering NavMesh with a material.

    Implements Drawable protocol - renders NavMesh geometry using selected material.
    Supports hot-reload via NavMeshHandle.
    """

    is_drawable = True

    inspect_fields = {
        "navmesh": InspectField(
            path="navmesh",
            label="NavMesh",
            kind="navmesh_handle",
        ),
    }

    def __init__(
        self,
        navmesh_name: str = "",
        material_name: str = "",
    ) -> None:
        super().__init__()
        self.navmesh: NavMeshHandle = NavMeshHandle()
        self._material: TcMaterial | None = None
        self._last_navmesh: Optional["NavMesh"] = None
        self._mesh: Optional[TcMesh] = None
        self._mesh_gpu: Optional["MeshGPU"] = None
        self._needs_rebuild = True

        if navmesh_name:
            self.navmesh = NavMeshHandle.from_name(navmesh_name)
        if material_name:
            self.set_material_by_name(material_name)

    @property
    def material(self) -> TcMaterial | None:
        """Current material."""
        return self._material

    @material.setter
    def material(self, value: TcMaterial | None) -> None:
        """Set material."""
        self._material = value

    def set_material_by_name(self, name: str) -> None:
        """Set material by name from ResourceManager."""
        from termin.assets.resources import ResourceManager
        rm = ResourceManager.instance()
        asset = rm.get_material_asset(name)
        if asset is not None:
            self._material = asset.material
        else:
            self._material = None

    # --- Drawable protocol ---

    @property
    def phase_marks(self) -> Set[str]:
        """Get phase marks from material."""
        mat = self._material
        if mat is None:
            return set()
        marks: Set[str] = set()
        for i in range(mat.phase_count):
            phase = mat.get_phase(i)
            if phase is not None:
                marks.add(phase.phase_mark)
        return marks

    def draw_geometry(self, context: "RenderContext", geometry_id: int = 0) -> None:
        """Draw NavMesh geometry."""
        self._check_hot_reload()

        if self._mesh is not None and self._mesh.is_valid:
            if self._mesh_gpu is None:
                from termin._native.render import MeshGPU
                self._mesh_gpu = MeshGPU()
            self._mesh_gpu.draw(context, self._mesh.mesh, self._mesh.version)

    def _check_hot_reload(self) -> None:
        """Check if navmesh changed (hot-reload)."""
        current = self.navmesh.get_navmesh()
        if self._needs_rebuild or current is not self._last_navmesh:
            self._needs_rebuild = False
            self._rebuild_mesh()

    def get_geometry_draws(self, phase_mark: str | None = None) -> List[GeometryDrawCall]:
        """Return GeometryDrawCalls for rendering."""
        mat = self._material
        if mat is None:
            return []

        # Collect phases from TcMaterial
        phases: List["TcMaterialPhase"] = []
        for i in range(mat.phase_count):
            phase = mat.get_phase(i)
            if phase is None:
                continue
            if phase_mark is None or phase.phase_mark == phase_mark:
                phases.append(phase)

        phases.sort(key=lambda p: p.priority)
        return [GeometryDrawCall(phase=phase, geometry_id=0) for phase in phases]

    # --- Mesh building ---

    def _rebuild_mesh(self) -> None:
        """Rebuild mesh from NavMesh."""
        self._mesh = None
        self._mesh_gpu = None

        navmesh = self.navmesh.get_navmesh()
        self._last_navmesh = navmesh

        if navmesh is None or navmesh.polygon_count() == 0:
            return

        # Collect all vertices and triangles from polygons
        all_vertices: list[np.ndarray] = []
        all_normals: list[np.ndarray] = []
        all_triangles: list[np.ndarray] = []
        vertex_offset = 0

        for polygon in navmesh.polygons:
            verts = polygon.vertices
            tris = polygon.triangles
            normal = polygon.normal

            if len(verts) == 0 or len(tris) == 0:
                continue

            all_vertices.append(verts)

            # One normal per polygon surface
            poly_normals = np.tile(normal, (len(verts), 1))
            all_normals.append(poly_normals)

            # Offset triangle indices
            shifted_tris = tris + vertex_offset
            all_triangles.append(shifted_tris)

            vertex_offset += len(verts)

        if all_vertices:
            from termin.voxels.voxel_mesh import create_voxel_mesh
            vertices = np.vstack(all_vertices).astype(np.float32)
            normals = np.vstack(all_normals).astype(np.float32)
            triangles = np.vstack(all_triangles).astype(np.int32)

            self._mesh = create_voxel_mesh(
                vertices=vertices,
                triangles=triangles,
                vertex_normals=normals,
                name="navmesh_material",
            )

    def invalidate(self) -> None:
        """Force mesh rebuild on next frame."""
        self._needs_rebuild = True
