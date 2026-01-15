"""Asset management mixin for all resource types."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from termin.visualization.core.material import Material
    from termin.assets.material_asset import MaterialAsset
    from termin.assets.mesh_asset import MeshAsset
    from termin.mesh import TcMesh
    from termin.assets.texture_handle import TextureHandle
    from termin.assets.glb_asset import GLBAsset
    from termin.visualization.render.texture import Texture
    from termin.assets.texture_asset import TextureAsset
    from termin.visualization.render.shader_parser import ShaderMultyPhaseProgramm
    from termin.assets.shader_asset import ShaderAsset
    from termin.voxels.grid import VoxelGrid
    from termin.assets.voxel_grid_asset import VoxelGridAsset
    from termin.navmesh.types import NavMesh
    from termin.assets.navmesh_asset import NavMeshAsset
    from termin.visualization.animation.clip import TcAnimationClip
    from termin.assets.animation_clip_asset import AnimationClipAsset
    from termin.skeleton import TcSkeleton
    from termin.assets.skeleton_asset import SkeletonAsset
    from termin.assets.prefab_asset import PrefabAsset
    from termin.kinematic.general_transform import GeneralTransform3
    from termin.assets.audio_clip_asset import AudioClipAsset
    from termin.assets.audio_clip_handle import AudioClipHandle
    from termin.visualization.core.entity import Entity
    from termin.assets.asset import Asset


class AssetsMixin:
    """Mixin for all asset type management methods."""

    # --------- Prefabs ---------
    def get_prefab_asset(self, name: str) -> Optional["PrefabAsset"]:
        """Get PrefabAsset by name."""
        return self._prefab_assets.get(name)

    def get_prefab(self, name: str) -> Optional["PrefabAsset"]:
        """Get PrefabAsset by name (alias for get_prefab_asset)."""
        return self._prefab_assets.get(name)

    def get_prefab_by_uuid(self, uuid: str) -> Optional["PrefabAsset"]:
        """Get PrefabAsset by UUID."""
        from termin.assets.prefab_asset import PrefabAsset
        asset = self._assets_by_uuid.get(uuid)
        if asset is not None and isinstance(asset, PrefabAsset):
            return asset
        return None

    def register_prefab(
        self,
        name: str,
        asset: "PrefabAsset",
        source_path: str | None = None,
    ) -> None:
        """Register a PrefabAsset."""
        self._prefab_assets[name] = asset
        self._assets_by_uuid[asset.uuid] = asset
        if source_path:
            asset._source_path = source_path

    def list_prefab_names(self) -> list[str]:
        """List all registered prefab names."""
        return sorted(self._prefab_assets.keys())

    def find_prefab_name(self, asset: "PrefabAsset") -> Optional[str]:
        """Find name of a PrefabAsset."""
        for name, a in self._prefab_assets.items():
            if a is asset:
                return name
        return None

    def find_prefab_uuid(self, asset: "PrefabAsset") -> Optional[str]:
        """Find UUID of a PrefabAsset."""
        return asset.uuid if asset else None

    def instantiate_prefab(
        self,
        name_or_uuid: str,
        parent: "GeneralTransform3 | None" = None,
        position: tuple[float, float, float] | None = None,
        instance_name: str | None = None,
    ) -> Optional["Entity"]:
        """Instantiate a prefab by name or UUID."""
        asset = self._prefab_assets.get(name_or_uuid)
        if asset is None:
            asset = self.get_prefab_by_uuid(name_or_uuid)
        if asset is None:
            return None
        if not asset.is_loaded:
            asset.ensure_loaded()
        return asset.instantiate(parent=parent, position=position, name=instance_name)

    def unregister_prefab(self, name: str) -> None:
        """Remove prefab by name."""
        asset = self._prefab_assets.pop(name, None)
        if asset is not None:
            self._assets_by_uuid.pop(asset.uuid, None)

    def get_glsl(self, name: str) -> Optional[str]:
        """Get GLSL source by include name."""
        return self._glsl_registry.get(name)

    def get_glb_asset(self, name: str) -> Optional["GLBAsset"]:
        """Get GLBAsset by name."""
        return self._glb_assets.get(name)

    def get_asset_by_uuid(self, uuid: str) -> Optional["Asset"]:
        """Get any Asset by UUID."""
        return self._assets_by_uuid.get(uuid)

    # --------- Materials ---------
    def get_material_asset(self, name: str) -> Optional["MaterialAsset"]:
        """Get MaterialAsset by name."""
        return self._material_assets.get(name)

    def register_material(
        self, name: str, mat: "Material", source_path: str | None = None, uuid: str | None = None
    ):
        """Register a material."""
        from termin.assets.material_asset import MaterialAsset
        asset = MaterialAsset.from_material(mat, name=name, source_path=source_path, uuid=uuid)
        self._material_assets[name] = asset
        self._assets_by_uuid[asset.uuid] = asset
        self.materials[name] = mat

    def get_material(self, name: str) -> "Material":
        """
        Get material by name (lazy loading).

        Returns UnknownMaterial if material is not found or failed to load.
        """
        from termin.visualization.render.materials.unknown_material import UnknownMaterial

        mat = self.materials.get(name)
        if mat is not None:
            return mat
        asset = self._material_assets.get(name)
        if asset is None:
            return UnknownMaterial.for_missing_material(name)
        if asset.material is None:
            if not asset.ensure_loaded():
                return UnknownMaterial.for_missing_material(name)
        if asset.material is not None:
            self.materials[name] = asset.material
            return asset.material
        return UnknownMaterial.for_missing_material(name)

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
        for asset in self._material_assets.values():
            if asset.material is mat:
                return asset.uuid
        return None

    def get_material_by_uuid(self, uuid: str) -> "Material":
        """
        Get Material by UUID (lazy loading).

        Returns UnknownMaterial if material is not found or failed to load.
        """
        from termin.assets.material_asset import MaterialAsset
        from termin.visualization.render.materials.unknown_material import UnknownMaterial

        asset = self._assets_by_uuid.get(uuid)
        if asset is None or not isinstance(asset, MaterialAsset):
            return UnknownMaterial.for_missing_material(f"uuid:{uuid}")
        if asset.material is None:
            if not asset.ensure_loaded():
                return UnknownMaterial.for_missing_material(asset.name or f"uuid:{uuid}")
        if asset.material is not None:
            if asset.name:
                self.materials[asset.name] = asset.material
            return asset.material
        return UnknownMaterial.for_missing_material(asset.name or f"uuid:{uuid}")

    def get_material_asset_by_uuid(self, uuid: str) -> Optional["MaterialAsset"]:
        """Get MaterialAsset by UUID."""
        from termin.assets.material_asset import MaterialAsset
        asset = self._assets_by_uuid.get(uuid)
        if asset is not None and isinstance(asset, MaterialAsset):
            return asset
        return None

    def get_texture_asset_by_uuid(self, uuid: str) -> Optional["TextureAsset"]:
        """Get TextureAsset by UUID."""
        from termin.assets.texture_asset import TextureAsset
        asset = self._assets_by_uuid.get(uuid)
        if asset is not None and isinstance(asset, TextureAsset):
            return asset
        return None

    # --------- Shaders ---------
    def get_shader_asset(self, name: str) -> Optional["ShaderAsset"]:
        """Get ShaderAsset by name."""
        return self._shader_assets.get(name)

    def register_shader(
        self, name: str, shader: "ShaderMultyPhaseProgramm", source_path: str | None = None, uuid: str | None = None
    ):
        """Register a shader."""
        from termin.assets.shader_asset import ShaderAsset
        asset = ShaderAsset.from_program(shader, name=name, source_path=source_path, uuid=uuid)
        self._shader_assets[name] = asset
        self._assets_by_uuid[asset.uuid] = asset
        self.shaders[name] = shader
        if source_path:
            shader.source_path = source_path

    def get_shader(self, name: str) -> Optional["ShaderMultyPhaseProgramm"]:
        """Get shader by name (lazy loading)."""
        shader = self.shaders.get(name)
        if shader is not None:
            return shader
        asset = self._shader_assets.get(name)
        if asset is None:
            return None
        if asset.program is None:
            if not asset.ensure_loaded():
                return None
        if asset.program is not None:
            self.shaders[name] = asset.program
        return asset.program

    def list_shader_names(self) -> list[str]:
        names = set(self._shader_assets.keys()) | set(self.shaders.keys())
        return sorted(names)

    def register_default_shader(self) -> None:
        """Register builtin DefaultShader."""
        from termin.assets.builtin_resources import register_default_shader
        register_default_shader(self)

    def register_pbr_shader(self) -> None:
        """Register builtin PBR shader."""
        from termin.assets.builtin_resources import register_pbr_shader
        register_pbr_shader(self)

    def register_advanced_pbr_shader(self) -> None:
        """Register builtin Advanced PBR shader."""
        from termin.assets.builtin_resources import register_advanced_pbr_shader
        register_advanced_pbr_shader(self)

    def register_skinned_shader(self) -> None:
        """Register builtin SkinnedShader."""
        from termin.assets.builtin_resources import register_skinned_shader
        register_skinned_shader(self)

    def register_builtin_materials(self) -> None:
        """Register builtin materials."""
        from termin.assets.builtin_resources import register_builtin_materials
        register_builtin_materials(self)

    def register_builtin_meshes(self) -> List[str]:
        """Register builtin primitive meshes."""
        from termin.assets.builtin_resources import register_builtin_meshes
        return register_builtin_meshes(self)

    # --------- Meshes ---------
    def get_mesh_asset(self, name: str) -> Optional["MeshAsset"]:
        """Get MeshAsset by name."""
        return self._mesh_registry.get_asset(name)

    def register_mesh_asset(
        self, name: str, asset: "MeshAsset", source_path: str | None = None, uuid: str | None = None
    ) -> None:
        """Register MeshAsset."""
        self._mesh_registry.register(name, asset, source_path, uuid)

    def get_mesh(self, name: str) -> Optional["TcMesh"]:
        """Get TcMesh by name."""
        return self._mesh_registry.get(name)

    def list_mesh_names(self) -> list[str]:
        return list(self._mesh_assets.keys())

    def find_mesh_name(self, mesh: "TcMesh") -> Optional[str]:
        """Find mesh name by TcMesh."""
        if mesh is None:
            return None
        name = self._mesh_registry.find_name(mesh)
        if name:
            return name
        if mesh.is_valid and mesh.name and mesh.name in self._mesh_assets:
            return mesh.name
        return None

    def find_mesh_uuid(self, mesh: "TcMesh") -> Optional[str]:
        """Find mesh UUID by TcMesh."""
        if mesh is None:
            return None
        return self._mesh_registry.find_uuid(mesh)

    def get_mesh_by_uuid(self, uuid: str) -> Optional["TcMesh"]:
        """Get TcMesh by UUID."""
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
        """Get MeshAsset by name, creating if needed."""
        return self._mesh_registry.get_or_create_asset(
            name=name, source_path=source_path, uuid=uuid, parent=parent, parent_key=parent_key,
        )

    def unregister_mesh(self, name: str) -> None:
        """Remove mesh."""
        self._mesh_registry.unregister(name)

    # --------- Voxel Grids ---------
    def get_voxel_grid_asset(self, name: str) -> Optional["VoxelGridAsset"]:
        """Get VoxelGridAsset by name."""
        return self._voxel_grid_registry.get_asset(name)

    def register_voxel_grid(self, name: str, grid: "VoxelGrid", source_path: str | None = None) -> None:
        """Register voxel grid."""
        from termin.assets.voxel_grid_asset import VoxelGridAsset
        grid.name = name
        existing_asset = self._voxel_grid_registry.get_asset(name)
        if existing_asset is not None:
            existing_asset.data = grid
            self.voxel_grids[name] = grid
            return
        asset = VoxelGridAsset.from_grid(grid, name=name, source_path=source_path)
        self._voxel_grid_registry.register(name, asset, source_path)
        self.voxel_grids[name] = grid

    def get_voxel_grid(self, name: str) -> Optional["VoxelGrid"]:
        """Get voxel grid by name (lazy loading)."""
        grid = self.voxel_grids.get(name)
        if grid is not None:
            return grid
        grid = self._voxel_grid_registry.get(name)
        if grid is not None:
            self.voxel_grids[name] = grid
        return grid

    def list_voxel_grid_names(self) -> list[str]:
        return self._voxel_grid_registry.list_names()

    def find_voxel_grid_name(self, grid: "VoxelGrid") -> Optional[str]:
        return self._voxel_grid_registry.find_name(grid)

    def find_voxel_grid_uuid(self, grid: "VoxelGrid") -> Optional[str]:
        return self._voxel_grid_registry.find_uuid(grid)

    def get_voxel_grid_by_uuid(self, uuid: str) -> Optional["VoxelGrid"]:
        grid = self._voxel_grid_registry.get_by_uuid(uuid)
        if grid is not None:
            asset = self._voxel_grid_registry.get_asset_by_uuid(uuid)
            if asset is not None and asset.name:
                self.voxel_grids[asset.name] = grid
        return grid

    def get_voxel_grid_asset_by_uuid(self, uuid: str) -> Optional["VoxelGridAsset"]:
        return self._voxel_grid_registry.get_asset_by_uuid(uuid)

    def unregister_voxel_grid(self, name: str) -> None:
        self._voxel_grid_registry.unregister(name)
        if name in self.voxel_grids:
            del self.voxel_grids[name]

    # --------- NavMeshes ---------
    def get_navmesh_asset(self, name: str) -> Optional["NavMeshAsset"]:
        return self._navmesh_registry.get_asset(name)

    def register_navmesh(self, name: str, navmesh: "NavMesh", source_path: str | None = None) -> None:
        from termin.assets.navmesh_asset import NavMeshAsset
        navmesh.name = name
        asset = NavMeshAsset.from_navmesh(navmesh, name=name, source_path=source_path)
        self._navmesh_registry.register(name, asset, source_path)
        self.navmeshes[name] = navmesh

    def get_navmesh(self, name: str) -> Optional["NavMesh"]:
        navmesh = self.navmeshes.get(name)
        if navmesh is not None:
            return navmesh
        navmesh = self._navmesh_registry.get(name)
        if navmesh is not None:
            self.navmeshes[name] = navmesh
        return navmesh

    def list_navmesh_names(self) -> list[str]:
        return self._navmesh_registry.list_names()

    def find_navmesh_name(self, navmesh: "NavMesh") -> Optional[str]:
        return self._navmesh_registry.find_name(navmesh)

    def find_navmesh_uuid(self, navmesh: "NavMesh") -> Optional[str]:
        return self._navmesh_registry.find_uuid(navmesh)

    def get_navmesh_by_uuid(self, uuid: str) -> Optional["NavMesh"]:
        navmesh = self._navmesh_registry.get_by_uuid(uuid)
        if navmesh is not None:
            asset = self._navmesh_registry.get_asset_by_uuid(uuid)
            if asset is not None and asset.name:
                self.navmeshes[asset.name] = navmesh
        return navmesh

    def get_navmesh_asset_by_uuid(self, uuid: str) -> Optional["NavMeshAsset"]:
        return self._navmesh_registry.get_asset_by_uuid(uuid)

    def unregister_navmesh(self, name: str) -> None:
        self._navmesh_registry.unregister(name)
        if name in self.navmeshes:
            del self.navmeshes[name]

    # --------- Animation Clips ---------
    def get_animation_clip_asset(self, name: str) -> Optional["AnimationClipAsset"]:
        return self._animation_clip_registry.get_asset(name)

    def register_animation_clip(
        self, name: str, clip: "TcAnimationClip", source_path: str | None = None, uuid: str | None = None
    ) -> None:
        from termin.assets.animation_clip_asset import AnimationClipAsset
        asset = AnimationClipAsset(clip=clip, name=name, source_path=source_path, uuid=uuid)
        self._animation_clip_registry.register(name, asset, source_path, uuid)
        self.animation_clips[name] = clip

    def get_animation_clip(self, name: str) -> Optional["TcAnimationClip"]:
        clip = self.animation_clips.get(name)
        if clip is not None:
            return clip
        return self._animation_clip_registry.get(name)

    def get_animation_clip_asset_by_uuid(self, uuid: str) -> Optional["AnimationClipAsset"]:
        return self._animation_clip_registry.get_asset_by_uuid(uuid)

    def get_or_create_animation_clip_asset(
        self,
        name: str,
        source_path: str | None = None,
        uuid: str | None = None,
        parent: "Asset | None" = None,
        parent_key: str | None = None,
    ) -> "AnimationClipAsset":
        return self._animation_clip_registry.get_or_create_asset(
            name=name, source_path=source_path, uuid=uuid, parent=parent, parent_key=parent_key,
        )

    def list_animation_clip_names(self) -> list[str]:
        return self._animation_clip_registry.list_names()

    def find_animation_clip_name(self, clip: "TcAnimationClip") -> Optional[str]:
        return self._animation_clip_registry.find_name(clip)

    def unregister_animation_clip(self, name: str) -> None:
        self._animation_clip_registry.unregister(name)
        if name in self.animation_clips:
            del self.animation_clips[name]

    # --------- Skeletons ---------
    def get_skeleton_asset(self, name: str) -> Optional["SkeletonAsset"]:
        return self._skeleton_registry.get_asset(name)

    def register_skeleton(
        self, name: str, skeleton: "TcSkeleton", source_path: str | None = None, uuid: str | None = None
    ) -> None:
        from termin.assets.skeleton_asset import SkeletonAsset
        asset = SkeletonAsset.from_tc_skeleton(skeleton, name=name, source_path=source_path, uuid=uuid)
        self._skeleton_registry.register(name, asset, source_path, uuid)
        self.skeletons[name] = skeleton

    def get_skeleton(self, name: str) -> Optional["TcSkeleton"]:
        skeleton = self.skeletons.get(name)
        if skeleton is not None:
            return skeleton
        skeleton = self._skeleton_registry.get(name)
        if skeleton is not None:
            self.skeletons[name] = skeleton
        return skeleton

    def list_skeleton_names(self) -> list[str]:
        return self._skeleton_registry.list_names()

    def find_skeleton_name(self, skeleton: "TcSkeleton") -> Optional[str]:
        return self._skeleton_registry.find_name(skeleton)

    def find_skeleton_uuid(self, skeleton: "TcSkeleton") -> Optional[str]:
        return self._skeleton_registry.find_uuid(skeleton)

    def get_skeleton_by_uuid(self, uuid: str) -> Optional["TcSkeleton"]:
        skeleton = self._skeleton_registry.get_by_uuid(uuid)
        if skeleton is not None:
            asset = self._skeleton_registry.get_asset_by_uuid(uuid)
            if asset is not None and asset.name:
                self.skeletons[asset.name] = skeleton
        return skeleton

    def get_skeleton_asset_by_uuid(self, uuid: str) -> Optional["SkeletonAsset"]:
        return self._skeleton_registry.get_asset_by_uuid(uuid)

    def get_or_create_skeleton_asset(
        self,
        name: str,
        source_path: str | None = None,
        uuid: str | None = None,
        parent: "Asset | None" = None,
        parent_key: str | None = None,
    ) -> "SkeletonAsset":
        return self._skeleton_registry.get_or_create_asset(
            name=name, source_path=source_path, uuid=uuid, parent=parent, parent_key=parent_key,
        )

    def unregister_skeleton(self, name: str) -> None:
        self._skeleton_registry.unregister(name)
        if name in self.skeletons:
            del self.skeletons[name]

    # --------- Audio Clips ---------
    def get_audio_clip_asset(self, name: str) -> Optional["AudioClipAsset"]:
        return self._audio_clip_registry.get_asset(name)

    def get_audio_clip(self, name: str) -> Optional["AudioClipHandle"]:
        return self._audio_clip_registry.get(name)

    def register_audio_clip_asset(
        self, name: str, asset: "AudioClipAsset", source_path: str | None = None, uuid: str | None = None,
    ) -> None:
        self._audio_clip_registry.register(name, asset, source_path, uuid)

    def list_audio_clip_names(self) -> list[str]:
        return self._audio_clip_registry.list_names()

    def find_audio_clip_name(self, handle: "AudioClipHandle") -> Optional[str]:
        return self._audio_clip_registry.find_name(handle)

    def find_audio_clip_uuid(self, handle: "AudioClipHandle") -> Optional[str]:
        return self._audio_clip_registry.find_uuid(handle)

    def get_audio_clip_by_uuid(self, uuid: str) -> Optional["AudioClipHandle"]:
        return self._audio_clip_registry.get_by_uuid(uuid)

    def get_audio_clip_asset_by_uuid(self, uuid: str) -> Optional["AudioClipAsset"]:
        return self._audio_clip_registry.get_asset_by_uuid(uuid)

    def get_or_create_audio_clip_asset(
        self, name: str, source_path: str | None = None, uuid: str | None = None,
    ) -> "AudioClipAsset":
        return self._audio_clip_registry.get_or_create_asset(name=name, source_path=source_path, uuid=uuid)

    def unregister_audio_clip(self, name: str) -> None:
        self._audio_clip_registry.unregister(name)

    # --------- UI Layouts ---------
    def get_ui_asset(self, name: str):
        return self._ui_registry.get_asset(name)

    def get_ui_handle(self, name: str):
        from termin.assets.ui_handle import UIHandle
        asset = self._ui_registry.get_asset(name)
        if asset is not None:
            return UIHandle.from_asset(asset)
        return None

    def list_ui_names(self) -> list[str]:
        return self._ui_registry.list_names()

    def get_ui_asset_by_uuid(self, uuid: str):
        return self._ui_registry.get_asset_by_uuid(uuid)

    def unregister_ui(self, name: str) -> None:
        self._ui_registry.unregister(name)

    # --------- Textures ---------
    def get_texture_asset(self, name: str) -> Optional["TextureAsset"]:
        return self._texture_registry.get_asset(name)

    def get_texture_handle(self, name: str) -> Optional["TextureHandle"]:
        return self._texture_registry.get(name)

    def get_texture(self, name: str) -> Optional["Texture"]:
        from termin.visualization.render.texture import Texture
        asset = self._texture_registry.get_asset(name)
        if asset is not None:
            return Texture.from_asset(asset)
        return None

    def register_texture_asset(
        self, name: str, asset: "TextureAsset", source_path: str | None = None, uuid: str | None = None,
    ) -> None:
        self._texture_registry.register(name, asset, source_path, uuid)

    def list_texture_names(self) -> list[str]:
        return self._texture_registry.list_names()

    def find_texture_name(self, texture) -> Optional[str]:
        from termin.assets.texture_handle import TextureHandle
        if isinstance(texture, TextureHandle):
            # Get asset from handle and compare by uuid
            asset = texture.asset
            if asset is not None and not isinstance(asset, type(None)):
                try:
                    asset_uuid = asset.uuid
                    for name, a in self._texture_registry.assets.items():
                        if a.uuid == asset_uuid:
                            return name
                except (AttributeError, TypeError):
                    pass
            # Fallback to registry method
            return self._texture_registry.find_name(texture)
        else:
            for n, a in self._texture_assets.items():
                if a is texture:
                    return n
        return None

    def unregister_texture(self, name: str) -> None:
        self._texture_registry.unregister(name)
