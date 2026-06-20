"""Default Termin ResourceManager implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin_assets import AssetRuntimeManager

from termin.default_assets.resource_api import DefaultAssetResourceMixin
from termin.default_assets.resource_accessors import DefaultResourceAccessorsMixin
from termin.default_assets.resource_components import DefaultComponentsMixin
from termin.default_assets.resource_registries import DefaultAssetRegistryFactoryMixin
from termin.default_assets.resource_serialization import DefaultSerializationMixin

if TYPE_CHECKING:
    from termin.animation import TcAnimationClip
    from termin.animation.asset import AnimationClipAsset
    from termin.default_assets.audio.asset import AudioClipAsset
    from termin.default_assets.mesh.asset import MeshAsset
    from termin.default_assets.navmesh.asset import NavMeshAsset
    from termin.default_assets.render.material_asset import MaterialAsset
    from termin.default_assets.render.shader_asset import ShaderAsset
    from termin.default_assets.render.texture_asset import TextureAsset
    from termin.default_assets.voxels.asset import VoxelGridAsset
    from termin.glb.asset import GLBAsset
    from termin.materials import ShaderMultyPhaseProgramm
    from termin.materials import TcMaterial as Material
    from termin.navmesh._navmesh_native import TcNavMesh
    from termin.prefab.asset import PrefabAsset
    from termin.skeleton import TcSkeleton
    from termin.skeleton.asset import SkeletonAsset
    from termin.voxels._voxels_native import TcVoxelGrid


class DefaultResourceManagerBase(DefaultAssetRegistryFactoryMixin, AssetRuntimeManager):
    """Base class with default runtime registries and caches."""

    _instance: "DefaultResourceManagerBase | None" = None

    def __init__(self):
        super().__init__()

        from termin.render_framework.frame_pass_registry import FramePassRegistry
        from termin.scene.component_registry import ComponentClassRegistry

        self.component_registry = ComponentClassRegistry()
        self.frame_pass_registry = FramePassRegistry()
        self.components = self.component_registry.classes
        self.frame_passes = self.frame_pass_registry.classes

        # Runtime caches for direct data objects. AssetRegistry remains the
        # authoritative asset storage; these preserve legacy fast paths.
        self.materials: dict[str, "Material"] = {}
        self.shaders: dict[str, "ShaderMultyPhaseProgramm"] = {}
        self.voxel_grids: dict[str, "TcVoxelGrid"] = {}
        self.navmeshes: dict[str, "TcNavMesh"] = {}
        self.animation_clips: dict[str, "TcAnimationClip"] = {}
        self.skeletons: dict[str, "TcSkeleton"] = {}

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
        self.register_default_asset_type_plugins()

    @property
    def _prefab_assets(self) -> dict[str, "PrefabAsset"]:
        return self._prefab_registry.assets

    @property
    def _glb_assets(self) -> dict[str, "GLBAsset"]:
        return self._glb_registry.assets

    @property
    def _material_assets(self) -> dict[str, "MaterialAsset"]:
        return self._material_registry.assets

    @property
    def _shader_assets(self) -> dict[str, "ShaderAsset"]:
        return self._shader_registry.assets

    @property
    def _mesh_assets(self) -> dict[str, "MeshAsset"]:
        return self._mesh_registry.assets

    @property
    def _texture_assets(self) -> dict[str, "TextureAsset"]:
        return self._texture_registry.assets

    @property
    def _voxel_grid_assets(self) -> dict[str, "VoxelGridAsset"]:
        return self._voxel_grid_registry.assets

    @property
    def _navmesh_assets(self) -> dict[str, "NavMeshAsset"]:
        return self._navmesh_registry.assets

    @property
    def _animation_clip_assets(self) -> dict[str, "AnimationClipAsset"]:
        return self._animation_clip_registry.assets

    @property
    def _skeleton_assets(self) -> dict[str, "SkeletonAsset"]:
        return self._skeleton_registry.assets

    @property
    def _audio_clip_assets(self) -> dict[str, "AudioClipAsset"]:
        return self._audio_clip_registry.assets

    @property
    def _ui_assets(self):
        return self._ui_registry.assets

    @property
    def glsl(self):
        return self._glsl_registry

    @classmethod
    def instance(cls) -> "DefaultResourceManagerBase":
        if cls._instance is None:
            cls._instance = cls()
            from termin_assets import set_resource_manager_factory
            from termin.default_assets.builtin_resources import register_all_builtins

            set_resource_manager_factory(cls.instance)
            register_all_builtins(cls._instance)
        return cls._instance

    @classmethod
    def _reset_for_testing(cls) -> None:
        cls._instance = None
        from termin_assets import set_resource_manager_factory

        set_resource_manager_factory(cls.instance)


class DefaultResourceManager(
    DefaultResourceManagerBase,
    DefaultAssetResourceMixin,
    DefaultComponentsMixin,
    DefaultResourceAccessorsMixin,
    DefaultSerializationMixin,
):
    """Default asset runtime manager without editor-specific extensions."""

    pass


__all__ = ["DefaultResourceManager", "DefaultResourceManagerBase"]
