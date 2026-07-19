"""Default Termin ResourceManager implementation."""

from __future__ import annotations

import atexit
import sys
from typing import TYPE_CHECKING

from termin_assets import AssetRuntimeManager

from termin.default_assets.resource_api import DefaultAssetResourceMixin
from termin.default_assets.resource_accessors import DefaultResourceAccessorsMixin
from termin.default_assets.resource_components import DefaultComponentsMixin
from termin.default_assets.resource_registries import DefaultAssetRegistryFactoryMixin
from termin.default_assets.resource_serialization import DefaultSerializationMixin

if TYPE_CHECKING:
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
    from termin.prefab.asset import PrefabAsset
    from termin.skeleton.asset import SkeletonAsset


class DefaultResourceManagerBase(DefaultAssetRegistryFactoryMixin, AssetRuntimeManager):
    """Base class with default runtime registries and the parsed shader cache."""

    _instance: "DefaultResourceManagerBase | None" = None

    def __init__(self):
        super().__init__()

        from termin.render_framework.frame_pass_registry import FramePassRegistry
        from termin.scene.component_registry import ComponentClassRegistry

        self.component_registry = ComponentClassRegistry()
        self.frame_pass_registry = FramePassRegistry()
        self.components = self.component_registry.classes
        self.frame_passes = self.frame_pass_registry.classes

        # Parsed shader programs do not yet have a canonical Tc* registry.
        # Their ownership is tracked separately in #647.
        self.shaders: dict[str, "ShaderMultyPhaseProgramm"] = {}

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
        }.items():
            self.register_runtime_asset_registry(type_id, registry)

        self._register_builtin_asset_type_plugins()

    def _register_builtin_asset_type_plugins(self) -> None:
        self.register_default_asset_type_plugins()

    def unregister_runtime_asset(
        self,
        type_id: str,
        name: str,
        *,
        uuid: str | None = None,
    ):
        """Remove a runtime asset and its parsed shader cache entry."""
        removed = super().unregister_runtime_asset(type_id, name, uuid=uuid)
        removed_name = removed.name if removed is not None else name
        if type_id == "shader":
            self.shaders.pop(removed_name, None)
        return removed

    def unregister_runtime_asset_by_uuid(self, type_id: str, uuid: str):
        """Remove canonical UUID membership and synchronize the shader cache."""
        asset = self.get_runtime_asset_by_uuid(type_id, uuid)
        if asset is None:
            return None
        return self.unregister_runtime_asset(type_id, asset.name, uuid=uuid)

    def rename_runtime_asset(self, type_id: str, uuid: str, name: str) -> bool:
        asset = self.get_asset_by_uuid(uuid)
        old_name = asset.name if asset is not None else None
        renamed = super().rename_runtime_asset(type_id, uuid, name)
        if not renamed:
            return False
        if type_id != "shader":
            return True
        for candidate in (old_name, name):
            if candidate is None:
                continue
            self.shaders.pop(candidate, None)
        return True

    @property
    def _prefab_assets(self) -> dict[str, "PrefabAsset"]:
        return self._prefab_registry.unique_assets_by_name

    @property
    def _glb_assets(self) -> dict[str, "GLBAsset"]:
        return self._glb_registry.unique_assets_by_name

    @property
    def _material_assets(self) -> dict[str, "MaterialAsset"]:
        return self._material_registry.unique_assets_by_name

    @property
    def _shader_assets(self) -> dict[str, "ShaderAsset"]:
        return self._shader_registry.unique_assets_by_name

    @property
    def _mesh_assets(self) -> dict[str, "MeshAsset"]:
        return self._mesh_registry.unique_assets_by_name

    @property
    def _texture_assets(self) -> dict[str, "TextureAsset"]:
        return self._texture_registry.unique_assets_by_name

    @property
    def _voxel_grid_assets(self) -> dict[str, "VoxelGridAsset"]:
        return self._voxel_grid_registry.unique_assets_by_name

    @property
    def _navmesh_assets(self) -> dict[str, "NavMeshAsset"]:
        return self._navmesh_registry.unique_assets_by_name

    @property
    def _animation_clip_assets(self) -> dict[str, "AnimationClipAsset"]:
        return self._animation_clip_registry.unique_assets_by_name

    @property
    def _skeleton_assets(self) -> dict[str, "SkeletonAsset"]:
        return self._skeleton_registry.unique_assets_by_name

    @property
    def _audio_clip_assets(self) -> dict[str, "AudioClipAsset"]:
        return self._audio_clip_registry.unique_assets_by_name

    @property
    def _ui_assets(self):
        return self._ui_registry.unique_assets_by_name

    @property
    def glsl(self):
        return self._glsl_registry

    @classmethod
    def instance(cls) -> "DefaultResourceManagerBase":
        if cls._instance is None:
            cls._instance = cls()
            from termin_assets import set_resource_manager_factory

            set_resource_manager_factory(cls.instance)
        return cls._instance

    def clear_runtime_state(self) -> None:
        """Drop runtime asset registries and the parsed shader cache."""
        self._destroy_cached_pipelines()

        for registry in list(self._runtime_asset_registries.values()):
            registry.clear()
        self._asset_store.clear()
        self.external_assets.clear()

        self.shaders.clear()

        self.component_registry.classes.clear()
        self.frame_pass_registry.classes.clear()

        self._clear_default_texture_caches()

    def _destroy_cached_pipelines(self) -> None:
        for asset in list(self._pipeline_registry.iter_assets()):
            pipeline = asset.cached_data
            if pipeline is None:
                continue
            try:
                pipeline.destroy()
            except Exception:
                from tcbase import log

                log.error(
                    f"[DefaultResourceManager] Failed to destroy pipeline '{asset.name}'",
                    exc_info=True,
                )
            asset.unload()

    def _clear_default_texture_caches(self) -> None:
        texture_module = sys.modules.get("termin.render.texture")
        if texture_module is not None:
            texture_module._white_texture = None
            texture_module._normal_texture = None

        texture_handle_module = sys.modules.get("termin.render.texture_handle")
        if texture_handle_module is not None:
            texture_handle_module._white_texture_handle = None
            texture_handle_module._normal_texture_handle = None

    @classmethod
    def shutdown_instance(cls) -> None:
        """Clear and detach the process-wide default resource manager, if any."""
        instance = cls._instance
        if instance is None:
            return

        try:
            instance.clear_runtime_state()
        finally:
            cls._instance = None
            from termin_assets import set_resource_manager_factory

            set_resource_manager_factory(cls.instance)

    @classmethod
    def _reset_for_testing(cls) -> None:
        cls.shutdown_instance()
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


atexit.register(DefaultResourceManager.shutdown_instance)


__all__ = ["DefaultResourceManager", "DefaultResourceManagerBase"]
