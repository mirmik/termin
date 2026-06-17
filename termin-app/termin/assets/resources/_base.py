"""Base ResourceManager with core initialization and registries."""

from __future__ import annotations

from typing import Dict, TYPE_CHECKING

from termin_assets import AssetRuntimeManager

if TYPE_CHECKING:
    from termin.materials import TcMaterial as Material
    from termin.assets.material_asset import MaterialAsset
    from termin.mesh.asset import MeshAsset
    from termin.render.texture_asset import TextureAsset
    from termin.materials import ShaderMultyPhaseProgramm
    from termin.assets.shader_asset import ShaderAsset
    from termin.voxels.grid import VoxelGrid
    from termin.voxels.asset import VoxelGridAsset
    from termin.navmesh.types import NavMesh
    from termin.navmesh.asset import NavMeshAsset
    from termin.animation import TcAnimationClip
    from termin.animation.asset import AnimationClipAsset
    from termin.skeleton import TcSkeleton
    from termin.skeleton.asset import SkeletonAsset
    from termin.assets.prefab_asset import PrefabAsset
    from termin.assets.glb_asset import GLBAsset
    from termin.audio.asset import AudioClipAsset


class ResourceManagerBase(AssetRuntimeManager):
    """Base class with core initialization and registry setup."""

    _instance: "ResourceManagerBase | None" = None

    def __init__(self):
        super().__init__()

        self.materials: Dict[str, "Material"] = {}
        self.shaders: Dict[str, "ShaderMultyPhaseProgramm"] = {}
        self.voxel_grids: Dict[str, "VoxelGrid"] = {}
        self.navmeshes: Dict[str, "NavMesh"] = {}
        self.animation_clips: Dict[str, "TcAnimationClip"] = {}
        self.skeletons: Dict[str, "TcSkeleton"] = {}
        from termin.scene.component_registry import ComponentClassRegistry
        from termin.render_framework.frame_pass_registry import FramePassRegistry

        self.component_registry = ComponentClassRegistry()
        self.frame_pass_registry = FramePassRegistry()
        self.components = self.component_registry.classes
        self.frame_passes = self.frame_pass_registry.classes

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
        self._scene_pipeline_registry = self._create_scene_pipeline_registry()

        # Legacy dicts (for types without registry)
        self._material_assets: Dict[str, "MaterialAsset"] = {}
        self._shader_assets: Dict[str, "ShaderAsset"] = {}
        self._glb_assets: Dict[str, "GLBAsset"] = {}
        self._prefab_assets: Dict[str, "PrefabAsset"] = {}

        for type_id, registry in {
            "mesh": self._mesh_registry,
            "texture": self._texture_registry,
            "voxel_grid": self._voxel_grid_registry,
            "navmesh": self._navmesh_registry,
            "animation_clip": self._animation_clip_registry,
            "skeleton": self._skeleton_registry,
            "glsl": self._glsl_registry,
            "audio_clip": self._audio_clip_registry,
            "ui": self._ui_registry,
            "pipeline": self._pipeline_registry,
            "scene_pipeline": self._scene_pipeline_registry,
        }.items():
            self.register_runtime_asset_registry(type_id, registry)

        self._register_builtin_asset_type_plugins()

    def _register_builtin_asset_type_plugins(self) -> None:
        """Register asset plugins that have already migrated off hard-coded dispatch."""
        self.register_default_asset_type_plugins()

    def _create_mesh_registry(self):
        """Create AssetRegistry for meshes."""
        from termin_assets import AssetRegistry
        from termin.mesh.asset import MeshAsset
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
        from termin.render.texture_asset import TextureAsset
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
            from termin.voxels.asset import VoxelGridAsset
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
            from termin.navmesh.asset import NavMeshAsset
            return NavMeshAsset

        return AssetRegistry(
            asset_class=get_asset_class,
            uuid_registry=self._assets_by_uuid,
            data_from_asset=data_from_asset,
            data_to_asset=data_to_asset,
        )

    def _create_animation_clip_registry(self):
        """Create AssetRegistry for animation clips."""
        from termin_assets import AssetRegistry

        def data_from_asset(asset):
            return asset.clip

        def data_to_asset(data):
            for asset in self._animation_clip_registry.assets.values():
                if asset.clip is data:
                    return asset
            return None

        def get_asset_class():
            from termin.animation.asset import AnimationClipAsset
            return AnimationClipAsset

        return AssetRegistry(
            asset_class=get_asset_class,
            uuid_registry=self._assets_by_uuid,
            data_from_asset=data_from_asset,
            data_to_asset=data_to_asset,
        )

    def _create_skeleton_registry(self):
        """Create AssetRegistry for skeletons."""
        from termin_assets import AssetRegistry

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
            from termin.skeleton.asset import SkeletonAsset
            return SkeletonAsset

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
            from termin.render.glsl_asset import GlslAsset
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
            from termin.audio.handle import AudioClipHandle
            return AudioClipHandle.from_asset(asset)

        def data_to_asset(handle):
            if handle is not None:
                return handle.get_asset()
            return None

        def get_asset_class():
            from termin.audio.asset import AudioClipAsset
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
            from termin.assets.pipeline_asset import PipelineAsset
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
            from termin.assets.scene_pipeline_asset import ScenePipelineAsset
            return ScenePipelineAsset

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
