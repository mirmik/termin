"""Default handle accessors for standard Termin asset resources."""

from __future__ import annotations

from typing import Any, Optional, TYPE_CHECKING

from tcbase import log
from termin_assets import AssetCreationPlugin

from termin.default_assets.handle_accessors import HandleAccessors

if TYPE_CHECKING:
    from termin.default_assets.ui.handle import UIHandle
    from termin.materials import TcMaterial
    from termin.mesh import TcMesh
    from termin.navmesh._navmesh_native import TcNavMesh
    from termin.skeleton._skeleton_native import TcSkeleton
    from termin.voxels._voxels_native import TcVoxelGrid


class DefaultResourceAccessorsMixin:
    """Mixin for default resource handle accessors."""

    def get_handle_accessors(self, kind: str) -> Optional[HandleAccessors]:
        """
        Get unified handle accessors for a resource kind.

        Args:
            kind: Resource kind such as ``tc_material``, ``tc_texture``,
                ``mesh_handle``, ``voxel_grid_handle`` or ``navmesh_handle``.

        Returns:
            ``HandleAccessors`` for the kind, or ``None`` if the kind is unknown.
        """
        if kind == "tc_material":
            return HandleAccessors(
                list_names=self.list_material_names,
                get_by_name=self._get_tc_material,
                find_name=self._find_tc_material_name,
                find_uuid=self._find_material_uuid_by_name,
                iter_items=lambda: self._runtime_handle_items("material"),
            )
        if kind == "mesh_handle":
            return HandleAccessors(
                list_names=self.list_mesh_names,
                get_by_name=self.get_mesh,
                find_name=self.find_mesh_name,
                find_uuid=self._find_mesh_uuid_by_name,
                iter_items=lambda: self._runtime_handle_items("mesh"),
            )
        if kind == "audio_clip_handle":
            return HandleAccessors(
                list_names=self.list_audio_clip_names,
                get_by_name=self.get_audio_clip,
                find_name=self.find_audio_clip_name,
                find_uuid=self._find_audio_clip_uuid_by_name,
                iter_items=lambda: self._runtime_handle_items("audio_clip"),
            )
        if kind == "voxel_grid_handle":
            return HandleAccessors(
                list_names=self.list_voxel_grid_names,
                get_by_name=self._get_voxel_grid_handle,
                find_name=self._find_voxel_grid_handle_name,
                find_uuid=self._find_voxel_grid_uuid_by_name,
                iter_items=lambda: self._runtime_handle_items("voxel_grid"),
            )
        if kind == "navmesh_handle":
            return HandleAccessors(
                list_names=self.list_navmesh_names,
                get_by_name=self._get_navmesh_handle,
                find_name=self._find_navmesh_handle_name,
                find_uuid=self._find_navmesh_uuid_by_name,
                iter_items=lambda: self._runtime_handle_items("navmesh"),
            )
        if kind == "tc_skeleton":
            return HandleAccessors(
                list_names=self.list_skeleton_names,
                get_by_name=self._get_tc_skeleton,
                find_name=self._find_tc_skeleton_name,
                find_uuid=self._find_skeleton_uuid_by_name,
                iter_items=lambda: self._runtime_handle_items("skeleton"),
            )
        if kind in ("tc_texture", "texture_handle"):
            return HandleAccessors(
                list_names=self.list_texture_names,
                get_by_name=self.get_texture_handle,
                find_name=self._find_tc_texture_name,
                find_uuid=self._find_texture_uuid_by_name,
                iter_items=lambda: self._runtime_handle_items("texture"),
            )
        if kind == "ui_handle":
            return HandleAccessors(
                list_names=self.list_ui_names,
                get_by_name=self._get_ui_handle,
                find_name=self._find_ui_handle_name,
                find_uuid=self._find_ui_uuid_by_name,
                iter_items=lambda: self._runtime_handle_items("ui"),
            )
        if kind == "tc_mesh":
            return HandleAccessors(
                list_names=self._list_tc_mesh_names,
                get_by_name=self._get_tc_mesh_by_name,
                find_name=self._find_tc_mesh_name,
                find_uuid=self._find_tc_mesh_uuid_by_name,
                iter_items=lambda: self._runtime_handle_items("mesh"),
            )
        if kind.endswith("_handle"):
            type_id = kind[:-7]
            plugin = self.asset_type_plugins.get_import(type_id)
            if plugin is not None:
                return HandleAccessors(
                    list_names=lambda: self.external_assets.list_names(type_id),
                    get_by_name=lambda name: self.external_assets.get_by_name(type_id, name),
                    find_name=lambda record: record.name if record is not None else None,
                    find_uuid=lambda name: self.external_assets.find_uuid_by_name(type_id, name),
                    iter_items=lambda: (
                        (record.name, record.uuid)
                        for record in self.external_assets.iter_records(type_id)
                    ),
                    create_item=lambda: self._create_external_asset(type_id),
                )
        return None

    def _runtime_handle_items(self, type_id: str):
        return ((asset.name, asset.uuid) for asset in self.iter_runtime_assets(type_id))

    def _create_external_asset(self, type_id: str) -> tuple[str, Optional[str]] | None:
        plugin = self.asset_type_plugins.get_import(type_id)
        if plugin is None:
            log.error(f"[ResourceManager] Cannot create external asset: import plugin not found: {type_id}")
            return None
        if not isinstance(plugin, AssetCreationPlugin):
            log.error(f"[ResourceManager] Import plugin does not support asset creation: {type_id}")
            return None
        if self.external_assets.project_root is None:
            log.error(f"[ResourceManager] Cannot create external asset without project root: {type_id}")
            return None

        base_name = type_id
        existing = set(self.external_assets.list_names(type_id))
        name = base_name
        index = 1
        while name in existing:
            index += 1
            name = f"{base_name}_{index:02d}"

        try:
            result = plugin.create_asset(str(self.external_assets.project_root), name)
            self.register_file(result)
            created_name = result.path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
            return created_name, result.uuid
        except Exception as e:
            log.error(f"[ResourceManager] Failed to create external asset {type_id}: {e}")
            return None

    def _get_tc_material(self, name: str) -> Optional["TcMaterial"]:
        """Get TcMaterial by name."""
        from termin.materials import TcMaterial

        mat = TcMaterial.from_name(name)
        return mat if mat.is_valid else None

    def _find_tc_material_name(self, handle: Any) -> Optional[str]:
        """Find name for a TcMaterial."""
        from termin.materials import TcMaterial

        if isinstance(handle, TcMaterial) and handle.is_valid:
            return handle.name or None
        return None

    def _get_voxel_grid_handle(self, name: str) -> Optional["TcVoxelGrid"]:
        """Get TcVoxelGrid by name."""
        from termin.voxels._voxels_native import TcVoxelGrid

        handle = TcVoxelGrid.from_name(name)
        return handle if handle.is_valid else None

    def _find_voxel_grid_handle_name(self, handle: Any) -> Optional[str]:
        """Find name for a TcVoxelGrid."""
        from termin.voxels._voxels_native import TcVoxelGrid

        if isinstance(handle, TcVoxelGrid) and handle.is_valid:
            return handle.name or None
        return None

    def _get_navmesh_handle(self, name: str) -> Optional["TcNavMesh"]:
        """Get TcNavMesh by name."""
        from termin.navmesh._navmesh_native import TcNavMesh

        handle = TcNavMesh.from_name(name)
        return handle if handle.is_valid else None

    def _find_navmesh_handle_name(self, handle: Any) -> Optional[str]:
        """Find name for a TcNavMesh."""
        from termin.navmesh._navmesh_native import TcNavMesh

        if isinstance(handle, TcNavMesh) and handle.is_valid:
            return handle.name or None
        return None

    def _get_tc_skeleton(self, name: str) -> Optional["TcSkeleton"]:
        """Get TcSkeleton by name."""
        from termin.skeleton._skeleton_native import TcSkeleton

        asset = self._skeleton_assets.get(name)
        if asset is None:
            return None
        return TcSkeleton.from_uuid(asset.uuid)

    def _find_tc_skeleton_name(self, handle: Any) -> Optional[str]:
        """Find name for a TcSkeleton."""
        from termin.skeleton._skeleton_native import TcSkeleton

        if isinstance(handle, TcSkeleton) and handle.is_valid:
            return handle.name
        return None

    def _find_tc_texture_name(self, handle: Any) -> Optional[str]:
        """Find name for a TcTexture."""
        from tgfx import TcTexture

        if isinstance(handle, TcTexture):
            return self.find_texture_name(handle)
        return None

    def _get_ui_handle(self, name: str) -> Optional["UIHandle"]:
        """Get UIHandle by name."""
        from termin.default_assets.ui.handle import UIHandle

        return UIHandle.from_name(name)

    def _find_ui_handle_name(self, handle: Any) -> Optional[str]:
        """Find name for a UIHandle."""
        from termin.default_assets.ui.handle import UIHandle

        if isinstance(handle, UIHandle):
            asset = handle.get_asset()
            if asset is not None:
                return asset.name
        return None

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

    def _find_material_uuid_by_name(self, name: str) -> Optional[str]:
        """Find UUID for material by name."""
        asset = self.get_material_asset(name)
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
        return asset.uuid if asset else None

    def get_handle_by_uuid(self, kind: str, uuid: str) -> Any:
        """
        Get a handle by UUID for the specified resource kind.

        Args:
            kind: Resource kind such as ``mesh``, ``material``, ``voxel_grid``,
                ``navmesh``, ``skeleton``, ``audio_clip``, ``texture`` or
                ``tc_texture``.
            uuid: Asset UUID.

        Returns:
            Handle instance or ``None`` if not found.
        """
        if kind == "mesh":
            return self.get_mesh_by_uuid(uuid)

        if kind == "material":
            from termin.materials import TcMaterial

            return TcMaterial.from_uuid(uuid)

        if kind == "voxel_grid":
            from termin.voxels._voxels_native import TcVoxelGrid

            handle = TcVoxelGrid.from_uuid(uuid)
            return handle if handle.is_valid else None

        if kind == "navmesh":
            from termin.navmesh._navmesh_native import TcNavMesh

            handle = TcNavMesh.from_uuid(uuid)
            return handle if handle.is_valid else None

        if kind == "skeleton":
            from termin.skeleton._skeleton_native import TcSkeleton

            return TcSkeleton.from_uuid(uuid)

        if kind == "audio_clip":
            return self.get_audio_clip_by_uuid(uuid)

        if kind in ("texture", "tc_texture"):
            from tgfx import TcTexture

            asset = self.get_texture_asset_by_uuid(uuid)
            if asset:
                texture = TcTexture.from_uuid(asset.uuid)
                if texture.is_valid:
                    return texture
                return asset.texture_data
            return None

        return None


# Compatibility alias for old app-side naming.
AccessorsMixin = DefaultResourceAccessorsMixin

__all__ = ["AccessorsMixin", "DefaultResourceAccessorsMixin", "HandleAccessors"]
