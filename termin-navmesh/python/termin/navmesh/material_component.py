"""
NavMeshMaterialComponent - renders NavMesh using a material.

Simple component that displays NavMesh geometry with a user-selected material.
Implements Drawable protocol for integration with ColorPass.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Set

import numpy as np

from termin.render import DrawableComponent
from termin.mesh import TcMesh
from termin.navmesh._navmesh_native import TcNavMesh
from termin.materials import TcMaterial
from termin.render.drawable import RenderItem, RenderItemCollectContext
from termin.inspect import InspectField

if TYPE_CHECKING:
    from termin.navmesh.types import NavMesh
    from termin.materials import TcMaterialPhase


class NavMeshMaterialComponent(DrawableComponent):
    """
    Component for rendering NavMesh with a material.

    Implements Drawable protocol - renders NavMesh geometry using selected material.
    Supports hot-reload via TcNavMesh.
    """

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
        self.navmesh: TcNavMesh = TcNavMesh()
        self._material: TcMaterial | None = None
        self._last_navmesh: Optional["NavMesh"] = None
        self._last_navmesh_version: int = -1
        self._mesh: Optional[TcMesh] = None
        self._needs_rebuild = True

        if navmesh_name:
            self.navmesh = TcNavMesh.from_name(navmesh_name)
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
        from tcbase import log
        from termin_assets import get_resource_manager

        rm = get_resource_manager()
        if rm is None:
            log.error("[NavMeshMaterialComponent] Resource manager is not configured")
            self._material = None
            return
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

    def _check_hot_reload(self) -> None:
        """Check if navmesh changed (hot-reload)."""
        current_version = self.navmesh.version
        if self._needs_rebuild or current_version != self._last_navmesh_version:
            self._needs_rebuild = False
            self._last_navmesh_version = current_version
            self._rebuild_mesh()

    def collect_render_items(self, context: RenderItemCollectContext) -> list[RenderItem]:
        """Return RenderItems for rendering."""
        self._check_hot_reload()
        if self._mesh is None or not self._mesh.is_valid:
            return []

        mat = self._material
        if mat is None:
            return []

        # Collect phases from TcMaterial
        phases: list["TcMaterialPhase"] = []
        for i in range(mat.phase_count):
            phase = mat.get_phase(i)
            if phase is None:
                continue
            if context.phase_mark == "" or phase.phase_mark == context.phase_mark:
                phases.append(phase)

        phases.sort(key=lambda p: p.priority)
        return [RenderItem.mesh(mesh=self._mesh, phase=phase, geometry_id=0) for phase in phases]

    # --- Mesh building ---

    def _rebuild_mesh(self) -> None:
        """Rebuild mesh from NavMesh."""
        self._mesh = None

        navmesh = self._get_navmesh_payload()
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

    def _get_navmesh_payload(self) -> "NavMesh | None":
        """Resolve legacy polygon payload for the selected canonical TcNavMesh."""
        if not self.navmesh.is_valid:
            return None
        self.navmesh.ensure_loaded()
        from termin_assets import get_resource_manager
        from tcbase import log

        rm = get_resource_manager()
        if rm is None:
            log.error("[NavMeshMaterialComponent] Resource manager is not configured")
            return None
        asset = rm.get_navmesh_asset_by_uuid(self.navmesh.uuid)
        if asset is None and self.navmesh.name:
            asset = rm.get_navmesh_asset(self.navmesh.name)
        if asset is None:
            log.error(f"[NavMeshMaterialComponent] NavMesh asset not found: {self.navmesh.uuid}")
            return None
        return asset.navmesh

    def invalidate(self) -> None:
        """Force mesh rebuild on next frame."""
        self._needs_rebuild = True
