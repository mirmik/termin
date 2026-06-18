"""AssetRegistry factories for default Termin asset types."""

from __future__ import annotations


class DefaultAssetRegistryFactoryMixin:
    """Create runtime registries for asset types owned by default-assets.

    The host resource manager provides ``_assets_by_uuid`` and stores registry
    attributes. Keeping the factories here lets application hosts assemble a
    concrete manager without making ``termin-app`` own default asset type
    wiring.
    """

    def _create_prefab_registry(self):
        """Create AssetRegistry for prefabs."""
        from termin_assets import AssetRegistry

        def data_from_asset(asset):
            return asset

        def data_to_asset(data):
            for asset in self._prefab_registry.assets.values():
                if asset is data:
                    return asset
            return None

        def get_asset_class():
            from termin.prefab.asset import PrefabAsset
            return PrefabAsset

        return AssetRegistry(
            asset_class=get_asset_class,
            uuid_registry=self._assets_by_uuid,
            data_from_asset=data_from_asset,
            data_to_asset=data_to_asset,
        )

    def _create_material_registry(self):
        """Create AssetRegistry for materials."""
        from termin_assets import AssetRegistry

        def data_from_asset(asset):
            if asset.material is None:
                asset.ensure_loaded()
            return asset.material

        def data_to_asset(data):
            for asset in self._material_registry.assets.values():
                if asset.material is data:
                    return asset
            return None

        def get_asset_class():
            from termin.default_assets.render.material_asset import MaterialAsset
            return MaterialAsset

        return AssetRegistry(
            asset_class=get_asset_class,
            uuid_registry=self._assets_by_uuid,
            data_from_asset=data_from_asset,
            data_to_asset=data_to_asset,
        )

    def _create_shader_registry(self):
        """Create AssetRegistry for shader programs."""
        from termin_assets import AssetRegistry

        def data_from_asset(asset):
            if asset.program is None:
                asset.ensure_loaded()
            return asset.program

        def data_to_asset(data):
            for asset in self._shader_registry.assets.values():
                if asset.program is data:
                    return asset
            return None

        def get_asset_class():
            from termin.default_assets.render.shader_asset import ShaderAsset
            return ShaderAsset

        return AssetRegistry(
            asset_class=get_asset_class,
            uuid_registry=self._assets_by_uuid,
            data_from_asset=data_from_asset,
            data_to_asset=data_to_asset,
        )

    def _create_mesh_registry(self):
        """Create AssetRegistry for meshes."""
        from termin_assets import AssetRegistry
        from termin.default_assets.mesh.asset import MeshAsset
        from tmesh import TcMesh

        def data_from_asset(asset: MeshAsset) -> TcMesh | None:
            if asset.mesh_data is None:
                asset.ensure_loaded()
            return asset.mesh_data

        def data_to_asset(mesh: TcMesh) -> MeshAsset | None:
            if mesh is None or not mesh.is_valid:
                return None
            for asset in self._mesh_registry.assets.values():
                if asset.mesh_data is not None and asset.mesh_data.uuid == mesh.uuid:
                    return asset
            return None

        return AssetRegistry[MeshAsset, TcMesh](
            asset_class=MeshAsset,
            uuid_registry=self._assets_by_uuid,
            data_from_asset=data_from_asset,
            data_to_asset=data_to_asset,
        )

    def _create_texture_registry(self):
        """Create AssetRegistry for textures."""
        from termin_assets import AssetRegistry
        from termin.default_assets.render.texture_asset import TextureAsset
        from termin.render.texture_handle import TextureHandle

        def data_from_asset(asset: TextureAsset) -> TextureHandle:
            return TextureHandle.from_asset(asset)

        def data_to_asset(handle: TextureHandle) -> TextureAsset | None:
            return handle.asset

        return AssetRegistry[TextureAsset, TextureHandle](
            asset_class=TextureAsset,
            uuid_registry=self._assets_by_uuid,
            data_from_asset=data_from_asset,
            data_to_asset=data_to_asset,
        )

    def _create_voxel_grid_registry(self):
        """Create AssetRegistry for voxel grids."""
        from termin_assets import AssetRegistry

        def data_from_asset(asset):
            if asset.grid is None:
                asset.ensure_loaded()
            return asset.grid

        def data_to_asset(data):
            for asset in self._voxel_grid_registry.assets.values():
                if asset.grid is data:
                    return asset
            return None

        def get_asset_class():
            from termin.default_assets.voxels.asset import VoxelGridAsset
            return VoxelGridAsset

        return AssetRegistry(
            asset_class=get_asset_class,
            uuid_registry=self._assets_by_uuid,
            data_from_asset=data_from_asset,
            data_to_asset=data_to_asset,
        )

    def _create_navmesh_registry(self):
        """Create AssetRegistry for navmeshes."""
        from termin_assets import AssetRegistry

        def data_from_asset(asset):
            if asset.navmesh is None:
                asset.ensure_loaded()
            return asset.navmesh

        def data_to_asset(data):
            for asset in self._navmesh_registry.assets.values():
                if asset.navmesh is data:
                    return asset
            return None

        def get_asset_class():
            from termin.default_assets.navmesh.asset import NavMeshAsset
            return NavMeshAsset

        return AssetRegistry(
            asset_class=get_asset_class,
            uuid_registry=self._assets_by_uuid,
            data_from_asset=data_from_asset,
            data_to_asset=data_to_asset,
        )

    def _create_glsl_registry(self):
        """Create AssetRegistry for GLSL include files."""
        from termin_assets import AssetRegistry

        def data_from_asset(asset):
            if asset.source is None:
                asset.ensure_loaded()
            return asset.source

        def data_to_asset(data):
            for asset in self._glsl_registry.assets.values():
                if asset.source is data:
                    return asset
            return None

        def get_asset_class():
            from termin.default_assets.render.glsl_asset import GlslAsset
            return GlslAsset

        return AssetRegistry(
            asset_class=get_asset_class,
            uuid_registry=self._assets_by_uuid,
            data_from_asset=data_from_asset,
            data_to_asset=data_to_asset,
        )

    def _create_audio_clip_registry(self):
        """Create AssetRegistry for audio clips."""
        from termin_assets import AssetRegistry

        def data_from_asset(asset):
            from termin.default_assets.audio.handle import AudioClipHandle
            return AudioClipHandle.from_asset(asset)

        def data_to_asset(handle):
            if handle is not None:
                return handle.get_asset()
            return None

        def get_asset_class():
            from termin.default_assets.audio.asset import AudioClipAsset
            return AudioClipAsset

        return AssetRegistry(
            asset_class=get_asset_class,
            uuid_registry=self._assets_by_uuid,
            data_from_asset=data_from_asset,
            data_to_asset=data_to_asset,
        )

    def _create_ui_registry(self):
        """Create AssetRegistry for UI layouts."""
        from termin_assets import AssetRegistry

        def data_from_asset(asset):
            from termin.default_assets.ui.handle import UIHandle
            return UIHandle.from_asset(asset)

        def data_to_asset(handle):
            if handle is not None:
                return handle.get_asset()
            return None

        def get_asset_class():
            from termin.default_assets.ui.asset import UIAsset
            return UIAsset

        return AssetRegistry(
            asset_class=get_asset_class,
            uuid_registry=self._assets_by_uuid,
            data_from_asset=data_from_asset,
            data_to_asset=data_to_asset,
        )

    def _create_pipeline_registry(self):
        """Create AssetRegistry for render pipelines."""
        from termin_assets import AssetRegistry

        def data_from_asset(asset):
            if asset.pipeline is None:
                asset.ensure_loaded()
            return asset.pipeline

        def data_to_asset(data):
            for asset in self._pipeline_registry.assets.values():
                if asset.pipeline is data:
                    return asset
            return None

        def get_asset_class():
            from termin.default_assets.render.pipeline_asset import PipelineAsset
            return PipelineAsset

        return AssetRegistry(
            asset_class=get_asset_class,
            uuid_registry=self._assets_by_uuid,
            data_from_asset=data_from_asset,
            data_to_asset=data_to_asset,
        )

    def _create_scene_pipeline_registry(self):
        """Create AssetRegistry for scene pipelines (.scene_pipeline files)."""
        from termin_assets import AssetRegistry

        def data_from_asset(asset):
            if asset.pipeline is None:
                asset.ensure_loaded()
            return asset.pipeline

        def data_to_asset(data):
            for asset in self._scene_pipeline_registry.assets.values():
                if asset.pipeline is data:
                    return asset
            return None

        def get_asset_class():
            from termin.default_assets.render.scene_pipeline_asset import ScenePipelineAsset
            return ScenePipelineAsset

        return AssetRegistry(
            asset_class=get_asset_class,
            uuid_registry=self._assets_by_uuid,
            data_from_asset=data_from_asset,
            data_to_asset=data_to_asset,
        )
