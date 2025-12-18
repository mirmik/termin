# termin/visualization/resources.py
from __future__ import annotations

from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # только для типов, чтобы не ловить циклы импортов
    from termin.visualization.core.material import Material
    from termin.visualization.core.material_asset import MaterialAsset
    from termin.visualization.core.mesh_asset import MeshAsset
    from termin.visualization.core.mesh_handle import MeshHandle
    from termin.visualization.core.texture_handle import TextureHandle
    from termin.mesh.mesh import Mesh3
    from termin.visualization.core.glb_asset import GLBAsset
    from termin.visualization.core.entity import Component
    from termin.visualization.render.texture import Texture
    from termin.visualization.render.texture_asset import TextureAsset
    from termin.visualization.render.shader_parser import ShaderMultyPhaseProgramm
    from termin.visualization.render.shader_asset import ShaderAsset
    from termin.voxels.grid import VoxelGrid
    from termin.voxels.voxel_grid_asset import VoxelGridAsset
    from termin.navmesh.types import NavMesh
    from termin.navmesh.navmesh_asset import NavMeshAsset
    from termin.visualization.animation.clip import AnimationClip
    from termin.visualization.animation.animation_clip_asset import AnimationClipAsset
    from termin.skeleton.skeleton import SkeletonData
    from termin.skeleton.skeleton_asset import SkeletonAsset


# Список стандартных компонентов для предрегистрации.
# Формат: (имя_модуля, имя_класса)
_BUILTIN_COMPONENTS: List[Tuple[str, str]] = [
    # Рендеринг
    ("termin.visualization.render.components.mesh_renderer", "MeshRenderer"),
    ("termin.visualization.render.components.skinned_mesh_renderer", "SkinnedMeshRenderer"),
    ("termin.visualization.render.components.line_renderer", "LineRenderer"),
    ("termin.visualization.render.components.light_component", "LightComponent"),
    # Камера
    ("termin.visualization.core.camera", "CameraComponent"),
    ("termin.visualization.core.camera", "CameraController"),
    # Анимация
    ("termin.visualization.animation.player", "AnimationPlayer"),
    ("termin.visualization.components.rotator", "RotatorComponent"),
    # Физика
    ("termin.physics.physics_world_component", "PhysicsWorldComponent"),
    ("termin.physics.rigid_body_component", "RigidBodyComponent"),
    # Коллайдеры
    ("termin.colliders.collider_component", "ColliderComponent"),
    # Воксели
    ("termin.voxels.voxelizer_component", "VoxelizerComponent"),
    ("termin.voxels.display_component", "VoxelDisplayComponent"),
    # NavMesh
    ("termin.navmesh.display_component", "NavMeshDisplayComponent"),
]

# Список встроенных FramePass'ов для предрегистрации.
# Формат: (имя_модуля, имя_класса)
_BUILTIN_FRAME_PASSES: List[Tuple[str, str]] = [
    # Основные пассы
    ("termin.visualization.render.framegraph.passes.color", "ColorPass"),
    ("termin.visualization.render.framegraph.passes.skybox", "SkyBoxPass"),
    ("termin.visualization.render.framegraph.passes.depth", "DepthPass"),
    ("termin.visualization.render.framegraph.passes.shadow", "ShadowPass"),
    ("termin.visualization.render.framegraph.passes.canvas", "CanvasPass"),
    ("termin.visualization.render.framegraph.passes.present", "PresentToScreenPass"),
    ("termin.visualization.render.framegraph.passes.present", "BlitPass"),
    # ID/Picking
    ("termin.visualization.render.framegraph.passes.id_pass", "IdPass"),
    ("termin.visualization.render.framegraph.passes.gizmo", "GizmoPass"),
    # Post-processing
    ("termin.visualization.render.postprocess", "PostProcessPass"),
    # Debug
    ("termin.visualization.render.framegraph.passes.frame_debugger", "FrameDebuggerPass"),
]

# Список встроенных PostEffect'ов для предрегистрации.
# Формат: (имя_модуля, имя_класса)
_BUILTIN_POST_EFFECTS: List[Tuple[str, str]] = [
    ("termin.visualization.render.posteffects.blur", "GaussianBlurPass"),
    ("termin.visualization.render.posteffects.highlight", "HighlightEffect"),
    ("termin.visualization.render.posteffects.fog", "FogEffect"),
    ("termin.visualization.render.posteffects.gray", "GrayscaleEffect"),
]

# Фиксированные UUID для встроенных ресурсов.
# Гарантируют стабильные ссылки между сессиями.
from termin.visualization.core.builtin_resources import BUILTIN_UUIDS


