# termin/visualization/resources.py
from __future__ import annotations

from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # только для типов, чтобы не ловить циклы импортов
    from termin.visualization.core.material import Material
    from termin.visualization.core.material_asset import MaterialAsset
    from termin.visualization.core.mesh_asset import MeshAsset
    from termin.visualization.core.mesh_handle import MeshHandle
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
_BUILTIN_UUIDS: Dict[str, str] = {
    # Шейдеры
    "DefaultShader": "00000000-0000-0000-0001-000000000001",
    "PBRShader": "00000000-0000-0000-0001-000000000002",
    "AdvancedPBRShader": "00000000-0000-0000-0001-000000000003",
    "SkinnedShader": "00000000-0000-0000-0001-000000000004",
    # Материалы
    "DefaultMaterial": "00000000-0000-0000-0002-000000000001",
    "PBRMaterial": "00000000-0000-0000-0002-000000000002",
    "AdvancedPBRMaterial": "00000000-0000-0000-0002-000000000003",
    "GridMaterial": "00000000-0000-0000-0002-000000000004",
    "SkinnedMaterial": "00000000-0000-0000-0002-000000000005",
    # Меши
    "Cube": "00000000-0000-0000-0003-000000000001",
    "Sphere": "00000000-0000-0000-0003-000000000002",
    "Plane": "00000000-0000-0000-0003-000000000003",
    "Cylinder": "00000000-0000-0000-0003-000000000004",
}


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
        self.textures: Dict[str, "Texture"] = {}
        self.voxel_grids: Dict[str, "VoxelGrid"] = {}  # VoxelGrid instances by name
        self.navmeshes: Dict[str, "NavMesh"] = {}  # NavMesh instances by name
        self.animation_clips: Dict[str, "AnimationClip"] = {}  # AnimationClip instances by name
        self.skeletons: Dict[str, "SkeletonData"] = {}  # SkeletonData instances by name
        self.components: Dict[str, type["Component"]] = {}
        self.frame_passes: Dict[str, type] = {}  # FramePass classes by name
        self.post_effects: Dict[str, type] = {}  # PostEffect classes by name
        self.pipelines: Dict[str, "RenderPipeline"] = {}  # RenderPipeline instances by name

        # Asset'ы по имени
        self._material_assets: Dict[str, "MaterialAsset"] = {}
        self._mesh_assets: Dict[str, "MeshAsset"] = {}
        self._texture_assets: Dict[str, "TextureAsset"] = {}
        self._shader_assets: Dict[str, "ShaderAsset"] = {}
        self._voxel_grid_assets: Dict[str, "VoxelGridAsset"] = {}
        self._navmesh_assets: Dict[str, "NavMeshAsset"] = {}
        self._animation_clip_assets: Dict[str, "AnimationClipAsset"] = {}
        self._skeleton_assets: Dict[str, "SkeletonAsset"] = {}
        self._glb_assets: Dict[str, "GLBAsset"] = {}

        # Asset'ы по UUID (для поиска существующих при загрузке)
        from termin.visualization.core.asset import Asset
        self._assets_by_uuid: Dict[str, Asset] = {}

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
        texture = self.textures.get(name)
        if texture is not None:
            texture._gpu.delete()
            texture._preview_pixmap = None

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
        if "DefaultShader" in self.shaders:
            return

        from termin.visualization.render.materials.default_material import (
            DEFAULT_VERT,
            DEFAULT_FRAG,
        )
        from termin.visualization.render.shader_parser import (
            ShaderMultyPhaseProgramm,
            ShaderPhase,
            ShasderStage,
            MaterialProperty,
        )

        # Создаём ShaderMultyPhaseProgramm для DefaultShader
        vertex_stage = ShasderStage("vertex", DEFAULT_VERT)
        fragment_stage = ShasderStage("fragment", DEFAULT_FRAG)

        phase = ShaderPhase(
            phase_mark="opaque",
            priority=0,
            gl_depth_mask=True,
            gl_depth_test=True,
            gl_blend=False,
            gl_cull=True,
            stages={"vertex": vertex_stage, "fragment": fragment_stage},
            uniforms=[
                MaterialProperty("u_color", "Color", (1.0, 1.0, 1.0, 1.0)),
                MaterialProperty("u_albedo_texture", "Texture", None),
                MaterialProperty("u_shininess", "Float", 32.0, 1.0, 2048.0),
            ],
        )

        program = ShaderMultyPhaseProgramm(program="DefaultShader", phases=[phase])
        self.register_shader("DefaultShader", program, uuid=_BUILTIN_UUIDS["DefaultShader"])

    def register_pbr_shader(self) -> None:
        """Регистрирует встроенный PBR шейдер."""
        if "PBRShader" in self.shaders:
            return

        from termin.visualization.render.materials.pbr_material import (
            PBR_VERT,
            PBR_FRAG,
        )
        from termin.visualization.render.shader_parser import (
            ShaderMultyPhaseProgramm,
            ShaderPhase,
            ShasderStage,
            MaterialProperty,
        )

        vertex_stage = ShasderStage("vertex", PBR_VERT)
        fragment_stage = ShasderStage("fragment", PBR_FRAG)

        phase = ShaderPhase(
            phase_mark="opaque",
            priority=0,
            gl_depth_mask=True,
            gl_depth_test=True,
            gl_blend=False,
            gl_cull=True,
            stages={"vertex": vertex_stage, "fragment": fragment_stage},
            uniforms=[
                MaterialProperty("u_color", "Color", (1.0, 1.0, 1.0, 1.0)),
                MaterialProperty("u_albedo_texture", "Texture", None),
                MaterialProperty("u_metallic", "Float", 0.0, 0.0, 1.0),
                MaterialProperty("u_roughness", "Float", 0.5, 0.0, 1.0),
            ],
        )

        program = ShaderMultyPhaseProgramm(program="PBRShader", phases=[phase])
        self.register_shader("PBRShader", program, uuid=_BUILTIN_UUIDS["PBRShader"])

    def register_advanced_pbr_shader(self) -> None:
        """Регистрирует встроенный Advanced PBR шейдер с SSS и ACES."""
        if "AdvancedPBRShader" in self.shaders:
            return

        from termin.visualization.render.materials.advanced_pbr_material import (
            ADVANCED_PBR_VERT,
            ADVANCED_PBR_FRAG,
        )
        from termin.visualization.render.shader_parser import (
            ShaderMultyPhaseProgramm,
            ShaderPhase,
            ShasderStage,
            MaterialProperty,
        )

        vertex_stage = ShasderStage("vertex", ADVANCED_PBR_VERT)
        fragment_stage = ShasderStage("fragment", ADVANCED_PBR_FRAG)

        phase = ShaderPhase(
            phase_mark="opaque",
            priority=0,
            gl_depth_mask=True,
            gl_depth_test=True,
            gl_blend=False,
            gl_cull=True,
            stages={"vertex": vertex_stage, "fragment": fragment_stage},
            uniforms=[
                MaterialProperty("u_color", "Color", (1.0, 1.0, 1.0, 1.0)),
                MaterialProperty("u_albedo_texture", "Texture", None),
                MaterialProperty("u_metallic", "Float", 0.0, 0.0, 1.0),
                MaterialProperty("u_roughness", "Float", 0.5, 0.0, 1.0),
                MaterialProperty("u_subsurface", "Float", 0.0, 0.0, 1.0),
            ],
        )

        program = ShaderMultyPhaseProgramm(program="AdvancedPBRShader", phases=[phase])
        self.register_shader("AdvancedPBRShader", program, uuid=_BUILTIN_UUIDS["AdvancedPBRShader"])

    def register_skinned_shader(self) -> None:
        """Регистрирует встроенный SkinnedShader для скелетной анимации."""
        if "SkinnedShader" in self.shaders:
            return

        from termin.visualization.render.materials.skinned_material import (
            SKINNED_VERT,
            SKINNED_FRAG,
        )
        from termin.visualization.render.shader_parser import (
            ShaderMultyPhaseProgramm,
            ShaderPhase,
            ShasderStage,
            MaterialProperty,
        )

        vertex_stage = ShasderStage("vertex", SKINNED_VERT)
        fragment_stage = ShasderStage("fragment", SKINNED_FRAG)

        phase = ShaderPhase(
            phase_mark="opaque",
            priority=0,
            gl_depth_mask=True,
            gl_depth_test=True,
            gl_blend=False,
            gl_cull=True,
            stages={"vertex": vertex_stage, "fragment": fragment_stage},
            uniforms=[
                MaterialProperty("u_color", "Color", (1.0, 1.0, 1.0, 1.0)),
                MaterialProperty("u_albedo_texture", "Texture", None),
                MaterialProperty("u_shininess", "Float", 32.0, 1.0, 2048.0),
            ],
        )

        program = ShaderMultyPhaseProgramm(program="SkinnedShader", phases=[phase])
        self.register_shader("SkinnedShader", program, uuid=_BUILTIN_UUIDS["SkinnedShader"])

    def register_builtin_materials(self) -> None:
        """Регистрирует встроенные материалы."""
        from termin.visualization.core.material import Material
        from termin.visualization.render.texture import get_white_texture

        # Убедимся что шейдеры зарегистрированы
        self.register_default_shader()
        self.register_pbr_shader()
        self.register_advanced_pbr_shader()
        self.register_skinned_shader()

        white_tex = get_white_texture()

        # DefaultMaterial (Blinn-Phong)
        if "DefaultMaterial" not in self.materials:
            shader = self.shaders.get("DefaultShader")
            if shader is not None:
                mat = Material.from_parsed(shader, textures={"u_albedo_texture": white_tex})
                mat.name = "DefaultMaterial"
                mat.color = (0.3, 0.85, 0.9, 1.0)
                self.register_material("DefaultMaterial", mat, uuid=_BUILTIN_UUIDS["DefaultMaterial"])

        # PBRMaterial
        if "PBRMaterial" not in self.materials:
            shader = self.shaders.get("PBRShader")
            if shader is not None:
                mat = Material.from_parsed(shader, textures={"u_albedo_texture": white_tex})
                mat.name = "PBRMaterial"
                mat.color = (0.8, 0.8, 0.8, 1.0)
                self.register_material("PBRMaterial", mat, uuid=_BUILTIN_UUIDS["PBRMaterial"])

        # AdvancedPBRMaterial (SSS + ACES)
        if "AdvancedPBRMaterial" not in self.materials:
            shader = self.shaders.get("AdvancedPBRShader")
            if shader is not None:
                mat = Material.from_parsed(shader, textures={"u_albedo_texture": white_tex})
                mat.name = "AdvancedPBRMaterial"
                mat.color = (0.8, 0.8, 0.8, 1.0)
                self.register_material("AdvancedPBRMaterial", mat, uuid=_BUILTIN_UUIDS["AdvancedPBRMaterial"])

        # GridMaterial (calibration grid)
        if "GridMaterial" not in self.materials:
            from termin.visualization.render.materials.grid_material import GridMaterial
            mat = GridMaterial(color=(0.8, 0.8, 0.8, 1.0), grid_spacing=1.0, line_width=0.02)
            mat.name = "GridMaterial"
            self.register_material("GridMaterial", mat, uuid=_BUILTIN_UUIDS["GridMaterial"])

        # SkinnedMaterial (skeletal animation)
        if "SkinnedMaterial" not in self.materials:
            shader = self.shaders.get("SkinnedShader")
            if shader is not None:
                mat = Material.from_parsed(shader, textures={"u_albedo_texture": white_tex})
                mat.name = "SkinnedMaterial"
                mat.color = (0.8, 0.8, 0.8, 1.0)
                self.register_material("SkinnedMaterial", mat, uuid=_BUILTIN_UUIDS["SkinnedMaterial"])

    def register_builtin_meshes(self) -> List[str]:
        """
        Регистрирует встроенные примитивные меши.

        Returns:
            Список имён зарегистрированных мешей.
        """
        from termin.visualization.core.mesh_asset import MeshAsset
        from termin.mesh.mesh import (
            TexturedCubeMesh,
            UVSphereMesh,
            PlaneMesh,
            CylinderMesh,
        )

        registered = []

        # Куб с корректными UV (текстура на каждой грани)
        if "Cube" not in self._mesh_assets:
            cube = MeshAsset.from_mesh3(TexturedCubeMesh(size=1.0), name="Cube")
            self.register_mesh_asset("Cube", cube, uuid=_BUILTIN_UUIDS["Cube"])
            registered.append("Cube")

        # Сфера
        if "Sphere" not in self._mesh_assets:
            sphere = MeshAsset.from_mesh3(UVSphereMesh(radius=0.5, n_meridians=32, n_parallels=16), name="Sphere")
            self.register_mesh_asset("Sphere", sphere, uuid=_BUILTIN_UUIDS["Sphere"])
            registered.append("Sphere")

        # Плоскость
        if "Plane" not in self._mesh_assets:
            plane = MeshAsset.from_mesh3(PlaneMesh(width=1.0, depth=1.0), name="Plane")
            self.register_mesh_asset("Plane", plane, uuid=_BUILTIN_UUIDS["Plane"])
            registered.append("Plane")

        # Цилиндр
        if "Cylinder" not in self._mesh_assets:
            cylinder = MeshAsset.from_mesh3(CylinderMesh(radius=0.5, height=1.0), name="Cylinder")
            self.register_mesh_asset("Cylinder", cylinder, uuid=_BUILTIN_UUIDS["Cylinder"])
            registered.append("Cylinder")

        return registered

    # --------- Меши (Asset-based) ---------
    def get_mesh_asset(self, name: str) -> Optional["MeshAsset"]:
        """Получить MeshAsset по имени."""
        return self._mesh_assets.get(name)

    def register_mesh_asset(
        self, name: str, asset: "MeshAsset", source_path: str | None = None, uuid: str | None = None
    ) -> None:
        """Регистрирует MeshAsset."""
        asset._name = name
        if source_path:
            asset._source_path = source_path
        if uuid is not None:
            asset._uuid = uuid
            asset._runtime_id = hash(uuid) & 0xFFFFFFFFFFFFFFFF
        self._mesh_assets[name] = asset
        self._assets_by_uuid[asset.uuid] = asset

    def get_mesh(self, name: str) -> Optional["MeshHandle"]:
        """Получить MeshHandle по имени."""
        from termin.visualization.core.mesh_handle import MeshHandle

        asset = self._mesh_assets.get(name)
        if asset is None:
            return None

        return MeshHandle.from_asset(asset)

    def list_mesh_names(self) -> list[str]:
        return sorted(self._mesh_assets.keys())

    def find_mesh_name(self, handle: "MeshHandle") -> Optional[str]:
        """Найти имя меша по MeshHandle."""
        if handle is None:
            return None
        # Get asset from handle and find it in registry
        asset = handle.get_asset()
        if asset is not None:
            for n, a in self._mesh_assets.items():
                if a is asset:
                    return n
        # Fallback: try by name
        if handle.name:
            if handle.name in self._mesh_assets:
                return handle.name
        return None

    def find_mesh_uuid(self, handle: "MeshHandle") -> Optional[str]:
        """Найти UUID меша по MeshHandle."""
        if handle is None:
            return None
        asset = handle.get_asset()
        if asset is not None:
            return asset.uuid
        return None

    def get_mesh_by_uuid(self, uuid: str) -> Optional["MeshHandle"]:
        """Получить MeshHandle по UUID."""
        from termin.visualization.core.mesh_asset import MeshAsset
        from termin.visualization.core.mesh_handle import MeshHandle

        asset = self._assets_by_uuid.get(uuid)
        if asset is None or not isinstance(asset, MeshAsset):
            return None

        return MeshHandle.from_asset(asset)

    def get_mesh_asset_by_uuid(self, uuid: str) -> Optional["MeshAsset"]:
        """Get MeshAsset by UUID."""
        from termin.visualization.core.mesh_asset import MeshAsset

        asset = self._assets_by_uuid.get(uuid)
        if asset is not None and isinstance(asset, MeshAsset):
            return asset
        return None

    def unregister_mesh(self, name: str) -> None:
        """Удаляет меш."""
        asset = self._mesh_assets.pop(name, None)
        if asset is not None:
            self._assets_by_uuid.pop(asset.uuid, None)

    # --------- Воксельные сетки (Asset-based) ---------
    def get_voxel_grid_asset(self, name: str) -> Optional["VoxelGridAsset"]:
        """Получить VoxelGridAsset по имени."""
        return self._voxel_grid_assets.get(name)

    def register_voxel_grid(self, name: str, grid: "VoxelGrid", source_path: str | None = None) -> None:
        """
        Регистрирует воксельную сетку.

        Args:
            name: Имя сетки
            grid: VoxelGrid
            source_path: Путь к файлу-источнику
        """
        from termin.voxels.voxel_grid_asset import VoxelGridAsset

        grid.name = name
        asset = VoxelGridAsset.from_grid(grid, name=name, source_path=source_path)
        self._voxel_grid_assets[name] = asset
        # Для обратной совместимости
        self.voxel_grids[name] = grid

    def get_voxel_grid(self, name: str) -> Optional["VoxelGrid"]:
        """Получить воксельную сетку по имени (lazy loading)."""
        # Check legacy dict first
        grid = self.voxel_grids.get(name)
        if grid is not None:
            return grid

        # Try lazy loading from asset
        asset = self._voxel_grid_assets.get(name)
        if asset is None:
            return None

        # Trigger lazy load if not loaded
        if asset.grid is None:
            if not asset.load():
                return None

        # Cache in legacy dict
        if asset.grid is not None:
            self.voxel_grids[name] = asset.grid

        return asset.grid

    def list_voxel_grid_names(self) -> list[str]:
        """Список имён всех воксельных сеток."""
        names = set(self._voxel_grid_assets.keys()) | set(self.voxel_grids.keys())
        return sorted(names)

    def find_voxel_grid_name(self, grid: "VoxelGrid") -> Optional[str]:
        """Найти имя воксельной сетки."""
        for n, asset in self._voxel_grid_assets.items():
            if asset.grid is grid:
                return n
        for n, g in self.voxel_grids.items():
            if g is grid:
                return n
        return None

    def find_voxel_grid_uuid(self, grid: "VoxelGrid") -> Optional[str]:
        """Find UUID of a VoxelGrid by looking up its asset."""
        for asset in self._voxel_grid_assets.values():
            if asset.grid is grid:
                return asset.uuid
        return None

    def get_voxel_grid_by_uuid(self, uuid: str) -> Optional["VoxelGrid"]:
        """Get VoxelGrid by UUID (lazy loading)."""
        from termin.voxels.voxel_grid_asset import VoxelGridAsset

        asset = self._assets_by_uuid.get(uuid)
        if asset is None or not isinstance(asset, VoxelGridAsset):
            return None

        # Trigger lazy load if not loaded
        if asset.grid is None:
            if not asset.load():
                return None

        # Cache in legacy dict
        if asset.grid is not None and asset.name:
            self.voxel_grids[asset.name] = asset.grid

        return asset.grid

    def get_voxel_grid_asset_by_uuid(self, uuid: str) -> Optional["VoxelGridAsset"]:
        """Get VoxelGridAsset by UUID."""
        from termin.voxels.voxel_grid_asset import VoxelGridAsset

        asset = self._assets_by_uuid.get(uuid)
        if asset is not None and isinstance(asset, VoxelGridAsset):
            return asset
        return None

    def unregister_voxel_grid(self, name: str) -> None:
        """Удаляет воксельную сетку."""
        if name in self._voxel_grid_assets:
            del self._voxel_grid_assets[name]
        if name in self.voxel_grids:
            del self.voxel_grids[name]

    # --------- Навигационные сетки (Asset-based) ---------
    def get_navmesh_asset(self, name: str) -> Optional["NavMeshAsset"]:
        """Получить NavMeshAsset по имени."""
        return self._navmesh_assets.get(name)

    def register_navmesh(self, name: str, navmesh: "NavMesh", source_path: str | None = None) -> None:
        """
        Регистрирует NavMesh.

        Args:
            name: Имя сетки
            navmesh: NavMesh
            source_path: Путь к файлу-источнику
        """
        from termin.navmesh.navmesh_asset import NavMeshAsset

        navmesh.name = name
        asset = NavMeshAsset.from_navmesh(navmesh, name=name, source_path=source_path)
        self._navmesh_assets[name] = asset
        # Для обратной совместимости
        self.navmeshes[name] = navmesh

    def get_navmesh(self, name: str) -> Optional["NavMesh"]:
        """Получить NavMesh по имени (lazy loading)."""
        # Check legacy dict first
        navmesh = self.navmeshes.get(name)
        if navmesh is not None:
            return navmesh

        # Try lazy loading from asset
        asset = self._navmesh_assets.get(name)
        if asset is None:
            return None

        # Trigger lazy load if not loaded
        if asset.navmesh is None:
            if not asset.load():
                return None

        # Cache in legacy dict
        if asset.navmesh is not None:
            self.navmeshes[name] = asset.navmesh

        return asset.navmesh

    def list_navmesh_names(self) -> list[str]:
        """Список имён всех NavMesh."""
        names = set(self._navmesh_assets.keys()) | set(self.navmeshes.keys())
        return sorted(names)

    def find_navmesh_name(self, navmesh: "NavMesh") -> Optional[str]:
        """Найти имя NavMesh."""
        for n, asset in self._navmesh_assets.items():
            if asset.navmesh is navmesh:
                return n
        for n, nm in self.navmeshes.items():
            if nm is navmesh:
                return n
        return None

    def find_navmesh_uuid(self, navmesh: "NavMesh") -> Optional[str]:
        """Find UUID of a NavMesh by looking up its asset."""
        for asset in self._navmesh_assets.values():
            if asset.navmesh is navmesh:
                return asset.uuid
        return None

    def get_navmesh_by_uuid(self, uuid: str) -> Optional["NavMesh"]:
        """Get NavMesh by UUID (lazy loading)."""
        from termin.navmesh.navmesh_asset import NavMeshAsset

        asset = self._assets_by_uuid.get(uuid)
        if asset is None or not isinstance(asset, NavMeshAsset):
            return None

        # Trigger lazy load if not loaded
        if asset.navmesh is None:
            if not asset.load():
                return None

        # Cache in legacy dict
        if asset.navmesh is not None and asset.name:
            self.navmeshes[asset.name] = asset.navmesh

        return asset.navmesh

    def get_navmesh_asset_by_uuid(self, uuid: str) -> Optional["NavMeshAsset"]:
        """Get NavMeshAsset by UUID."""
        from termin.navmesh.navmesh_asset import NavMeshAsset

        asset = self._assets_by_uuid.get(uuid)
        if asset is not None and isinstance(asset, NavMeshAsset):
            return asset
        return None

    def unregister_navmesh(self, name: str) -> None:
        """Удаляет NavMesh."""
        if name in self._navmesh_assets:
            del self._navmesh_assets[name]
        if name in self.navmeshes:
            del self.navmeshes[name]

    # --------- Анимационные клипы (Asset-based) ---------
    def get_animation_clip_asset(self, name: str) -> Optional["AnimationClipAsset"]:
        """Получить AnimationClipAsset по имени."""
        return self._animation_clip_assets.get(name)

    def register_animation_clip(
        self, name: str, clip: "AnimationClip", source_path: str | None = None, uuid: str | None = None
    ) -> None:
        """
        Регистрирует AnimationClip.

        Args:
            name: Имя клипа
            clip: AnimationClip
            source_path: Путь к файлу-источнику (.tanim)
            uuid: UUID для ассета (если None, генерируется автоматически)
        """
        from termin.visualization.animation.animation_clip_asset import AnimationClipAsset

        clip.name = name
        asset = AnimationClipAsset(clip=clip, name=name, source_path=source_path, uuid=uuid)
        self._animation_clip_assets[name] = asset
        self._assets_by_uuid[asset.uuid] = asset
        # Для обратной совместимости
        self.animation_clips[name] = clip

    def get_animation_clip(self, name: str) -> Optional["AnimationClip"]:
        """Получить AnimationClip по имени."""
        asset = self._animation_clip_assets.get(name)
        if asset is not None:
            return asset.clip
        return self.animation_clips.get(name)

    def get_animation_clip_asset_by_uuid(self, uuid: str) -> Optional["AnimationClipAsset"]:
        """Получить AnimationClipAsset по UUID."""
        from termin.visualization.animation.animation_clip_asset import AnimationClipAsset

        asset = self._assets_by_uuid.get(uuid)
        if asset is not None and isinstance(asset, AnimationClipAsset):
            return asset
        return None

    def list_animation_clip_names(self) -> list[str]:
        """Список имён всех AnimationClip."""
        names = set(self._animation_clip_assets.keys()) | set(self.animation_clips.keys())
        return sorted(names)

    def find_animation_clip_name(self, clip: "AnimationClip") -> Optional[str]:
        """Найти имя AnimationClip."""
        for n, asset in self._animation_clip_assets.items():
            if asset.clip is clip:
                return n
        for n, c in self.animation_clips.items():
            if c is clip:
                return n
        return None

    def unregister_animation_clip(self, name: str) -> None:
        """Удаляет AnimationClip."""
        if name in self._animation_clip_assets:
            del self._animation_clip_assets[name]
        if name in self.animation_clips:
            del self.animation_clips[name]

    # --------- Скелеты (Asset-based) ---------
    def get_skeleton_asset(self, name: str) -> Optional["SkeletonAsset"]:
        """Получить SkeletonAsset по имени."""
        return self._skeleton_assets.get(name)

    def register_skeleton(
        self, name: str, skeleton: "SkeletonData", source_path: str | None = None, uuid: str | None = None
    ) -> None:
        """
        Регистрирует скелет.

        Args:
            name: Имя скелета
            skeleton: SkeletonData
            source_path: Путь к файлу-источнику (GLB)
            uuid: UUID скелета (если известен)
        """
        from termin.skeleton.skeleton_asset import SkeletonAsset

        asset = SkeletonAsset.from_skeleton_data(skeleton, name=name, source_path=source_path, uuid=uuid)
        self._skeleton_assets[name] = asset
        self._assets_by_uuid[asset.uuid] = asset
        # Для обратной совместимости
        self.skeletons[name] = skeleton

    def get_skeleton(self, name: str) -> Optional["SkeletonData"]:
        """Получить SkeletonData по имени (lazy loading)."""
        # Check legacy dict first
        skeleton = self.skeletons.get(name)
        if skeleton is not None:
            return skeleton

        # Try lazy loading from asset
        asset = self._skeleton_assets.get(name)
        if asset is None:
            return None

        # Trigger lazy load if not loaded
        if asset.skeleton_data is None:
            if not asset.load():
                return None

        # Cache in legacy dict
        if asset.skeleton_data is not None:
            self.skeletons[name] = asset.skeleton_data

        return asset.skeleton_data

    def list_skeleton_names(self) -> list[str]:
        """Список имён всех скелетов."""
        names = set(self._skeleton_assets.keys()) | set(self.skeletons.keys())
        return sorted(names)

    def find_skeleton_name(self, skeleton: "SkeletonData") -> Optional[str]:
        """Найти имя скелета."""
        for n, asset in self._skeleton_assets.items():
            if asset.skeleton_data is skeleton:
                return n
        for n, s in self.skeletons.items():
            if s is skeleton:
                return n
        return None

    def find_skeleton_uuid(self, skeleton: "SkeletonData") -> Optional[str]:
        """Find UUID of a SkeletonData by looking up its asset."""
        for asset in self._skeleton_assets.values():
            if asset.skeleton_data is skeleton:
                return asset.uuid
        return None

    def get_skeleton_by_uuid(self, uuid: str) -> Optional["SkeletonData"]:
        """Get SkeletonData by UUID (lazy loading)."""
        from termin.skeleton.skeleton_asset import SkeletonAsset

        asset = self._assets_by_uuid.get(uuid)
        if asset is None or not isinstance(asset, SkeletonAsset):
            return None

        # Trigger lazy load if not loaded
        if asset.skeleton_data is None:
            if not asset.load():
                return None

        # Cache in legacy dict
        if asset.skeleton_data is not None and asset.name:
            self.skeletons[asset.name] = asset.skeleton_data

        return asset.skeleton_data

    def get_skeleton_asset_by_uuid(self, uuid: str) -> Optional["SkeletonAsset"]:
        """Get SkeletonAsset by UUID."""
        from termin.skeleton.skeleton_asset import SkeletonAsset

        asset = self._assets_by_uuid.get(uuid)
        if asset is not None and isinstance(asset, SkeletonAsset):
            return asset
        return None

    def unregister_skeleton(self, name: str) -> None:
        """Удаляет скелет."""
        if name in self._skeleton_assets:
            del self._skeleton_assets[name]
        if name in self.skeletons:
            del self.skeletons[name]

    # --------- Текстуры (Asset-based) ---------
    def get_texture_asset(self, name: str) -> Optional["TextureAsset"]:
        """Получить TextureAsset по имени."""
        asset = self._texture_assets.get(name)
        if asset is not None:
            return asset
        # Fallback: извлечь из Texture
        texture = self.textures.get(name)
        if texture is not None:
            return texture.asset
        return None

    def register_texture(self, name: str, texture: "Texture", source_path: str | None = None):
        """Регистрирует текстуру."""
        asset = texture.asset
        if asset is not None:
            asset.name = name
            if source_path:
                asset.source_path = source_path
            self._texture_assets[name] = asset
        # Для обратной совместимости
        self.textures[name] = texture

    def get_texture(self, name: str) -> Optional["Texture"]:
        """Получить текстуру по имени."""
        # Check if already loaded
        texture = self.textures.get(name)
        if texture is not None:
            return texture

        # Try from asset (lazy loading happens inside asset.data)
        asset = self._texture_assets.get(name)
        if asset is None:
            return None

        # Access data triggers lazy load inside asset
        if asset.data is None:
            return None

        # Create Texture wrapper and cache it
        from termin.visualization.render.texture import Texture
        texture = Texture.from_asset(asset)
        self.textures[name] = texture
        return texture

    def list_texture_names(self) -> list[str]:
        names = set(self._texture_assets.keys()) | set(self.textures.keys())
        return sorted(names)

    def find_texture_name(self, texture: "Texture") -> Optional[str]:
        for n, t in self.textures.items():
            if t is texture:
                return n
        return None

    def unregister_texture(self, name: str) -> None:
        """Удаляет текстуру."""
        if name in self._texture_assets:
            del self._texture_assets[name]
        if name in self.textures:
            del self.textures[name]

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
                   Примеры:
                   - "termin.visualization.components" (модуль)
                   - "/home/user/my_components" (директория)
                   - "/home/user/rotator.py" (файл)

        Returns:
            Список имён загруженных компонентов.
        """
        import importlib
        import importlib.util
        import os
        import sys

        loaded = []

        for path in paths:
            if os.path.isfile(path) and path.endswith(".py"):
                # Загружаем отдельный .py файл
                loaded.extend(self._scan_file(path))
            elif os.path.isdir(path):
                # Сканируем директорию
                loaded.extend(self._scan_directory(path))
            else:
                # Пробуем как имя модуля
                loaded.extend(self._scan_module(path))

        return loaded

    def _scan_file(self, filepath: str) -> list[str]:
        """Загружает компоненты из одного .py файла."""
        import importlib.util
        import os
        import sys

        before = set(self.components.keys())
        filename = os.path.basename(filepath)
        module_name = f"_dynamic_components_.{os.path.splitext(filename)[0]}_{id(filepath)}"

        try:
            spec = importlib.util.spec_from_file_location(module_name, filepath)
            if spec is None or spec.loader is None:
                return []

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

        except Exception as e:
            print(f"Warning: Failed to load {filepath}: {e}")
            return []

        after = set(self.components.keys())
        return list(after - before)

    def _scan_module(self, module_name: str) -> list[str]:
        """Загружает модуль и все его подмодули."""
        import importlib
        import pkgutil

        loaded = []
        before = set(self.components.keys())

        try:
            module = importlib.import_module(module_name)

            # Если это пакет, сканируем подмодули
            if hasattr(module, "__path__"):
                for importer, name, is_pkg in pkgutil.walk_packages(
                    module.__path__, prefix=module_name + "."
                ):
                    try:
                        importlib.import_module(name)
                    except Exception as e:
                        print(f"Warning: Failed to import {name}: {e}")

            after = set(self.components.keys())
            loaded = list(after - before)

        except Exception as e:
            print(f"Warning: Failed to import module {module_name}: {e}")

        return loaded

    def _scan_directory(self, directory: str) -> list[str]:
        """Сканирует директорию и загружает все .py файлы как модули."""
        import importlib.util
        import os
        import sys

        loaded = []
        before = set(self.components.keys())

        for root, dirs, files in os.walk(directory):
            # Пропускаем __pycache__ и скрытые директории
            dirs[:] = [d for d in dirs if not d.startswith((".", "__"))]

            for filename in files:
                if not filename.endswith(".py") or filename.startswith("_"):
                    continue

                filepath = os.path.join(root, filename)
                module_name = os.path.splitext(filename)[0]

                # Создаём уникальное имя модуля
                rel_path = os.path.relpath(filepath, directory)
                unique_name = f"_dynamic_components_.{rel_path.replace(os.sep, '.')[:-3]}"

                try:
                    spec = importlib.util.spec_from_file_location(unique_name, filepath)
                    if spec is None or spec.loader is None:
                        continue

                    module = importlib.util.module_from_spec(spec)
                    sys.modules[unique_name] = module
                    spec.loader.exec_module(module)

                except Exception as e:
                    print(f"Warning: Failed to load {filepath}: {e}")

        after = set(self.components.keys())
        loaded = list(after - before)

        return loaded

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
        import importlib
        import importlib.util
        import os
        import sys

        loaded = []

        for path in paths:
            if os.path.isfile(path) and path.endswith(".py"):
                loaded.extend(self._scan_file_for_frame_passes(path))
            elif os.path.isdir(path):
                loaded.extend(self._scan_directory_for_frame_passes(path))
            else:
                loaded.extend(self._scan_module_for_frame_passes(path))

        return loaded

    def _scan_file_for_frame_passes(self, filepath: str) -> list[str]:
        """Загружает FramePass'ы из одного .py файла."""
        import importlib.util
        import os
        import sys

        before = set(self.frame_passes.keys())

        filename = os.path.basename(filepath)
        module_name = f"_dynamic_frame_passes_.{os.path.splitext(filename)[0]}_{id(filepath)}"

        try:
            spec = importlib.util.spec_from_file_location(module_name, filepath)
            if spec is None or spec.loader is None:
                return []

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            # Ищем классы, наследующиеся от FramePass
            from termin.visualization.render.framegraph.core import FramePass

            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, FramePass)
                    and attr is not FramePass
                    and attr_name not in self.frame_passes
                ):
                    self.frame_passes[attr_name] = attr

        except Exception as e:
            print(f"Warning: Failed to load frame passes from {filepath}: {e}")
            return []

        after = set(self.frame_passes.keys())
        return list(after - before)

    def _scan_directory_for_frame_passes(self, directory: str) -> list[str]:
        """Сканирует директорию и загружает все FramePass'ы."""
        import os

        loaded = []

        for root, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if not d.startswith((".", "__"))]

            for filename in files:
                if not filename.endswith(".py") or filename.startswith("_"):
                    continue

                filepath = os.path.join(root, filename)
                loaded.extend(self._scan_file_for_frame_passes(filepath))

        return loaded

    def _scan_module_for_frame_passes(self, module_name: str) -> list[str]:
        """Загружает FramePass'ы из модуля."""
        import importlib
        import pkgutil

        loaded = []
        before = set(self.frame_passes.keys())

        try:
            module = importlib.import_module(module_name)

            from termin.visualization.render.framegraph.core import FramePass

            # Ищем классы в самом модуле
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, FramePass)
                    and attr is not FramePass
                    and attr_name not in self.frame_passes
                ):
                    self.frame_passes[attr_name] = attr

            # Если это пакет, сканируем подмодули
            if hasattr(module, "__path__"):
                for importer, name, is_pkg in pkgutil.walk_packages(
                    module.__path__, prefix=module_name + "."
                ):
                    try:
                        submodule = importlib.import_module(name)
                        for attr_name in dir(submodule):
                            attr = getattr(submodule, attr_name)
                            if (
                                isinstance(attr, type)
                                and issubclass(attr, FramePass)
                                and attr is not FramePass
                                and attr_name not in self.frame_passes
                            ):
                                self.frame_passes[attr_name] = attr
                    except Exception as e:
                        print(f"Warning: Failed to import {name}: {e}")

            after = set(self.frame_passes.keys())
            loaded = list(after - before)

        except Exception as e:
            print(f"Warning: Failed to import module {module_name}: {e}")

        return loaded

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
            "textures": {name: self._serialize_texture(tex) for name, tex in self.textures.items()},
        }

    def _serialize_texture(self, tex: "Texture") -> dict:
        """Сериализует текстуру."""
        source_path = tex.source_path if tex.source_path else None
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
