"""Base ResourceManager with core initialization and registries."""

from __future__ import annotations

from typing import Dict, TYPE_CHECKING

from termin_assets import AssetRuntimeManager
from termin.default_assets.resource_registries import DefaultAssetRegistryFactoryMixin

if TYPE_CHECKING:
    from termin.materials import TcMaterial as Material
    from termin.default_assets.render.material_asset import MaterialAsset
    from termin.default_assets.mesh.asset import MeshAsset
    from termin.default_assets.render.texture_asset import TextureAsset
    from termin.materials import ShaderMultyPhaseProgramm
    from termin.default_assets.render.shader_asset import ShaderAsset
    from termin.voxels.grid import VoxelGrid
    from termin.default_assets.voxels.asset import VoxelGridAsset
    from termin.navmesh.types import NavMesh
    from termin.default_assets.navmesh.asset import NavMeshAsset
    from termin.animation import TcAnimationClip
    from termin.animation.asset import AnimationClipAsset
    from termin.skeleton import TcSkeleton
    from termin.skeleton.asset import SkeletonAsset
    from termin.prefab.asset import PrefabAsset
    from termin.glb.asset import GLBAsset
    from termin.default_assets.audio.asset import AudioClipAsset


class ResourceManagerBase(DefaultAssetRegistryFactoryMixin, AssetRuntimeManager):
    """Base class with core initialization and registry setup."""

    _instance: "ResourceManagerBase | None" = None

    def __init__(self):
        super().__init__()

        from termin.scene.component_registry import ComponentClassRegistry
        from termin.render_framework.frame_pass_registry import FramePassRegistry

        self.component_registry = ComponentClassRegistry()
        self.frame_pass_registry = FramePassRegistry()
        self.components = self.component_registry.classes
        self.frame_passes = self.frame_pass_registry.classes

        # Runtime caches for direct data objects. AssetRegistry remains the
        # authoritative asset storage; these preserve legacy fast paths.
        self.materials: Dict[str, "Material"] = {}
        self.shaders: Dict[str, "ShaderMultyPhaseProgramm"] = {}
        self.voxel_grids: Dict[str, "VoxelGrid"] = {}
        self.navmeshes: Dict[str, "NavMesh"] = {}
        self.animation_clips: Dict[str, "TcAnimationClip"] = {}
        self.skeletons: Dict[str, "TcSkeleton"] = {}

        # Asset registries
        self._prefab_registry = self._create_prefab_registry()
        self._glb_registry = self._create_glb_registry()
        self._material_registry = self._create_material_registry()
        self._shader_registry = self._create_shader_registry()
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

        for type_id, registry in {
            "prefab": self._prefab_registry,
            "glb": self._glb_registry,
            "material": self._material_registry,
            "shader": self._shader_registry,
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

    def _create_glb_registry(self):
        """Create AssetRegistry for GLB model assets."""
        from termin_assets import AssetRegistry

        def data_from_asset(asset):
            return asset

        def data_to_asset(data):
            for asset in self._glb_registry.assets.values():
                if asset is data:
                    return asset
            return None

        def get_asset_class():
            from termin.glb.asset import GLBAsset
            return GLBAsset

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

    # Legacy property accessors
    @property
    def _prefab_assets(self) -> Dict[str, "PrefabAsset"]:
        """Legacy access to prefab assets dict."""
        return self._prefab_registry.assets

    @property
    def _glb_assets(self) -> Dict[str, "GLBAsset"]:
        """Legacy access to GLB assets dict."""
        return self._glb_registry.assets

    @property
    def _material_assets(self) -> Dict[str, "MaterialAsset"]:
        """Legacy access to material assets dict."""
        return self._material_registry.assets

    @property
    def _shader_assets(self) -> Dict[str, "ShaderAsset"]:
        """Legacy access to shader assets dict."""
        return self._shader_registry.assets

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
            from termin_assets import set_resource_manager_factory
            set_resource_manager_factory(cls.instance)
            from termin.assets.builtin_resources import register_all_builtins
            register_all_builtins(cls._instance)
        return cls._instance

    @classmethod
    def _reset_for_testing(cls) -> None:
        """Reset singleton instance. For testing only."""
        cls._instance = None
        from termin_assets import set_resource_manager_factory
        set_resource_manager_factory(cls.instance)