class ResourceManager:
    """
    Глобальный менеджер ресурсов редактора.
    """

    _instance: "ResourceManager | None" = None
    _creating_singleton: bool = False

    def __init__(self):
        if not ResourceManager._creating_singleton:
            raise RuntimeError(
                "ResourceManager is a singleton. Use ResourceManager.instance() instead of ResourceManager()."
            )

        self.materials: Dict[str, "Material"] = {}
        self.shaders: Dict[str, "ShaderMultyPhaseProgramm"] = {}
        self.voxel_grids: Dict[str, "VoxelGrid"] = {}  # VoxelGrid instances by name
        self.navmeshes: Dict[str, "NavMesh"] = {}  # NavMesh instances by name
        self.animation_clips: Dict[str, "AnimationClip"] = {}  # AnimationClip instances by name
        self.skeletons: Dict[str, "SkeletonData"] = {}  # SkeletonData instances by name
        self.components: Dict[str, type["Component"]] = {}
        self.frame_passes: Dict[str, type] = {}  # FramePass classes by name
        self.post_effects: Dict[str, type] = {}  # PostEffect classes by name
        self.pipelines: Dict[str, "RenderPipeline"] = {}  # RenderPipeline instances by name

        # Asset'ы по UUID (для поиска существующих при загрузке)
        from termin.visualization.core.asset import Asset
        self._assets_by_uuid: Dict[str, Asset] = {}

        # Asset registries
        self._mesh_registry = self._create_mesh_registry()
        self._texture_registry = self._create_texture_registry()
        self._voxel_grid_registry = self._create_voxel_grid_registry()
        self._navmesh_registry = self._create_navmesh_registry()
        self._animation_clip_registry = self._create_animation_clip_registry()
        self._skeleton_registry = self._create_skeleton_registry()
        self._glsl_registry = self._create_glsl_registry()

        # Legacy dicts (для обратной совместимости и типов без registry)
        self._material_assets: Dict[str, "MaterialAsset"] = {}
        self._shader_assets: Dict[str, "ShaderAsset"] = {}
        self._glb_assets: Dict[str, "GLBAsset"] = {}

    def _create_mesh_registry(self):
        """Create AssetRegistry for meshes."""
        from termin.visualization.core.asset_registry import AssetRegistry
        from termin.visualization.core.mesh_asset import MeshAsset
        from termin.visualization.core.mesh_handle import MeshHandle

        def data_from_asset(asset: MeshAsset) -> MeshHandle:
            return MeshHandle.from_asset(asset)

        def data_to_asset(handle: MeshHandle) -> MeshAsset | None:
            return handle.get_asset()

        return AssetRegistry[MeshAsset, MeshHandle](
            asset_class=MeshAsset,
            uuid_registry=self._assets_by_uuid,
            data_from_asset=data_from_asset,
            data_to_asset=data_to_asset,
        )

    def _create_texture_registry(self):
        """Create AssetRegistry for textures."""
        from termin.visualization.core.asset_registry import AssetRegistry
        from termin.visualization.render.texture_asset import TextureAsset
        from termin.visualization.core.texture_handle import TextureHandle

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
        from termin.visualization.core.asset_registry import AssetRegistry

        def data_from_asset(asset):
            # Lazy load if not loaded
            if asset.grid is None:
                asset.load()
            return asset.grid

        def data_to_asset(data):
            # Search through assets
            for asset in self._voxel_grid_registry.assets.values():
                if asset.grid is data:
                    return asset
            return None

        # Import asset class lazily to avoid circular imports
        def get_asset_class():
            from termin.voxels.voxel_grid_asset import VoxelGridAsset
            return VoxelGridAsset

        return AssetRegistry(
            asset_class=get_asset_class,
            uuid_registry=self._assets_by_uuid,
            data_from_asset=data_from_asset,
            data_to_asset=data_to_asset,
        )

    def _create_navmesh_registry(self):
        """Create AssetRegistry for navmeshes."""
        from termin.visualization.core.asset_registry import AssetRegistry

        def data_from_asset(asset):
            # Lazy load if not loaded
            if asset.navmesh is None:
                asset.load()
            return asset.navmesh

        def data_to_asset(data):
            # Search through assets
            for asset in self._navmesh_registry.assets.values():
                if asset.navmesh is data:
                    return asset
            return None

        # Import asset class lazily to avoid circular imports
        def get_asset_class():
            from termin.navmesh.navmesh_asset import NavMeshAsset
            return NavMeshAsset

        return AssetRegistry(
            asset_class=get_asset_class,
            uuid_registry=self._assets_by_uuid,
            data_from_asset=data_from_asset,
            data_to_asset=data_to_asset,
        )

    def _create_animation_clip_registry(self):
        """Create AssetRegistry for animation clips."""
        from termin.visualization.core.asset_registry import AssetRegistry

        def data_from_asset(asset):
            return asset.clip

        def data_to_asset(data):
            # Search through assets
            for asset in self._animation_clip_registry.assets.values():
                if asset.clip is data:
                    return asset
            return None

        # Import asset class lazily to avoid circular imports
        def get_asset_class():
            from termin.visualization.animation.animation_clip_asset import AnimationClipAsset
            return AnimationClipAsset

        return AssetRegistry(
            asset_class=get_asset_class,
            uuid_registry=self._assets_by_uuid,
            data_from_asset=data_from_asset,
            data_to_asset=data_to_asset,
        )

    def _create_skeleton_registry(self):
        """Create AssetRegistry for skeletons."""
        from termin.visualization.core.asset_registry import AssetRegistry

        def data_from_asset(asset):
            # Lazy load if not loaded
            if asset.skeleton_data is None:
                asset.load()
            return asset.skeleton_data

        def data_to_asset(data):
            # Search through assets
            for asset in self._skeleton_registry.assets.values():
                if asset.skeleton_data is data:
                    return asset
            return None

        # Import asset class lazily to avoid circular imports
        def get_asset_class():
            from termin.skeleton.skeleton_asset import SkeletonAsset
            return SkeletonAsset

        return AssetRegistry(
            asset_class=get_asset_class,
            uuid_registry=self._assets_by_uuid,
            data_from_asset=data_from_asset,
            data_to_asset=data_to_asset,
        )

    def _create_glsl_registry(self):
        """Create AssetRegistry for GLSL include files."""
        from termin.visualization.core.asset_registry import AssetRegistry

        def data_from_asset(asset):
            # Lazy load if not loaded
            if asset.source is None:
                asset.load()
            return asset.source

        def data_to_asset(data):
            # Search through assets
            for asset in self._glsl_registry.assets.values():
                if asset.source is data:
                    return asset
            return None

        # Import asset class lazily to avoid circular imports
        def get_asset_class():
            from termin.visualization.render.glsl_asset import GlslAsset
            return GlslAsset

        return AssetRegistry(
            asset_class=get_asset_class,
            uuid_registry=self._assets_by_uuid,
            data_from_asset=data_from_asset,
            data_to_asset=data_to_asset,
        )

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
    def glsl(self):
        """Access to GLSL include files registry."""
        return self._glsl_registry

    @classmethod
    def instance(cls) -> "ResourceManager":
        if cls._instance is None:
            cls._creating_singleton = True
            try:
                cls._instance = cls()
            finally:
                cls._creating_singleton = False
        return cls._instance

    @classmethod
    def _reset_for_testing(cls) -> None:
        """Reset singleton instance. For testing only."""
        cls._instance = None

    # --------- PreLoadResult-based registration ---------

    def register_file(self, result: "PreLoadResult") -> None:
        """
        Register a file from PreLoadResult.

        If UUID exists and is registered → uses existing Asset.
        Otherwise → creates new Asset.
        Then calls Asset.load() with content from result.
        """
        from termin.editor.project_file_watcher import PreLoadResult
        import os

        name = os.path.splitext(os.path.basename(result.path))[0]

        # Dispatch by resource type
        if result.resource_type == "material":
            self._register_material_file(name, result)
        elif result.resource_type == "shader":
            self._register_shader_file(name, result)
        elif result.resource_type == "texture":
            self._register_texture_file(name, result)
        elif result.resource_type == "mesh":
            self._register_mesh_file(name, result)
        elif result.resource_type == "voxel_grid":
            self._register_voxel_grid_file(name, result)
        elif result.resource_type == "navmesh":
            self._register_navmesh_file(name, result)
        elif result.resource_type == "glb":
            self._register_glb_file(name, result)
        elif result.resource_type == "glsl":
            self._register_glsl_file(name, result)
        else:
            print(f"[ResourceManager] Unknown resource type: {result.resource_type}")

    def reload_file(self, result: "PreLoadResult") -> None:
        """
        Reload a file from PreLoadResult.

        Finds existing Asset and calls load() with new content.
        """
        import os

        name = os.path.splitext(os.path.basename(result.path))[0]

        if result.resource_type == "material":
            self._reload_material_file(name, result)
        elif result.resource_type == "shader":
            self._reload_shader_file(name, result)
        elif result.resource_type == "texture":
            self._reload_texture_file(name, result)
        elif result.resource_type == "mesh":
            self._reload_mesh_file(name, result)
        elif result.resource_type == "voxel_grid":
            self._reload_voxel_grid_file(name, result)
        elif result.resource_type == "navmesh":
            self._reload_navmesh_file(name, result)
        elif result.resource_type == "glb":
            self._reload_glb_file(name, result)
        elif result.resource_type == "glsl":
            self._reload_glsl_file(name, result)
        else:
            print(f"[ResourceManager] Unknown resource type for reload: {result.resource_type}")

    def _register_material_file(self, name: str, result: "PreLoadResult") -> None:
        """Register material from PreLoadResult."""
        from termin.visualization.core.material_asset import MaterialAsset

        # Check if already registered by name
        if name in self._material_assets:
            return

        # Try to find existing Asset by UUID
        asset = None
        if result.uuid:
            asset = self._assets_by_uuid.get(result.uuid)
            if asset is not None and not isinstance(asset, MaterialAsset):
                # UUID collision with different asset type - ignore
                asset = None

        # Create new Asset if not found
        if asset is None:
            asset = MaterialAsset(
                material=None,
                name=name,
                source_path=result.path,
                uuid=result.uuid,  # May be None - will auto-generate
            )
            # Register in UUID registry
            self._assets_by_uuid[asset.uuid] = asset

        # Register by name
        self._material_assets[name] = asset

        # Load content (Asset parses it)
        asset.load_from_content(result.content)

        # Update legacy dict
        if asset.material is not None:
            self.materials[name] = asset.material


    def _reload_material_file(self, name: str, result: "PreLoadResult") -> None:
        """Reload material from PreLoadResult."""
        asset = self._material_assets.get(name)
        if asset is None:
            return

        # Skip if this was our own save
        if not asset.should_reload_from_file():
            return

        # Reload from file
        asset.load()

        # Update legacy dict
        if asset.material is not None:
            self.materials[name] = asset.material


    def _register_shader_file(self, name: str, result: "PreLoadResult") -> None:
        """Register shader from PreLoadResult (lazy loading)."""
        from termin.visualization.render.shader_asset import ShaderAsset

        # Check if already registered by name
        if name in self._shader_assets:
            return

        # Try to find existing Asset by UUID
        asset = None
        if result.uuid:
            asset = self._assets_by_uuid.get(result.uuid)
            if asset is not None and not isinstance(asset, ShaderAsset):
                asset = None

        # Create new Asset if not found
        if asset is None:
            asset = ShaderAsset(
                program=None,
                name=name,
                source_path=result.path,
            )

        # Parse spec to set UUID and any type-specific settings
        asset.parse_spec(result.spec_data)
        self._assets_by_uuid[asset.uuid] = asset

        # Register by name (lazy loading - don't load content yet)
        self._shader_assets[name] = asset

    def _reload_shader_file(self, name: str, result: "PreLoadResult") -> None:
        """Reload shader from PreLoadResult."""
        asset = self._shader_assets.get(name)
        if asset is None:
            return

        # Skip if this was our own save
        if not asset.should_reload_from_file():
            return

        # Parse spec for any updated settings, then reload
        asset.parse_spec(result.spec_data)
        asset.load()

        # Update legacy dict
        if asset.program is not None:
            self.shaders[name] = asset.program

    def _register_texture_file(self, name: str, result: "PreLoadResult") -> None:
        """Register texture from PreLoadResult (lazy loading)."""
        from termin.visualization.render.texture_asset import TextureAsset

        # Check if already registered by name
        if name in self._texture_assets:
            return

        # Try to find existing Asset by UUID
        asset = None
        if result.uuid:
            asset = self._assets_by_uuid.get(result.uuid)
            if asset is not None and not isinstance(asset, TextureAsset):
                asset = None

        # Create new Asset if not found
        if asset is None:
            asset = TextureAsset(
                texture_data=None,
                name=name,
                source_path=result.path,
            )

        # Parse spec to set UUID and texture settings (flip_x, flip_y, etc.)
        asset.parse_spec(result.spec_data)
        self._assets_by_uuid[asset.uuid] = asset

        # Register by name (lazy loading - don't load content yet)
        self._texture_assets[name] = asset

    def _reload_texture_file(self, name: str, result: "PreLoadResult") -> None:
        """Reload texture from PreLoadResult."""
        asset = self._texture_assets.get(name)
        if asset is None:
            return

        # Skip if this was our own save
        if not asset.should_reload_from_file():
            return

        # Parse spec for any updated settings, then reload
        asset.parse_spec(result.spec_data)
        asset.load()

        # Invalidate GPU texture to force re-upload
        asset.delete_gpu()

    def _register_mesh_file(self, name: str, result: "PreLoadResult") -> None:
        """Register mesh from PreLoadResult."""
        from termin.visualization.core.mesh_asset import MeshAsset

        # Check if already registered by name
        if name in self._mesh_assets:
            return

        # Try to find existing Asset by UUID
        asset = None
        if result.uuid:
            asset = self._assets_by_uuid.get(result.uuid)
            if asset is not None and not isinstance(asset, MeshAsset):
                asset = None

        # Create new Asset if not found
        if asset is None:
            asset = MeshAsset(
                mesh_data=None,
                name=name,
                source_path=result.path,
            )

        # Parse spec to set UUID and mesh settings (scale, axis, etc.)
        asset.parse_spec(result.spec_data)
        self._assets_by_uuid[asset.uuid] = asset

        # Register by name (lazy loading - don't load content yet)
        self._mesh_assets[name] = asset

    def _reload_mesh_file(self, name: str, result: "PreLoadResult") -> None:
        """Reload mesh from PreLoadResult."""
        asset = self._mesh_assets.get(name)
        if asset is None:
            return

        # Skip if this was our own save
        if not asset.should_reload_from_file():
            return

        # Parse spec for any updated settings, then reload
        asset.parse_spec(result.spec_data)
        asset.load()

        # Invalidate GPU mesh to force re-upload
        asset.delete_gpu()

    def _register_voxel_grid_file(self, name: str, result: "PreLoadResult") -> None:
        """Register voxel grid from PreLoadResult."""
        from termin.voxels.voxel_grid_asset import VoxelGridAsset

        # Check if already registered by name
        if name in self._voxel_grid_assets:
            return

        # Try to find existing Asset by UUID
        asset = None
        if result.uuid:
            asset = self._assets_by_uuid.get(result.uuid)
            if asset is not None and not isinstance(asset, VoxelGridAsset):
                asset = None

        # Create new Asset if not found
        if asset is None:
            asset = VoxelGridAsset(
                grid=None,
                name=name,
                source_path=result.path,
            )

        # Parse spec to set UUID
        asset.parse_spec(result.spec_data)
        self._assets_by_uuid[asset.uuid] = asset

        # Register by name (lazy loading - don't load content yet)
        self._voxel_grid_assets[name] = asset

    def _reload_voxel_grid_file(self, name: str, result: "PreLoadResult") -> None:
        """Reload voxel grid from PreLoadResult."""
        asset = self._voxel_grid_assets.get(name)
        if asset is None:
            return

        # Skip if this was our own save
        if not asset.should_reload_from_file():
            return

        # Parse spec for any updated settings, then reload
        asset.parse_spec(result.spec_data)
        asset.load()

        # Update legacy dict
        if asset.grid is not None:
            self.voxel_grids[name] = asset.grid

    def _register_navmesh_file(self, name: str, result: "PreLoadResult") -> None:
        """Register navmesh from PreLoadResult."""
        from termin.navmesh.navmesh_asset import NavMeshAsset

        # Check if already registered by name
        if name in self._navmesh_assets:
            return

        # Try to find existing Asset by UUID
        asset = None
        if result.uuid:
            asset = self._assets_by_uuid.get(result.uuid)
            if asset is not None and not isinstance(asset, NavMeshAsset):
                asset = None

        # Create new Asset if not found
        if asset is None:
            asset = NavMeshAsset(
                navmesh=None,
                name=name,
                source_path=result.path,
            )

        # Parse spec to set UUID
        asset.parse_spec(result.spec_data)
        self._assets_by_uuid[asset.uuid] = asset

        # Register by name (lazy loading - don't load content yet)
        self._navmesh_assets[name] = asset

    def _reload_navmesh_file(self, name: str, result: "PreLoadResult") -> None:
        """Reload navmesh from PreLoadResult."""
        asset = self._navmesh_assets.get(name)
        if asset is None:
            return

        # Skip if this was our own save
        if not asset.should_reload_from_file():
            return

        # Parse spec for any updated settings, then reload
        asset.parse_spec(result.spec_data)
        asset.load()

        # Update legacy dict
        if asset.navmesh is not None:
            self.navmeshes[name] = asset.navmesh

    def _register_glb_file(self, name: str, result: "PreLoadResult") -> None:
        """Register GLB from PreLoadResult."""
        from termin.visualization.core.glb_asset import GLBAsset

        # Check if already registered by name
        if name in self._glb_assets:
            return

        # Try to find existing Asset by UUID
        asset = None
        if result.uuid:
            asset = self._assets_by_uuid.get(result.uuid)
            if asset is not None and not isinstance(asset, GLBAsset):
                asset = None

        # Create new Asset if not found
        if asset is None:
            asset = GLBAsset(
                scene_data=None,
                name=name,
                source_path=result.path,
            )

        # Parse spec to set UUID, settings, and CREATE CHILD ASSETS
        asset.parse_spec(result.spec_data)
        self._assets_by_uuid[asset.uuid] = asset

        # Register by name (lazy loading - don't load content yet)
        self._glb_assets[name] = asset

        # Register child assets created during spec parsing
        self._register_glb_child_assets(asset)

    def _register_glb_child_assets(self, glb_asset: "GLBAsset") -> None:
        """Register child assets from GLBAsset (meshes, skeletons, animations)."""
        # Register mesh assets
        for mesh_name, mesh_asset in glb_asset.get_mesh_assets().items():
            full_name = mesh_asset.name
            if full_name not in self._mesh_assets:
                self._mesh_assets[full_name] = mesh_asset
                self._assets_by_uuid[mesh_asset.uuid] = mesh_asset

        # Register skeleton assets
        for skeleton_key, skeleton_asset in glb_asset.get_skeleton_assets().items():
            skeleton_name = skeleton_asset.name
            if skeleton_name not in self._skeleton_assets:
                self._skeleton_assets[skeleton_name] = skeleton_asset
                self._assets_by_uuid[skeleton_asset.uuid] = skeleton_asset

        # Register animation clip assets
        for anim_name, anim_asset in glb_asset.get_animation_assets().items():
            full_name = anim_asset.name
            if full_name not in self._animation_clip_assets:
                self._animation_clip_assets[full_name] = anim_asset
                self._assets_by_uuid[anim_asset.uuid] = anim_asset

    def _reload_glb_file(self, name: str, result: "PreLoadResult") -> None:
        """Reload GLB from PreLoadResult."""
        asset = self._glb_assets.get(name)
        if asset is None:
            return

        # Skip if this was our own save
        if not asset.should_reload_from_file():
            return

        # Parse spec for any updated settings, then reload
        asset.parse_spec(result.spec_data)
        asset.load()

        # Re-register child assets (may have new ones after reload)
        self._register_glb_child_assets(asset)

    def _register_glsl_file(self, name: str, result: "PreLoadResult") -> None:
        """Register GLSL include file from PreLoadResult."""
        from termin.visualization.render.glsl_asset import GlslAsset

        # Check if UUID already registered
        uuid = result.spec_data.get("uuid") if result.spec_data else None
        if uuid and uuid in self._assets_by_uuid:
            asset = self._assets_by_uuid[uuid]
            if isinstance(asset, GlslAsset):
                # Update name registration
                self._glsl_registry.assets[name] = asset
                asset.parse_spec(result.spec_data)
                return

        # Create new asset
        asset = self._glsl_registry.get_or_create_asset(
            name=name,
            source_path=result.path,
            uuid=uuid,
        )
        asset.parse_spec(result.spec_data)

    def _reload_glsl_file(self, name: str, result: "PreLoadResult") -> None:
        """Reload GLSL include file from PreLoadResult."""
        asset = self._glsl_registry.get_asset(name)
        if asset is None:
            return

        # Skip if this was our own save
        if not asset.should_reload_from_file():
            return

        # Reload content
        asset.parse_spec(result.spec_data)
        asset.reload()

    def get_glsl(self, name: str) -> Optional[str]:
        """Get GLSL source by include name."""
        return self._glsl_registry.get(name)

    def get_glb_asset(self, name: str) -> Optional["GLBAsset"]:
        """Get GLBAsset by name."""
        return self._glb_assets.get(name)

    def get_asset_by_uuid(self, uuid: str) -> Optional["Asset"]:
        """Get any Asset by UUID."""
        from termin.visualization.core.asset import Asset
        return self._assets_by_uuid.get(uuid)

    # --------- Материалы (Asset-based) ---------
    def get_material_asset(self, name: str) -> Optional["MaterialAsset"]:
        """Получить MaterialAsset по имени."""
        return self._material_assets.get(name)

    def register_material(
        self, name: str, mat: "Material", source_path: str | None = None, uuid: str | None = None
    ):
        """Регистрирует материал."""
        from termin.visualization.core.material_asset import MaterialAsset

        asset = MaterialAsset.from_material(mat, name=name, source_path=source_path, uuid=uuid)
        self._material_assets[name] = asset
        self._assets_by_uuid[asset.uuid] = asset
        # Для обратной совместимости
        self.materials[name] = mat

    def get_material(self, name: str) -> Optional["Material"]:
        """Получить материал по имени (lazy loading)."""
        # Check legacy dict first
        mat = self.materials.get(name)
        if mat is not None:
            return mat

        # Try lazy loading from asset
        asset = self._material_assets.get(name)
        if asset is None:
            return None

        # Trigger lazy load if not loaded
        if asset.material is None:
            if not asset.load():
                return None

        # Cache in legacy dict
        if asset.material is not None:
            self.materials[name] = asset.material

        return asset.material

    def list_material_names(self) -> list[str]:
        names = set(self._material_assets.keys()) | set(self.materials.keys())
        return sorted(names)

    def find_material_name(self, mat: "Material") -> Optional[str]:
        for name, asset in self._material_assets.items():
            if asset.material is mat:
                return name
        for n, m in self.materials.items():
            if m is mat:
                return n
        return None

    def find_material_uuid(self, mat: "Material") -> Optional[str]:
        """Find UUID of a Material by looking up its asset."""
        for asset in self._material_assets.values():
            if asset.material is mat:
                return asset.uuid
        return None

    def get_material_by_uuid(self, uuid: str) -> Optional["Material"]:
        """Get Material by UUID (lazy loading)."""
        from termin.visualization.core.material_asset import MaterialAsset

        asset = self._assets_by_uuid.get(uuid)
        if asset is None or not isinstance(asset, MaterialAsset):
            return None

        # Trigger lazy load if not loaded
        if asset.material is None:
            if not asset.load():
                return None

        # Cache in legacy dict
        if asset.material is not None and asset.name:
            self.materials[asset.name] = asset.material

        return asset.material

    def get_material_asset_by_uuid(self, uuid: str) -> Optional["MaterialAsset"]:
        """Get MaterialAsset by UUID."""
        from termin.visualization.core.material_asset import MaterialAsset

        asset = self._assets_by_uuid.get(uuid)
        if asset is not None and isinstance(asset, MaterialAsset):
            return asset
        return None

    # --------- Шейдеры (Asset-based) ---------
    def get_shader_asset(self, name: str) -> Optional["ShaderAsset"]:
        """Получить ShaderAsset по имени."""
        return self._shader_assets.get(name)

    def register_shader(
        self, name: str, shader: "ShaderMultyPhaseProgramm", source_path: str | None = None, uuid: str | None = None
    ):
        """Регистрирует шейдер."""
        from termin.visualization.render.shader_asset import ShaderAsset

        asset = ShaderAsset.from_program(shader, name=name, source_path=source_path, uuid=uuid)
        self._shader_assets[name] = asset
        self._assets_by_uuid[asset.uuid] = asset
        # Для обратной совместимости
        self.shaders[name] = shader
        if source_path:
            shader.source_path = source_path

    def get_shader(self, name: str) -> Optional["ShaderMultyPhaseProgramm"]:
        """Получить шейдер по имени (lazy loading)."""
        # Check legacy dict first
        shader = self.shaders.get(name)
        if shader is not None:
            return shader

        # Try lazy loading from asset
        asset = self._shader_assets.get(name)
        if asset is None:
            return None

        # Trigger lazy load if not loaded
        if asset.program is None:
            if not asset.load():
                return None

        # Cache in legacy dict
        if asset.program is not None:
            self.shaders[name] = asset.program

        return asset.program

    def list_shader_names(self) -> list[str]:
        names = set(self._shader_assets.keys()) | set(self.shaders.keys())
        return sorted(names)

    def register_default_shader(self) -> None:
        """Регистрирует встроенный DefaultShader."""
        from termin.visualization.core.builtin_resources import register_default_shader
        register_default_shader(self)

    def register_pbr_shader(self) -> None:
        """Регистрирует встроенный PBR шейдер."""
        from termin.visualization.core.builtin_resources import register_pbr_shader
        register_pbr_shader(self)

    def register_advanced_pbr_shader(self) -> None:
        """Регистрирует встроенный Advanced PBR шейдер с SSS и ACES."""
        from termin.visualization.core.builtin_resources import register_advanced_pbr_shader
        register_advanced_pbr_shader(self)

    def register_skinned_shader(self) -> None:
        """Регистрирует встроенный SkinnedShader для скелетной анимации."""
        from termin.visualization.core.builtin_resources import register_skinned_shader
        register_skinned_shader(self)

    def register_builtin_materials(self) -> None:
        """Регистрирует встроенные материалы."""
        from termin.visualization.core.builtin_resources import register_builtin_materials
        register_builtin_materials(self)

    def register_builtin_meshes(self) -> List[str]:
        """Регистрирует встроенные примитивные меши."""
        from termin.visualization.core.builtin_resources import register_builtin_meshes
        return register_builtin_meshes(self)

    # --------- Меши (Asset-based via registry) ---------
    def get_mesh_asset(self, name: str) -> Optional["MeshAsset"]:
        """Получить MeshAsset по имени."""
        return self._mesh_registry.get_asset(name)

    def register_mesh_asset(
        self, name: str, asset: "MeshAsset", source_path: str | None = None, uuid: str | None = None
    ) -> None:
        """Регистрирует MeshAsset."""
        self._mesh_registry.register(name, asset, source_path, uuid)

    def get_mesh(self, name: str) -> Optional["MeshHandle"]:
        """Получить MeshHandle по имени."""
        return self._mesh_registry.get(name)

    def list_mesh_names(self) -> list[str]:
        return self._mesh_registry.list_names()

    def find_mesh_name(self, handle: "MeshHandle") -> Optional[str]:
        """Найти имя меша по MeshHandle."""
        if handle is None:
            return None
        name = self._mesh_registry.find_name(handle)
        if name:
            return name
        # Fallback: try by name from handle
        if handle.name and handle.name in self._mesh_assets:
            return handle.name
        return None

    def find_mesh_uuid(self, handle: "MeshHandle") -> Optional[str]:
        """Найти UUID меша по MeshHandle."""
        if handle is None:
            return None
        return self._mesh_registry.find_uuid(handle)

    def get_mesh_by_uuid(self, uuid: str) -> Optional["MeshHandle"]:
        """Получить MeshHandle по UUID."""
        return self._mesh_registry.get_by_uuid(uuid)

    def get_mesh_asset_by_uuid(self, uuid: str) -> Optional["MeshAsset"]:
        """Get MeshAsset by UUID."""
        return self._mesh_registry.get_asset_by_uuid(uuid)

    def get_or_create_mesh_asset(
        self,
        name: str,
        source_path: str | None = None,
        uuid: str | None = None,
        parent: "Asset | None" = None,
        parent_key: str | None = None,
    ) -> "MeshAsset":
        """Get MeshAsset by name, creating it if it doesn't exist."""
        return self._mesh_registry.get_or_create_asset(
            name=name,
            source_path=source_path,
            uuid=uuid,
            parent=parent,
            parent_key=parent_key,
        )

    def unregister_mesh(self, name: str) -> None:
        """Удаляет меш."""
        self._mesh_registry.unregister(name)

    # --------- Воксельные сетки (Asset-based via registry) ---------
    def get_voxel_grid_asset(self, name: str) -> Optional["VoxelGridAsset"]:
        """Получить VoxelGridAsset по имени."""
        return self._voxel_grid_registry.get_asset(name)

    def register_voxel_grid(self, name: str, grid: "VoxelGrid", source_path: str | None = None) -> None:
        """Регистрирует воксельную сетку."""
        from termin.voxels.voxel_grid_asset import VoxelGridAsset

        grid.name = name
        asset = VoxelGridAsset.from_grid(grid, name=name, source_path=source_path)
        self._voxel_grid_registry.register(name, asset, source_path)
        self.voxel_grids[name] = grid

    def get_voxel_grid(self, name: str) -> Optional["VoxelGrid"]:
        """Получить воксельную сетку по имени (lazy loading)."""
        grid = self.voxel_grids.get(name)
        if grid is not None:
            return grid
        grid = self._voxel_grid_registry.get(name)
        if grid is not None:
            self.voxel_grids[name] = grid
        return grid

    def list_voxel_grid_names(self) -> list[str]:
        """Список имён всех воксельных сеток."""
        return self._voxel_grid_registry.list_names()

    def find_voxel_grid_name(self, grid: "VoxelGrid") -> Optional[str]:
        """Найти имя воксельной сетки."""
        return self._voxel_grid_registry.find_name(grid)

    def find_voxel_grid_uuid(self, grid: "VoxelGrid") -> Optional[str]:
        """Find UUID of a VoxelGrid."""
        return self._voxel_grid_registry.find_uuid(grid)

    def get_voxel_grid_by_uuid(self, uuid: str) -> Optional["VoxelGrid"]:
        """Get VoxelGrid by UUID (lazy loading)."""
        grid = self._voxel_grid_registry.get_by_uuid(uuid)
        if grid is not None:
            asset = self._voxel_grid_registry.get_asset_by_uuid(uuid)
            if asset is not None and asset.name:
                self.voxel_grids[asset.name] = grid
        return grid

    def get_voxel_grid_asset_by_uuid(self, uuid: str) -> Optional["VoxelGridAsset"]:
        """Get VoxelGridAsset by UUID."""
        return self._voxel_grid_registry.get_asset_by_uuid(uuid)

    def unregister_voxel_grid(self, name: str) -> None:
        """Удаляет воксельную сетку."""
        self._voxel_grid_registry.unregister(name)
        if name in self.voxel_grids:
            del self.voxel_grids[name]

    # --------- Навигационные сетки (Asset-based via registry) ---------
    def get_navmesh_asset(self, name: str) -> Optional["NavMeshAsset"]:
        """Получить NavMeshAsset по имени."""
        return self._navmesh_registry.get_asset(name)

    def register_navmesh(self, name: str, navmesh: "NavMesh", source_path: str | None = None) -> None:
        """Регистрирует NavMesh."""
        from termin.navmesh.navmesh_asset import NavMeshAsset

        navmesh.name = name
        asset = NavMeshAsset.from_navmesh(navmesh, name=name, source_path=source_path)
        self._navmesh_registry.register(name, asset, source_path)
        self.navmeshes[name] = navmesh

    def get_navmesh(self, name: str) -> Optional["NavMesh"]:
        """Получить NavMesh по имени (lazy loading)."""
        navmesh = self.navmeshes.get(name)
        if navmesh is not None:
            return navmesh
        navmesh = self._navmesh_registry.get(name)
        if navmesh is not None:
            self.navmeshes[name] = navmesh
        return navmesh

    def list_navmesh_names(self) -> list[str]:
        """Список имён всех NavMesh."""
        return self._navmesh_registry.list_names()

    def find_navmesh_name(self, navmesh: "NavMesh") -> Optional[str]:
        """Найти имя NavMesh."""
        return self._navmesh_registry.find_name(navmesh)

    def find_navmesh_uuid(self, navmesh: "NavMesh") -> Optional[str]:
        """Find UUID of a NavMesh."""
        return self._navmesh_registry.find_uuid(navmesh)

    def get_navmesh_by_uuid(self, uuid: str) -> Optional["NavMesh"]:
        """Get NavMesh by UUID (lazy loading)."""
        navmesh = self._navmesh_registry.get_by_uuid(uuid)
        if navmesh is not None:
            asset = self._navmesh_registry.get_asset_by_uuid(uuid)
            if asset is not None and asset.name:
                self.navmeshes[asset.name] = navmesh
        return navmesh

    def get_navmesh_asset_by_uuid(self, uuid: str) -> Optional["NavMeshAsset"]:
        """Get NavMeshAsset by UUID."""
        return self._navmesh_registry.get_asset_by_uuid(uuid)

    def unregister_navmesh(self, name: str) -> None:
        """Удаляет NavMesh."""
        self._navmesh_registry.unregister(name)
        if name in self.navmeshes:
            del self.navmeshes[name]

    # --------- Анимационные клипы (Asset-based via registry) ---------
    def get_animation_clip_asset(self, name: str) -> Optional["AnimationClipAsset"]:
        """Получить AnimationClipAsset по имени."""
        return self._animation_clip_registry.get_asset(name)

    def register_animation_clip(
        self, name: str, clip: "AnimationClip", source_path: str | None = None, uuid: str | None = None
    ) -> None:
        """Регистрирует AnimationClip."""
        from termin.visualization.animation.animation_clip_asset import AnimationClipAsset

        clip.name = name
        asset = AnimationClipAsset(clip=clip, name=name, source_path=source_path, uuid=uuid)
        self._animation_clip_registry.register(name, asset, source_path, uuid)
        self.animation_clips[name] = clip

    def get_animation_clip(self, name: str) -> Optional["AnimationClip"]:
        """Получить AnimationClip по имени."""
        clip = self.animation_clips.get(name)
        if clip is not None:
            return clip
        return self._animation_clip_registry.get(name)

    def get_animation_clip_asset_by_uuid(self, uuid: str) -> Optional["AnimationClipAsset"]:
        """Получить AnimationClipAsset по UUID."""
        return self._animation_clip_registry.get_asset_by_uuid(uuid)

    def get_or_create_animation_clip_asset(
        self,
        name: str,
        source_path: str | None = None,
        uuid: str | None = None,
        parent: "Asset | None" = None,
        parent_key: str | None = None,
    ) -> "AnimationClipAsset":
        """Get AnimationClipAsset by name, creating it if it doesn't exist."""
        return self._animation_clip_registry.get_or_create_asset(
            name=name,
            source_path=source_path,
            uuid=uuid,
            parent=parent,
            parent_key=parent_key,
        )

    def list_animation_clip_names(self) -> list[str]:
        """Список имён всех AnimationClip."""
        return self._animation_clip_registry.list_names()

    def find_animation_clip_name(self, clip: "AnimationClip") -> Optional[str]:
        """Найти имя AnimationClip."""
        return self._animation_clip_registry.find_name(clip)

    def unregister_animation_clip(self, name: str) -> None:
        """Удаляет AnimationClip."""
        self._animation_clip_registry.unregister(name)
        if name in self.animation_clips:
            del self.animation_clips[name]

    # --------- Скелеты (Asset-based via registry) ---------
    def get_skeleton_asset(self, name: str) -> Optional["SkeletonAsset"]:
        """Получить SkeletonAsset по имени."""
        return self._skeleton_registry.get_asset(name)

    def register_skeleton(
        self, name: str, skeleton: "SkeletonData", source_path: str | None = None, uuid: str | None = None
    ) -> None:
        """Регистрирует скелет."""
        from termin.skeleton.skeleton_asset import SkeletonAsset

        asset = SkeletonAsset.from_skeleton_data(skeleton, name=name, source_path=source_path, uuid=uuid)
        self._skeleton_registry.register(name, asset, source_path, uuid)
        self.skeletons[name] = skeleton

    def get_skeleton(self, name: str) -> Optional["SkeletonData"]:
        """Получить SkeletonData по имени (lazy loading)."""
        skeleton = self.skeletons.get(name)
        if skeleton is not None:
            return skeleton
        skeleton = self._skeleton_registry.get(name)
        if skeleton is not None:
            self.skeletons[name] = skeleton
        return skeleton

    def list_skeleton_names(self) -> list[str]:
        """Список имён всех скелетов."""
        return self._skeleton_registry.list_names()

    def find_skeleton_name(self, skeleton: "SkeletonData") -> Optional[str]:
        """Найти имя скелета."""
        return self._skeleton_registry.find_name(skeleton)

    def find_skeleton_uuid(self, skeleton: "SkeletonData") -> Optional[str]:
        """Find UUID of a SkeletonData."""
        return self._skeleton_registry.find_uuid(skeleton)

    def get_skeleton_by_uuid(self, uuid: str) -> Optional["SkeletonData"]:
        """Get SkeletonData by UUID (lazy loading)."""
        skeleton = self._skeleton_registry.get_by_uuid(uuid)
        if skeleton is not None:
            asset = self._skeleton_registry.get_asset_by_uuid(uuid)
            if asset is not None and asset.name:
                self.skeletons[asset.name] = skeleton
        return skeleton

    def get_skeleton_asset_by_uuid(self, uuid: str) -> Optional["SkeletonAsset"]:
        """Get SkeletonAsset by UUID."""
        return self._skeleton_registry.get_asset_by_uuid(uuid)

    def get_or_create_skeleton_asset(
        self,
        name: str,
        source_path: str | None = None,
        uuid: str | None = None,
        parent: "Asset | None" = None,
        parent_key: str | None = None,
    ) -> "SkeletonAsset":
        """Get SkeletonAsset by name, creating it if it doesn't exist."""
        return self._skeleton_registry.get_or_create_asset(
            name=name,
            source_path=source_path,
            uuid=uuid,
            parent=parent,
            parent_key=parent_key,
        )

    def unregister_skeleton(self, name: str) -> None:
        """Удаляет скелет."""
        self._skeleton_registry.unregister(name)
        if name in self.skeletons:
            del self.skeletons[name]

    # --------- Текстуры (Asset-based via registry) ---------
    def get_texture_asset(self, name: str) -> Optional["TextureAsset"]:
        """Получить TextureAsset по имени."""
        return self._texture_registry.get_asset(name)

    def get_texture_handle(self, name: str) -> Optional["TextureHandle"]:
        """Получить TextureHandle по имени."""
        return self._texture_registry.get(name)

    def get_texture(self, name: str) -> Optional["Texture"]:
        """Получить Texture по имени (для inspector UI)."""
        from termin.visualization.render.texture import Texture

        asset = self._texture_registry.get_asset(name)
        if asset is not None:
            return Texture.from_asset(asset)
        return None

    def register_texture_asset(
        self,
        name: str,
        asset: "TextureAsset",
        source_path: str | None = None,
        uuid: str | None = None,
    ) -> None:
        """Register TextureAsset."""
        self._texture_registry.register(name, asset, source_path, uuid)

    def list_texture_names(self) -> list[str]:
        """List all registered texture names."""
        return self._texture_registry.list_names()

    def find_texture_name(self, texture: "TextureAsset | TextureHandle") -> Optional[str]:
        """Find name for a TextureAsset or TextureHandle."""
        from termin.visualization.core.texture_handle import TextureHandle

        # Extract asset if given TextureHandle
        if isinstance(texture, TextureHandle):
            return self._texture_registry.find_name(texture)
        else:
            # Direct asset lookup
            for n, a in self._texture_assets.items():
                if a is texture:
                    return n
        return None

    def unregister_texture(self, name: str) -> None:
        """Remove texture by name."""
        self._texture_registry.unregister(name)

    # --------- Компоненты ---------
    def register_component(self, name: str, cls: type["Component"]):
        self.components[name] = cls

    def get_component(self, name: str) -> Optional[type["Component"]]:
        return self.components.get(name)

    def list_component_names(self) -> list[str]:
        return sorted(self.components.keys())

    def register_builtin_components(self) -> List[str]:
        """
        Регистрирует все встроенные компоненты из _BUILTIN_COMPONENTS.

        Вызывается при инициализации редактора, чтобы гарантировать
        доступность стандартных компонентов независимо от порядка импортов.

        Returns:
            Список имён успешно зарегистрированных компонентов.
        """
        import importlib

        registered = []

        for module_name, class_name in _BUILTIN_COMPONENTS:
            if class_name in self.components:
                # Уже зарегистрирован (например, через __init_subclass__)
                registered.append(class_name)
                continue

            try:
                module = importlib.import_module(module_name)
                cls = getattr(module, class_name, None)
                if cls is not None:
                    self.components[class_name] = cls
                    registered.append(class_name)
            except Exception as e:
                print(f"Warning: Failed to register component {class_name} from {module_name}: {e}")

        return registered

    def scan_components(self, paths: list[str]) -> list[str]:
        """
        Сканирует директории/модули/файлы и загружает все Component подклассы.

        Args:
            paths: Список путей к директориям, .py файлам или имён модулей.

        Returns:
            Список имён загруженных компонентов.
        """
        from termin.visualization.core.plugin_loader import scan_paths
        return scan_paths(paths, self.components, "_dynamic_components_")

    # --------- FramePass'ы ---------
    def register_frame_pass(self, name: str, cls: type):
        """Регистрирует класс FramePass по имени."""
        self.frame_passes[name] = cls

    def get_frame_pass(self, name: str) -> Optional[type]:
        """Получить класс FramePass по имени."""
        return self.frame_passes.get(name)

    def list_frame_pass_names(self) -> list[str]:
        """Список имён всех зарегистрированных FramePass'ов."""
        return sorted(self.frame_passes.keys())

    def register_builtin_frame_passes(self) -> List[str]:
        """
        Регистрирует все встроенные FramePass'ы из _BUILTIN_FRAME_PASSES.

        Returns:
            Список имён успешно зарегистрированных FramePass'ов.
        """
        import importlib

        registered = []

        for module_name, class_name in _BUILTIN_FRAME_PASSES:
            if class_name in self.frame_passes:
                registered.append(class_name)
                continue

            try:
                module = importlib.import_module(module_name)
                cls = getattr(module, class_name, None)
                if cls is not None:
                    self.frame_passes[class_name] = cls
                    registered.append(class_name)
            except Exception as e:
                print(f"Warning: Failed to register frame pass {class_name} from {module_name}: {e}")

        return registered

    def scan_frame_passes(self, paths: list[str]) -> list[str]:
        """
        Сканирует директории/модули/файлы и загружает все FramePass подклассы.

        Args:
            paths: Список путей к директориям, .py файлам или имён модулей.

        Returns:
            Список имён загруженных FramePass'ов.
        """
        from termin.visualization.core.plugin_loader import scan_for_subclasses
        from termin.visualization.render.framegraph.core import FramePass
        return scan_for_subclasses(paths, FramePass, self.frame_passes, "_dynamic_frame_passes_")

    # --------- PostEffect'ы ---------
    def register_post_effect(self, name: str, cls: type):
        """Регистрирует класс PostEffect по имени."""
        self.post_effects[name] = cls

    def get_post_effect(self, name: str) -> Optional[type]:
        """Получить класс PostEffect по имени."""
        return self.post_effects.get(name)

    def list_post_effect_names(self) -> list[str]:
        """Список имён всех зарегистрированных PostEffect'ов."""
        return sorted(self.post_effects.keys())

    def register_builtin_post_effects(self) -> List[str]:
        """
        Регистрирует все встроенные PostEffect'ы из _BUILTIN_POST_EFFECTS.

        Returns:
            Список имён успешно зарегистрированных PostEffect'ов.
        """
        import importlib

        registered = []

        for module_name, class_name in _BUILTIN_POST_EFFECTS:
            if class_name in self.post_effects:
                registered.append(class_name)
                continue

            try:
                module = importlib.import_module(module_name)
                cls = getattr(module, class_name, None)
                if cls is not None:
                    self.post_effects[class_name] = cls
                    registered.append(class_name)
            except Exception as e:
                print(f"Warning: Failed to register post effect {class_name} from {module_name}: {e}")

        return registered

    # --------- Pipelines ---------
    def register_pipeline(self, name: str, pipeline: "RenderPipeline"):
        """Регистрирует RenderPipeline по имени."""
        self.pipelines[name] = pipeline

    def get_pipeline(self, name: str) -> Optional["RenderPipeline"]:
        """Получить RenderPipeline по имени."""
        return self.pipelines.get(name)

    def list_pipeline_names(self) -> list[str]:
        """Список имён всех зарегистрированных пайплайнов."""
        return sorted(self.pipelines.keys())

    # --------- Сериализация ---------

    def serialize(self) -> dict:
        """
        Сериализует все ресурсы ResourceManager.

        Материалы и меши не сериализуются — они загружаются из файлов проекта.
        """
        return {
            "textures": {name: self._serialize_texture_asset(asset) for name, asset in self._texture_assets.items()},
        }

    def _serialize_texture_asset(self, asset: "TextureAsset") -> dict:
        """Сериализует TextureAsset."""
        source_path = str(asset.source_path) if asset.source_path else None
        if source_path:
            return {"type": "file", "source_path": source_path}
        return {"type": "unknown"}

    @classmethod
    def deserialize(cls, data: dict, context=None) -> "ResourceManager":
        """
        Восстанавливает ресурсы из сериализованных данных в синглтон.

        Добавляет десериализованные ресурсы к существующему синглтону.
        Меши и материалы загружаются из файлов проекта, не из сцены.
        """
        return cls.instance()
