"""Handle accessors mixin for ResourceManager."""

from __future__ import annotations

from typing import Any, Optional, TYPE_CHECKING

from ._handle_accessors import HandleAccessors

if TYPE_CHECKING:
    from termin.assets.material_handle import MaterialHandle
    from termin.assets.voxel_grid_handle import VoxelGridHandle
    from termin.assets.navmesh_handle import NavMeshHandle
    from termin.assets.skeleton_handle import SkeletonHandle
    from termin.assets.ui_handle import UIHandle
    from termin.mesh import TcMesh


class AccessorsMixin:
    """Mixin for handle accessors."""

    def get_handle_accessors(self, kind: str) -> Optional[HandleAccessors]:
        """
        Get unified handle accessors for a resource kind.

        Args:
            kind: Resource kind (material_handle, mesh_handle, audio_clip, voxel_grid, navmesh, skeleton, texture)

        Returns:
            HandleAccessors with list_names, get_by_name, find_name methods
        """
        if kind == "material_handle":
            return HandleAccessors(
                list_names=self.list_material_names,
                get_by_name=self._get_material_handle,
                find_name=self._find_material_handle_name,
                find_uuid=self._find_material_uuid_by_name,
            )
        if kind == "mesh_handle":
            return HandleAccessors(
                list_names=self.list_mesh_names,
                get_by_name=self.get_mesh,
                find_name=self.find_mesh_name,
                find_uuid=self._find_mesh_uuid_by_name,
            )
        if kind == "audio_clip_handle":
            return HandleAccessors(
                list_names=self.list_audio_clip_names,
                get_by_name=self.get_audio_clip,
                find_name=self.find_audio_clip_name,
                find_uuid=self._find_audio_clip_uuid_by_name,
            )
        if kind == "voxel_grid_handle":
            return HandleAccessors(
                list_names=self.list_voxel_grid_names,
                get_by_name=self._get_voxel_grid_handle,
                find_name=self._find_voxel_grid_handle_name,
                find_uuid=self._find_voxel_grid_uuid_by_name,
            )
        if kind == "navmesh_handle":
            return HandleAccessors(
                list_names=self.list_navmesh_names,
                get_by_name=self._get_navmesh_handle,
                find_name=self._find_navmesh_handle_name,
                find_uuid=self._find_navmesh_uuid_by_name,
            )
        if kind == "skeleton_handle":
            return HandleAccessors(
                list_names=self.list_skeleton_names,
                get_by_name=self._get_skeleton_handle,
                find_name=self._find_skeleton_handle_name,
                find_uuid=self._find_skeleton_uuid_by_name,
            )
        if kind == "texture_handle":
            return HandleAccessors(
                list_names=self.list_texture_names,
                get_by_name=self.get_texture_handle,
                find_name=self._find_texture_handle_name,
                find_uuid=self._find_texture_uuid_by_name,
            )
        if kind == "ui_handle":
            return HandleAccessors(
                list_names=self.list_ui_names,
                get_by_name=self._get_ui_handle,
                find_name=self._find_ui_handle_name,
                find_uuid=self._find_ui_uuid_by_name,
            )
        if kind == "tc_mesh":
            return HandleAccessors(
                list_names=self._list_tc_mesh_names,
                get_by_name=self._get_tc_mesh_by_name,
                find_name=self._find_tc_mesh_name,
                find_uuid=self._find_tc_mesh_uuid_by_name,
            )
        return None

    # Handle accessors for MaterialHandle
    def _get_material_handle(self, name: str) -> Optional["MaterialHandle"]:
        """Get MaterialHandle by name."""
        from termin.assets.material_handle import MaterialHandle
        return MaterialHandle.from_name(name)

    def _find_material_handle_name(self, handle: Any) -> Optional[str]:
        """Find name for a MaterialHandle or Material."""
        from termin.assets.material_handle import MaterialHandle
        if isinstance(handle, MaterialHandle):
            asset = handle.get_asset()
            if asset:
                return asset.name
            # Try to find by material
            mat = handle.get()
            if mat:
                return self.find_material_name(mat)
            return None
        # Legacy: raw Material object
        return self.find_material_name(handle)

    # Handle accessors for VoxelGridHandle (creates handle on-the-fly)
    def _get_voxel_grid_handle(self, name: str) -> Optional["VoxelGridHandle"]:
        """Get VoxelGridHandle by name."""
        from termin.assets.voxel_grid_handle import VoxelGridHandle
        return VoxelGridHandle.from_name(name)

    def _find_voxel_grid_handle_name(self, handle: Any) -> Optional[str]:
        """Find name for a VoxelGridHandle or VoxelGrid."""
        from termin.assets.voxel_grid_handle import VoxelGridHandle
        if isinstance(handle, VoxelGridHandle):
            asset = handle.get_asset()
            if asset:
                return asset.name
            grid = handle.get()
            if grid:
                return self.find_voxel_grid_name(grid)
            return None
        # Legacy: raw VoxelGrid
        return self.find_voxel_grid_name(handle)

    # Handle accessors for NavMeshHandle
    def _get_navmesh_handle(self, name: str) -> Optional["NavMeshHandle"]:
        """Get NavMeshHandle by name."""
        from termin.assets.navmesh_handle import NavMeshHandle
        return NavMeshHandle.from_name(name)

    def _find_navmesh_handle_name(self, handle: Any) -> Optional[str]:
        """Find name for a NavMeshHandle or NavMesh."""
        from termin.assets.navmesh_handle import NavMeshHandle
        if isinstance(handle, NavMeshHandle):
            asset = handle.get_asset()
            if asset:
                return asset.name
            navmesh = handle.get()
            if navmesh:
                return self.find_navmesh_name(navmesh)
            return None
        # Legacy: raw NavMesh
        return self.find_navmesh_name(handle)

    # Handle accessors for SkeletonHandle
    def _get_skeleton_handle(self, name: str) -> Optional["SkeletonHandle"]:
        """Get SkeletonHandle by name."""
        from termin.assets.skeleton_handle import SkeletonHandle
        return SkeletonHandle.from_name(name)

    def _find_skeleton_handle_name(self, handle: Any) -> Optional[str]:
        """Find name for a SkeletonHandle or SkeletonData."""
        from termin.assets.skeleton_handle import SkeletonHandle
        if isinstance(handle, SkeletonHandle):
            asset = handle.get_asset()
            if asset:
                return asset.name
            skeleton = handle.get()
            if skeleton:
                return self.find_skeleton_name(skeleton)
            return None
        # Legacy: raw SkeletonData
        return self.find_skeleton_name(handle)

    # Handle accessors for TextureHandle
    def _find_texture_handle_name(self, handle: Any) -> Optional[str]:
        """Find name for a TextureHandle."""
        from termin.assets.texture_handle import TextureHandle
        if isinstance(handle, TextureHandle):
            return self.find_texture_name(handle)
        return None

    # Handle accessors for UIHandle
    def _get_ui_handle(self, name: str) -> Optional["UIHandle"]:
        """Get UIHandle by name."""
        from termin.assets.ui_handle import UIHandle
        return UIHandle.from_name(name)

    def _find_ui_handle_name(self, handle: Any) -> Optional[str]:
        """Find name for a UIHandle."""
        from termin.assets.ui_handle import UIHandle
        if isinstance(handle, UIHandle):
            asset = handle.get_asset()
            if asset is not None:
                return asset.name
        return None

    # Handle accessors for TcMesh
    def _list_tc_mesh_names(self) -> list[str]:
        """Get list of all mesh names from assets."""
        return list(self._mesh_assets.keys())

    def _get_tc_mesh_by_name(self, name: str) -> Optional["TcMesh"]:
        """Get TcMesh by name, loading asset if needed."""
        asset = self._mesh_assets.get(name)
        if asset is None:
            return None
        return asset.data

    def _find_tc_mesh_name(self, mesh: Any) -> Optional[str]:
        """Find name for a TcMesh."""
        from termin.mesh import TcMesh
        if isinstance(mesh, TcMesh) and mesh.is_valid:
            return mesh.name
        return None

    # UUID lookup by name helpers
    def _find_material_uuid_by_name(self, name: str) -> Optional[str]:
        """Find UUID for material by name."""
        asset = self._material_assets.get(name)
        return asset.uuid if asset else None

    def _find_mesh_uuid_by_name(self, name: str) -> Optional[str]:
        """Find UUID for mesh by name."""
        asset = self._mesh_assets.get(name)
        return asset.uuid if asset else None

    def _find_audio_clip_uuid_by_name(self, name: str) -> Optional[str]:
        """Find UUID for audio clip by name."""
        asset = self._audio_clip_assets.get(name)
        return asset.uuid if asset else None

    def _find_voxel_grid_uuid_by_name(self, name: str) -> Optional[str]:
        """Find UUID for voxel grid by name."""
        asset = self._voxel_grid_assets.get(name)
        return asset.uuid if asset else None

    def _find_navmesh_uuid_by_name(self, name: str) -> Optional[str]:
        """Find UUID for navmesh by name."""
        asset = self._navmesh_assets.get(name)
        return asset.uuid if asset else None

    def _find_skeleton_uuid_by_name(self, name: str) -> Optional[str]:
        """Find UUID for skeleton by name."""
        asset = self._skeleton_assets.get(name)
        return asset.uuid if asset else None

    def _find_texture_uuid_by_name(self, name: str) -> Optional[str]:
        """Find UUID for texture by name."""
        asset = self._texture_assets.get(name)
        return asset.uuid if asset else None

    def _find_ui_uuid_by_name(self, name: str) -> Optional[str]:
        """Find UUID for UI by name."""
        asset = self._ui_assets.get(name)
        return asset.uuid if asset else None

    def _find_tc_mesh_uuid_by_name(self, name: str) -> Optional[str]:
        """Find UUID for TcMesh by name."""
        asset = self._mesh_assets.get(name)
        # Use asset.uuid, not asset.data.uuid to avoid triggering lazy loading
        return asset.uuid if asset else None

    def get_handle_by_uuid(self, kind: str, uuid: str) -> Any:
        """
        Get a Handle by UUID for the specified resource kind.

        Args:
            kind: Resource kind (mesh, material, voxel_grid, navmesh, skeleton, audio_clip, texture)
            uuid: Asset UUID

        Returns:
            Handle instance or None if not found
        """
        if kind == "mesh":
            return self.get_mesh_by_uuid(uuid)

        if kind == "material":
            from termin.assets.material_handle import MaterialHandle
            asset = self.get_material_asset_by_uuid(uuid)
            if asset:
                return MaterialHandle.from_asset(asset)
            return None

        if kind == "voxel_grid":
            from termin.assets.voxel_grid_handle import VoxelGridHandle
            asset = self.get_voxel_grid_asset_by_uuid(uuid)
            if asset:
                return VoxelGridHandle.from_asset(asset)
            return None

        if kind == "navmesh":
            from termin.assets.navmesh_handle import NavMeshHandle
            asset = self.get_navmesh_asset_by_uuid(uuid)
            if asset:
                return NavMeshHandle.from_asset(asset)
            return None

        if kind == "skeleton":
            from termin.assets.skeleton_handle import SkeletonHandle
            asset = self.get_skeleton_asset_by_uuid(uuid)
            if asset:
                return SkeletonHandle.from_asset(asset)
            return None

        if kind == "audio_clip":
            return self.get_audio_clip_by_uuid(uuid)

        if kind == "texture":
            from termin.assets.texture_handle import TextureHandle
            asset = self.get_texture_asset_by_uuid(uuid)
            if asset:
                return TextureHandle.from_asset(asset)
            return None

        return None
