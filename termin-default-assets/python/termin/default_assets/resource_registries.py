"""AssetRegistry factories for default Termin asset types."""

from __future__ import annotations


class DefaultAssetRegistryFactoryMixin:
    """Create runtime registries for asset types owned by default-assets.

    The host resource manager provides the canonical ``_asset_store`` and stores registry
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
            for asset in self._prefab_registry.iter_assets():
                if asset is data:
                    return asset
            return None

        def get_asset_class():
            from termin.prefab.asset import PrefabAsset
            return PrefabAsset

        return AssetRegistry(
            asset_class=get_asset_class,
            asset_store=self._asset_store,
            data_from_asset=data_from_asset,
            data_to_asset=data_to_asset,
        )

    def _create_glb_registry(self):
        """Create AssetRegistry for GLB model assets."""
        from termin_assets import AssetRegistry

        def data_from_asset(asset):
            return asset

        def data_to_asset(data):
            for asset in self._glb_registry.iter_assets():
                if asset is data:
                    return asset
            return None

        def get_asset_class():
            from termin.glb.asset import GLBAsset
            return GLBAsset

        return AssetRegistry(
            asset_class=get_asset_class,
            asset_store=self._asset_store,
            data_from_asset=data_from_asset,
            data_to_asset=data_to_asset,
        )

    def _create_material_registry(self):
        """Create AssetRegistry for materials."""
        from termin_assets import AssetRegistry
        from termin.materials import TcMaterial

        def data_from_asset(asset):
            if asset.material is None:
                asset.ensure_loaded()
            material = TcMaterial.from_uuid(asset.uuid)
            return material if material.is_valid else None

        def data_to_asset(data):
            if not isinstance(data, TcMaterial) or not data.is_valid:
                return None
            for asset in self._material_registry.iter_assets():
                if asset.uuid == data.uuid:
                    return asset
            return None

        def get_asset_class():
            from termin.default_assets.render.material_asset import MaterialAsset
            return MaterialAsset

        return AssetRegistry(
            asset_class=get_asset_class,
            asset_store=self._asset_store,
            data_from_asset=data_from_asset,
            data_to_asset=data_to_asset,
        )

    def _create_shader_registry(self):
        """Create AssetRegistry for shader programs."""
        from termin_assets import AssetRegistry
        from tgfx import TcShaderProgram

        def data_from_asset(asset):
            if asset.program is None:
                asset.ensure_loaded()
            return asset.program

        def data_to_asset(data):
            if not isinstance(data, TcShaderProgram) or not data.is_valid:
                return None
            for asset in self._shader_registry.iter_assets():
                if asset.uuid == data.uuid:
                    return asset
            return None

        def get_asset_class():
            from termin.default_assets.render.shader_asset import ShaderAsset
            return ShaderAsset

        return AssetRegistry(
            asset_class=get_asset_class,
            asset_store=self._asset_store,
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
            for asset in self._mesh_registry.iter_assets():
                if asset.mesh_data is not None and asset.mesh_data.uuid == mesh.uuid:
                    return asset
            return None

        return AssetRegistry[MeshAsset, TcMesh](
            asset_class=MeshAsset,
            asset_store=self._asset_store,
            data_from_asset=data_from_asset,
            data_to_asset=data_to_asset,
        )

    def _create_texture_registry(self):
        """Create AssetRegistry for textures."""
        from termin_assets import AssetRegistry
        from termin.default_assets.render.texture_asset import TextureAsset
        from tgfx import TcTexture

        def data_from_asset(asset: TextureAsset) -> TcTexture | None:
            texture = TcTexture.from_uuid(asset.uuid)
            if texture.is_valid:
                return texture
            if asset.texture_data is None:
                asset.ensure_loaded()
            return asset.texture_data

        def data_to_asset(texture: TcTexture) -> TextureAsset | None:
            if texture is None or not texture.is_valid:
                return None
            for asset in self._texture_registry.iter_assets():
                if asset.uuid == texture.uuid:
                    return asset
            return None

        return AssetRegistry[TextureAsset, TcTexture](
            asset_class=TextureAsset,
            asset_store=self._asset_store,
            data_from_asset=data_from_asset,
            data_to_asset=data_to_asset,
        )

    def _create_voxel_grid_registry(self):
        """Create AssetRegistry for voxel grids."""
        from termin_assets import AssetRegistry
        from termin.voxels._voxels_native import TcVoxelGrid

        def data_from_asset(asset):
            return TcVoxelGrid.from_uuid(asset.uuid)

        def data_to_asset(data: TcVoxelGrid):
            if not isinstance(data, TcVoxelGrid) or not data.is_valid:
                return None
            for asset in self._voxel_grid_registry.iter_assets():
                if asset.uuid == data.uuid:
                    return asset
            return None

        def get_asset_class():
            from termin.default_assets.voxels.asset import VoxelGridAsset
            return VoxelGridAsset

        return AssetRegistry(
            asset_class=get_asset_class,
            asset_store=self._asset_store,
            data_from_asset=data_from_asset,
            data_to_asset=data_to_asset,
        )

    def _create_navmesh_registry(self):
        """Create AssetRegistry for navmeshes."""
        from termin_assets import AssetRegistry
        from termin.navmesh._navmesh_native import TcNavMesh

        def data_from_asset(asset):
            return TcNavMesh.from_uuid(asset.uuid)

        def data_to_asset(data: TcNavMesh):
            if not isinstance(data, TcNavMesh) or not data.is_valid:
                return None
            for asset in self._navmesh_registry.iter_assets():
                if asset.uuid == data.uuid:
                    return asset
            return None

        def get_asset_class():
            from termin.default_assets.navmesh.asset import NavMeshAsset
            return NavMeshAsset

        return AssetRegistry(
            asset_class=get_asset_class,
            asset_store=self._asset_store,
            data_from_asset=data_from_asset,
            data_to_asset=data_to_asset,
        )

    def _create_animation_clip_registry(self):
        """Create AssetRegistry for animation clips."""
        from termin_assets import AssetRegistry
        from termin.animation import TcAnimationClip

        def data_from_asset(asset):
            clip = asset.clip
            if clip is None:
                asset.ensure_loaded()
            clip = TcAnimationClip.from_uuid(asset.uuid)
            return clip if clip.is_valid else None

        def data_to_asset(data):
            if not isinstance(data, TcAnimationClip) or not data.is_valid:
                return None
            for asset in self._animation_clip_registry.iter_assets():
                if asset.uuid == data.uuid:
                    return asset
            return None

        def get_asset_class():
            from termin.animation.asset import AnimationClipAsset
            return AnimationClipAsset

        return AssetRegistry(
            asset_class=get_asset_class,
            asset_store=self._asset_store,
            data_from_asset=data_from_asset,
            data_to_asset=data_to_asset,
        )

    def _create_skeleton_registry(self):
        """Create AssetRegistry for skeletons."""
        from termin_assets import AssetRegistry
        from termin.skeleton import TcSkeleton

        def data_from_asset(asset):
            if asset.skeleton_data is None:
                asset.ensure_loaded()
            skeleton = TcSkeleton.from_uuid(asset.uuid)
            return skeleton if skeleton.is_valid else None

        def data_to_asset(data):
            if not isinstance(data, TcSkeleton) or not data.is_valid:
                return None
            for asset in self._skeleton_registry.iter_assets():
                if asset.uuid == data.uuid:
                    return asset
            return None

        def get_asset_class():
            from termin.skeleton.asset import SkeletonAsset
            return SkeletonAsset

        return AssetRegistry(
            asset_class=get_asset_class,
            asset_store=self._asset_store,
            data_from_asset=data_from_asset,
            data_to_asset=data_to_asset,
        )

    def _create_audio_clip_registry(self):
        """Create AssetRegistry for audio clips."""
        from termin_assets import AssetRegistry
        from termin.audio import TcAudioClip

        def data_from_asset(asset):
            return asset.clip

        def data_to_asset(clip):
            if not isinstance(clip, TcAudioClip) or not clip.is_valid:
                return None
            for asset in self._audio_clip_registry.iter_assets():
                if asset.uuid == clip.uuid:
                    return asset
            return None

        def get_asset_class():
            from termin.default_assets.audio.asset import AudioClipAsset
            return AudioClipAsset

        return AssetRegistry(
            asset_class=get_asset_class,
            asset_store=self._asset_store,
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
            asset_store=self._asset_store,
            data_from_asset=data_from_asset,
            data_to_asset=data_to_asset,
        )

    def _create_pipeline_registry(self):
        """Create AssetRegistry for render pipelines."""
        from termin_assets import AssetRegistry

        def data_from_asset(asset):
            return asset.canonical_resource

        def data_to_asset(data):
            data_uuid = data.uuid if data is not None else None
            for asset in self._pipeline_registry.iter_assets():
                resource = asset.cached_data
                if resource is data or (data_uuid and resource is not None and resource.uuid == data_uuid):
                    return asset
            return None

        def get_asset_class():
            from termin.default_assets.render.pipeline_asset import PipelineAsset
            return PipelineAsset

        return AssetRegistry(
            asset_class=get_asset_class,
            asset_store=self._asset_store,
            data_from_asset=data_from_asset,
            data_to_asset=data_to_asset,
        )
