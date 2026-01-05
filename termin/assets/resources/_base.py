"""Base ResourceManager with core initialization and registries."""

from __future__ import annotations

from typing import Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from termin.visualization.core.material import Material
    from termin.assets.material_asset import MaterialAsset
    from termin.assets.mesh_asset import MeshAsset
    from termin.assets.texture_asset import TextureAsset
    from termin.visualization.render.shader_parser import ShaderMultyPhaseProgramm
    from termin.assets.shader_asset import ShaderAsset
    from termin.voxels.grid import VoxelGrid
    from termin.assets.voxel_grid_asset import VoxelGridAsset
    from termin.navmesh.types import NavMesh
    from termin.assets.navmesh_asset import NavMeshAsset
    from termin.visualization.animation.clip import AnimationClip
    from termin.assets.animation_clip_asset import AnimationClipAsset
    from termin.skeleton import SkeletonData
    from termin.assets.skeleton_asset import SkeletonAsset
    from termin.assets.prefab_asset import PrefabAsset
    from termin.assets.glb_asset import GLBAsset
    from termin.assets.audio_clip_asset import AudioClipAsset
    from termin.visualization.core.entity import Component


class ResourceManagerBase:
    """Base class with core initialization and registry setup."""

    _instance: "ResourceManagerBase | None" = None

    def __init__(self):
        self.materials: Dict[str, "Material"] = {}
        self.shaders: Dict[str, "ShaderMultyPhaseProgramm"] = {}
        self.voxel_grids: Dict[str, "VoxelGrid"] = {}
        self.navmeshes: Dict[str, "NavMesh"] = {}
        self.animation_clips: Dict[str, "AnimationClip"] = {}
        self.skeletons: Dict[str, "SkeletonData"] = {}
        self.components: Dict[str, type["Component"]] = {}
        self.frame_passes: Dict[str, type] = {}
        self.post_effects: Dict[str, type] = {}

        # Assets by UUID (for lookup during loading)
        from termin.assets.asset import Asset
        self._assets_by_uuid: Dict[str, Asset] = {}

        # Asset registries
        self._mesh_registry = self._create_mesh_registry()
        self._texture_registry = self._create_texture_registry()
        self._voxel_grid_registry = self._create_voxel_grid_registry()
        self._navmesh_registry = self._create_navmesh_registry()
        self._animation_clip_registry = self._create_animation_clip_registry()
        self._skeleton_registry = self._create_skeleton_registry()
        self._glsl_registry = self._create_glsl_registry()
        self._audio_clip_registry = self._create_audio_clip_registry()
        self._ui_registry = self._create_ui_registry()
        self._pipeline_registry = self._create_pipeline_registry()

        # Legacy dicts (for types without registry)
        self._material_assets: Dict[str, "MaterialAsset"] = {}
        self._shader_assets: Dict[str, "ShaderAsset"] = {}
        self._glb_assets: Dict[str, "GLBAsset"] = {}
        self._prefab_assets: Dict[str, "PrefabAsset"] = {}

    def _create_mesh_registry(self):
        """Create AssetRegistry for meshes."""
        from termin.assets.asset_registry import AssetRegistry
        from termin.assets.mesh_asset import MeshAsset
        from termin.mesh import TcMesh

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
        from termin.assets.asset_registry import AssetRegistry
        from termin.assets.texture_asset import TextureAsset
        from termin.assets.texture_handle import TextureHandle

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
        from termin.assets.asset_registry import AssetRegistry

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
            from termin.assets.voxel_grid_asset import VoxelGridAsset
            return VoxelGridAsset

        return AssetRegistry(
            asset_class=get_asset_class,
            uuid_registry=self._assets_by_uuid,
            data_from_asset=data_from_asset,
            data_to_asset=data_to_asset,
        )

    def _create_navmesh_registry(self):
        """Create AssetRegistry for navmeshes."""
        from termin.assets.asset_registry import AssetRegistry

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
            from termin.assets.navmesh_asset import NavMeshAsset
            return NavMeshAsset

        return AssetRegistry(
            asset_class=get_asset_class,
            uuid_registry=self._assets_by_uuid,
            data_from_asset=data_from_asset,
            data_to_asset=data_to_asset,
        )

    def _create_animation_clip_registry(self):
        """Create AssetRegistry for animation clips."""
        from termin.assets.asset_registry import AssetRegistry

        def data_from_asset(asset):
            return asset.clip

        def data_to_asset(data):
            for asset in self._animation_clip_registry.assets.values():
                if asset.clip is data:
                    return asset
            return None

        def get_asset_class():
            from termin.assets.animation_clip_asset import AnimationClipAsset
            return AnimationClipAsset

        return AssetRegistry(
            asset_class=get_asset_class,
            uuid_registry=self._assets_by_uuid,
            data_from_asset=data_from_asset,
            data_to_asset=data_to_asset,
        )

    def _create_skeleton_registry(self):
        """Create AssetRegistry for skeletons."""
        from termin.assets.asset_registry import AssetRegistry

        def data_from_asset(asset):
            if asset.skeleton_data is None:
                asset.ensure_loaded()
            return asset.skeleton_data

        def data_to_asset(data):
            for asset in self._skeleton_registry.assets.values():
                if asset.skeleton_data is data:
                    return asset
            return None

        def get_asset_class():
            from termin.assets.skeleton_asset import SkeletonAsset
            return SkeletonAsset

        return AssetRegistry(
            asset_class=get_asset_class,
            uuid_registry=self._assets_by_uuid,
            data_from_asset=data_from_asset,
            data_to_asset=data_to_asset,
        )

    def _create_glsl_registry(self):
        """Create AssetRegistry for GLSL include files."""
        from termin.assets.asset_registry import AssetRegistry

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
            from termin.assets.glsl_asset import GlslAsset
            return GlslAsset

        return AssetRegistry(
            asset_class=get_asset_class,
            uuid_registry=self._assets_by_uuid,
            data_from_asset=data_from_asset,
            data_to_asset=data_to_asset,
        )

    def _create_audio_clip_registry(self):
        """Create AssetRegistry for audio clips."""
        from termin.assets.asset_registry import AssetRegistry

        def data_from_asset(asset):
            from termin.assets.audio_clip_handle import AudioClipHandle
            return AudioClipHandle.from_asset(asset)

        def data_to_asset(handle):
            if handle is not None:
                return handle.get_asset()
            return None

        def get_asset_class():
            from termin.assets.audio_clip_asset import AudioClipAsset
            return AudioClipAsset

        return AssetRegistry(
            asset_class=get_asset_class,
            uuid_registry=self._assets_by_uuid,
            data_from_asset=data_from_asset,
            data_to_asset=data_to_asset,
        )

    def _create_ui_registry(self):
        """Create AssetRegistry for UI layouts."""
        from termin.assets.asset_registry import AssetRegistry

        def data_from_asset(asset):
            from termin.assets.ui_handle import UIHandle
            return UIHandle.from_asset(asset)

        def data_to_asset(handle):
            if handle is not None:
                return handle.get_asset()
            return None

        def get_asset_class():
            from termin.assets.ui_asset import UIAsset
            return UIAsset

        return AssetRegistry(
            asset_class=get_asset_class,
            uuid_registry=self._assets_by_uuid,
            data_from_asset=data_from_asset,
            data_to_asset=data_to_asset,
        )

    def _create_pipeline_registry(self):
        """Create AssetRegistry for render pipelines."""
        from termin.assets.asset_registry import AssetRegistry

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
            from termin.assets.pipeline_asset import PipelineAsset
            return PipelineAsset

        return AssetRegistry(
            asset_class=get_asset_class,
            uuid_registry=self._assets_by_uuid,
            data_from_asset=data_from_asset,
            data_to_asset=data_to_asset,
        )

    # Legacy property accessors
    @property
    def _mesh_assets(self) -> Dict[str, "MeshAsset"]:
        """Legacy access to mesh assets dict."""
        return self._mesh_registry.assets

    @property
    def _texture_assets(self) -> Dict[str, "TextureAsset"]:
        """Legacy access to texture assets dict."""
        return self._texture_registry.assets

    @property
    def _voxel_grid_assets(self) -> Dict[str, "VoxelGridAsset"]:
        """Legacy access to voxel grid assets dict."""
        return self._voxel_grid_registry.assets

    @property
    def _navmesh_assets(self) -> Dict[str, "NavMeshAsset"]:
        """Legacy access to navmesh assets dict."""
        return self._navmesh_registry.assets

    @property
    def _animation_clip_assets(self) -> Dict[str, "AnimationClipAsset"]:
        """Legacy access to animation clip assets dict."""
        return self._animation_clip_registry.assets

    @property
    def _skeleton_assets(self) -> Dict[str, "SkeletonAsset"]:
        """Legacy access to skeleton assets dict."""
        return self._skeleton_registry.assets

    @property
    def _audio_clip_assets(self) -> Dict[str, "AudioClipAsset"]:
        """Legacy access to audio clip assets dict."""
        return self._audio_clip_registry.assets

    @property
    def _ui_assets(self):
        """Legacy access to UI assets dict."""
        return self._ui_registry.assets

    @property
    def glsl(self):
        """Access to GLSL include files registry."""
        return self._glsl_registry

    @classmethod
    def instance(cls) -> "ResourceManagerBase":
        if cls._instance is None:
            cls._instance = cls()
            from termin.assets.builtin_resources import register_all_builtins
            register_all_builtins(cls._instance)
        return cls._instance

    @classmethod
    def _reset_for_testing(cls) -> None:
        """Reset singleton instance. For testing only."""
        cls._instance = None
