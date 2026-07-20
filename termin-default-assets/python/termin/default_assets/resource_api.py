"""Resource-manager API for default Termin asset types."""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from tcbase import log

if TYPE_CHECKING:
    from termin_assets import Asset
    from termin.animation import TcAnimationClip
    from termin.animation.asset import AnimationClipAsset
    from termin.default_assets.audio.asset import AudioClipAsset
    from termin.default_assets.audio.handle import AudioClipHandle
    from termin.default_assets.mesh.asset import MeshAsset
    from termin.default_assets.navmesh.asset import NavMeshAsset
    from termin.default_assets.render.material_asset import MaterialAsset
    from termin.default_assets.render.pipeline_asset import PipelineAsset
    from termin.default_assets.render.shader_asset import ShaderAsset
    from termin.default_assets.render.texture_asset import TextureAsset
    from termin.default_assets.ui.handle import UIHandle
    from termin.default_assets.voxels.asset import VoxelGridAsset
    from termin.glb.asset import GLBAsset
    from termin.materials import ShaderMultyPhaseProgramm
    from termin.materials import TcMaterial as Material
    from termin.navmesh._navmesh_native import TcNavMesh
    from termin.navmesh.types import NavMesh
    from termin.prefab.asset import PrefabAsset
    from termin.render.texture import Texture
    from termin.scene import Entity, GeneralTransform3, TcScene
    from termin.render_framework import RenderPipeline
    from tgfx import TcShaderProgram
    from termin.voxels._voxels_native import TcVoxelGrid
    from termin.voxels.grid import VoxelGrid
    from termin.skeleton import TcSkeleton
    from termin.skeleton.asset import SkeletonAsset
    from tgfx import TcTexture
    from tmesh import TcMesh


class DefaultAssetResourceMixin:
    """Public ResourceManager methods for asset types owned by default-assets."""

    # --------- Built-ins ---------
    def register_builtin_shaders(self) -> None:
        """Register built-in shader dependencies."""
        from termin.default_assets.builtin_resources import register_builtin_shaders

        register_builtin_shaders(self)

    def register_builtin_materials(self) -> None:
        """Register built-in material dependencies."""
        from termin.default_assets.builtin_resources import register_builtin_materials

        register_builtin_materials(self)

    def register_builtin_textures(self) -> None:
        """Register built-in placeholder textures."""
        from termin.default_assets.builtin_resources import register_builtin_textures

        register_builtin_textures(self)

    def register_builtin_meshes(self) -> list[str]:
        """Register built-in primitive meshes."""
        from termin.default_assets.builtin_resources import register_builtin_meshes

        return register_builtin_meshes(self)

    def register_builtin_pipelines(self) -> None:
        """Register built-in render pipelines."""
        from termin.default_assets.builtin_resources import (
            register_default_pipeline,
            register_triangle_pipeline,
        )

        register_default_pipeline(self)
        register_triangle_pipeline(self)

    # --------- Prefabs ---------
    def get_prefab_asset(self, name: str) -> Optional["PrefabAsset"]:
        """Get PrefabAsset by name."""
        return self._prefab_registry.get_asset(name)

    def get_prefab(self, name: str) -> Optional["PrefabAsset"]:
        """Get PrefabAsset by name (alias for get_prefab_asset)."""
        return self._prefab_registry.get(name)

    def get_prefab_by_uuid(self, uuid: str) -> Optional["PrefabAsset"]:
        """Get PrefabAsset by UUID."""
        return self._prefab_registry.get_asset_by_uuid(uuid)

    def register_prefab(
        self,
        name: str,
        asset: "PrefabAsset",
        source_path: str | None = None,
    ) -> None:
        """Register a PrefabAsset."""
        self._prefab_registry.register(name, asset, source_path=source_path)

    def list_prefab_names(self) -> list[str]:
        """List all registered prefab names."""
        return self._prefab_registry.list_names()

    def find_prefab_name(self, asset: "PrefabAsset") -> Optional[str]:
        """Find name of a PrefabAsset."""
        return self._prefab_registry.find_name(asset)

    def find_prefab_uuid(self, asset: "PrefabAsset") -> Optional[str]:
        """Find UUID of a PrefabAsset."""
        return self._prefab_registry.find_uuid(asset)

    def instantiate_prefab(
        self,
        name_or_uuid: str,
        scene: "TcScene | None" = None,
        parent: "GeneralTransform3 | None" = None,
        position: tuple[float, float, float] | None = None,
        instance_name: str | None = None,
    ) -> Optional["Entity"]:
        """Instantiate a prefab by name or UUID."""
        asset = self.get_prefab_asset(name_or_uuid)
        if asset is None:
            asset = self.get_prefab_by_uuid(name_or_uuid)
        if asset is None:
            return None
        if not asset.is_loaded:
            asset.ensure_loaded()
        return asset.instantiate(
            scene=scene,
            parent=parent,
            position=position,
            name=instance_name,
        )

    def unregister_prefab(self, name: str) -> None:
        """Remove prefab by name."""
        self._prefab_registry.unregister(name)

    # --------- GLB ---------
    def get_glb_asset(self, name: str) -> Optional["GLBAsset"]:
        """Get GLBAsset by name."""
        return self._glb_registry.get_asset(name)

    def get_glb_asset_by_uuid(self, uuid: str) -> Optional["GLBAsset"]:
        """Get GLBAsset by UUID."""
        return self._glb_registry.get_asset_by_uuid(uuid)

    def register_glb_asset(
        self,
        name: str,
        asset: "GLBAsset",
        source_path: str | None = None,
    ) -> None:
        """Register a GLBAsset."""
        self._glb_registry.register(name, asset, source_path=source_path)

    def unregister_glb_asset(self, name: str) -> None:
        """Remove a GLBAsset by name."""
        self._glb_registry.unregister(name)

    def list_glb_names(self) -> list[str]:
        """List all registered GLB asset names."""
        return self._glb_registry.list_names()

    # --------- Materials ---------
    def get_material_asset(self, name: str) -> Optional["MaterialAsset"]:
        """Get MaterialAsset by name."""
        return self._material_registry.get_asset(name)

    def register_material_asset(
        self,
        name: str,
        asset: "MaterialAsset",
        source_path: str | None = None,
        uuid: str | None = None,
    ) -> None:
        """Register MaterialAsset."""
        material = asset.cached_data
        if material is not None and material.uuid != asset.uuid:
            log.error(
                f"[DefaultResourceManager] Material asset UUID '{asset.uuid}' "
                f"does not match TcMaterial UUID '{material.uuid}'"
            )
            raise ValueError("Material asset and native handle UUIDs must match")
        self._material_registry.register(name, asset, source_path=source_path, uuid=uuid)

    def register_material(
        self,
        name: str,
        mat: "Material",
        source_path: str | None = None,
        uuid: str | None = None,
    ) -> None:
        """Register a material."""
        from termin.default_assets.render.material_asset import MaterialAsset

        if uuid is not None and uuid != mat.uuid:
            log.error(
                f"[DefaultResourceManager] Requested material UUID '{uuid}' "
                f"does not match TcMaterial UUID '{mat.uuid}'"
            )
            raise ValueError("Material asset and native handle UUIDs must match")
        asset = MaterialAsset.from_material(mat, name=name, source_path=source_path, uuid=uuid)
        self.register_material_asset(name, asset, source_path=source_path, uuid=uuid)

    def list_material_names(self) -> list[str]:
        return self._material_registry.list_names()

    def find_material_name(self, mat: "Material") -> Optional[str]:
        return self._material_registry.find_name(mat)

    def find_material_uuid(self, mat: "Material") -> Optional[str]:
        return self._material_registry.find_uuid(mat)

    def get_material_asset_by_uuid(self, uuid: str) -> Optional["MaterialAsset"]:
        """Get MaterialAsset by UUID."""
        return self._material_registry.get_asset_by_uuid(uuid)

    def get_material(self, name: str) -> "Material":
        """Get material by name, loading lazily and returning UnknownMaterial on miss."""
        from termin.materials import material_or_unknown

        asset = self._material_registry.get_asset(name)
        if asset is None:
            return material_or_unknown(None, name)
        if asset.material is None:
            if not asset.ensure_loaded():
                return material_or_unknown(None, name)
        from termin.materials import TcMaterial

        material = TcMaterial.from_uuid(asset.uuid)
        return material_or_unknown(material if material.is_valid else None, name)

    def get_material_by_uuid(self, uuid: str) -> "Material":
        """Get material by UUID, loading lazily and returning UnknownMaterial on miss."""
        from termin.materials import material_or_unknown

        asset: "MaterialAsset | None" = self._material_registry.get_asset_by_uuid(uuid)
        if asset is None:
            return material_or_unknown(None, f"uuid:{uuid}")
        if asset.material is None:
            if not asset.ensure_loaded():
                return material_or_unknown(None, asset.name or f"uuid:{uuid}")
        from termin.materials import TcMaterial

        material = TcMaterial.from_uuid(uuid)
        return material_or_unknown(
            material if material.is_valid else None,
            asset.name or f"uuid:{uuid}",
        )

    # --------- Shaders ---------
    def get_shader_asset(self, name: str) -> Optional["ShaderAsset"]:
        """Get ShaderAsset by name."""
        return self._shader_registry.get_asset(name)

    def register_shader_asset(
        self,
        name: str,
        asset: "ShaderAsset",
        source_path: str | None = None,
        uuid: str | None = None,
    ) -> None:
        """Register ShaderAsset."""
        self._shader_registry.register(name, asset, source_path=source_path, uuid=uuid)

    def register_shader(
        self,
        name: str,
        shader: "ShaderMultyPhaseProgramm",
        source_path: str | None = None,
        uuid: str | None = None,
    ) -> None:
        """Register a shader."""
        from termin.default_assets.render.shader_asset import ShaderAsset

        asset = ShaderAsset.from_program(shader, name=name, source_path=source_path, uuid=uuid)
        self.register_shader_asset(name, asset, source_path=source_path, uuid=uuid)
        if source_path:
            shader.source_path = source_path

    def get_shader(self, name: str) -> Optional["TcShaderProgram"]:
        """Get the canonical shader program by unique catalog name."""
        asset = self._shader_registry.get_asset(name)
        if asset is None:
            return None
        if asset.program is None:
            if not asset.ensure_loaded():
                return None
        return asset.program

    def get_shader_by_uuid(self, uuid: str) -> Optional["TcShaderProgram"]:
        """Get the canonical shader program by UUID (lazy loading)."""
        asset = self._shader_registry.get_asset_by_uuid(uuid)
        if asset is None:
            return None
        if asset.program is None:
            if not asset.ensure_loaded():
                return None
        return asset.program

    def list_shader_names(self) -> list[str]:
        return self._shader_registry.list_names()

    # --------- Meshes ---------
    def get_mesh_asset(self, name: str) -> Optional["MeshAsset"]:
        """Get MeshAsset by name."""
        return self._mesh_registry.get_asset(name)

    def register_mesh_asset(
        self,
        name: str,
        asset: "MeshAsset",
        source_path: str | None = None,
        uuid: str | None = None,
    ) -> None:
        """Register MeshAsset."""
        self._mesh_registry.register(name, asset, source_path, uuid)

    def get_mesh(self, name: str) -> Optional["TcMesh"]:
        """Get TcMesh by name."""
        return self._mesh_registry.get(name)

    def list_mesh_names(self) -> list[str]:
        return self._mesh_registry.list_names()

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
        from termin.default_assets.voxels.asset import VoxelGridAsset
        grid.name = name
        existing_asset = self._voxel_grid_registry.get_asset(name)
        if existing_asset is not None:
            existing_asset.data = grid
            return
        asset = VoxelGridAsset.from_grid(grid, name=name, source_path=source_path)
        self._voxel_grid_registry.register(name, asset, source_path)

    def get_voxel_grid(self, name: str) -> Optional["TcVoxelGrid"]:
        """Get voxel grid by name (lazy loading)."""
        asset = self._voxel_grid_registry.get_asset(name)
        if asset is None:
            return None
        return self.get_voxel_grid_by_uuid(asset.uuid)

    def list_voxel_grid_names(self) -> list[str]:
        return self._voxel_grid_registry.list_names()

    def find_voxel_grid_name(self, grid: "TcVoxelGrid") -> Optional[str]:
        return self._voxel_grid_registry.find_name(grid)

    def find_voxel_grid_uuid(self, grid: "TcVoxelGrid") -> Optional[str]:
        return self._voxel_grid_registry.find_uuid(grid)

    def get_voxel_grid_by_uuid(self, uuid: str) -> Optional["TcVoxelGrid"]:
        asset = self._voxel_grid_registry.get_asset_by_uuid(uuid)
        if asset is None:
            return None
        from termin.voxels._voxels_native import TcVoxelGrid

        grid = TcVoxelGrid.from_uuid(uuid)
        if not grid.is_valid and asset.ensure_loaded():
            grid = TcVoxelGrid.from_uuid(uuid)
        return grid if grid.is_valid else None

    def get_voxel_grid_asset_by_uuid(self, uuid: str) -> Optional["VoxelGridAsset"]:
        return self._voxel_grid_registry.get_asset_by_uuid(uuid)

    def unregister_voxel_grid(self, name: str) -> None:
        self._voxel_grid_registry.unregister(name)

    # --------- NavMeshes ---------
    def get_navmesh_asset(self, name: str) -> Optional["NavMeshAsset"]:
        return self._navmesh_registry.get_asset(name)

    def register_navmesh(self, name: str, navmesh: "NavMesh", source_path: str | None = None) -> None:
        from termin.default_assets.navmesh.asset import NavMeshAsset
        navmesh.name = name
        asset = NavMeshAsset.from_navmesh(navmesh, name=name, source_path=source_path)
        self._navmesh_registry.register(name, asset, source_path)

    def get_navmesh(self, name: str) -> Optional["TcNavMesh"]:
        asset = self._navmesh_registry.get_asset(name)
        if asset is None:
            return None
        return self.get_navmesh_by_uuid(asset.uuid)

    def list_navmesh_names(self) -> list[str]:
        return self._navmesh_registry.list_names()

    def find_navmesh_name(self, navmesh: "TcNavMesh") -> Optional[str]:
        return self._navmesh_registry.find_name(navmesh)

    def find_navmesh_uuid(self, navmesh: "TcNavMesh") -> Optional[str]:
        return self._navmesh_registry.find_uuid(navmesh)

    def get_navmesh_by_uuid(self, uuid: str) -> Optional["TcNavMesh"]:
        asset = self._navmesh_registry.get_asset_by_uuid(uuid)
        if asset is None:
            return None
        from termin.navmesh._navmesh_native import TcNavMesh

        navmesh = TcNavMesh.from_uuid(uuid)
        if not navmesh.is_valid and asset.ensure_loaded():
            navmesh = TcNavMesh.from_uuid(uuid)
        return navmesh if navmesh.is_valid else None

    def get_navmesh_asset_by_uuid(self, uuid: str) -> Optional["NavMeshAsset"]:
        return self._navmesh_registry.get_asset_by_uuid(uuid)

    def unregister_navmesh(self, name: str) -> None:
        self._navmesh_registry.unregister(name)

    # --------- Animation Clips ---------
    def get_animation_clip_asset(self, name: str) -> Optional["AnimationClipAsset"]:
        return self._animation_clip_registry.get_asset(name)

    def register_animation_clip(
        self,
        name: str,
        clip: "TcAnimationClip",
        source_path: str | None = None,
        uuid: str | None = None,
    ) -> None:
        from termin.animation.asset import AnimationClipAsset

        asset_uuid = uuid or clip.uuid
        if asset_uuid != clip.uuid:
            log.error(
                f"[DefaultResourceManager] Requested animation UUID '{asset_uuid}' "
                f"does not match TcAnimationClip UUID '{clip.uuid}'"
            )
            raise ValueError("Animation asset and native handle UUIDs must match")
        asset = AnimationClipAsset(
            clip=clip,
            name=name,
            source_path=source_path,
            uuid=asset_uuid,
        )
        self._animation_clip_registry.register(name, asset, source_path, asset_uuid)

    def get_animation_clip(self, name: str) -> Optional["TcAnimationClip"]:
        asset = self._animation_clip_registry.get_asset(name)
        if asset is None:
            return None
        return self.get_animation_clip_by_uuid(asset.uuid)

    def get_animation_clip_by_uuid(self, uuid: str) -> Optional["TcAnimationClip"]:
        asset = self._animation_clip_registry.get_asset_by_uuid(uuid)
        if asset is None:
            return None
        from termin.animation import TcAnimationClip

        clip = TcAnimationClip.from_uuid(uuid)
        if not clip.is_valid and asset.ensure_loaded():
            clip = TcAnimationClip.from_uuid(uuid)
        return clip if clip.is_valid else None

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

    # --------- Skeletons ---------
    def get_skeleton_asset(self, name: str) -> Optional["SkeletonAsset"]:
        return self._skeleton_registry.get_asset(name)

    def register_skeleton(
        self,
        name: str,
        skeleton: "TcSkeleton",
        source_path: str | None = None,
        uuid: str | None = None,
    ) -> None:
        from termin.skeleton.asset import SkeletonAsset

        asset_uuid = uuid or skeleton.uuid
        if asset_uuid != skeleton.uuid:
            log.error(
                f"[DefaultResourceManager] Requested skeleton UUID '{asset_uuid}' "
                f"does not match TcSkeleton UUID '{skeleton.uuid}'"
            )
            raise ValueError("Skeleton asset and native handle UUIDs must match")
        asset = SkeletonAsset.from_tc_skeleton(
            skeleton,
            name=name,
            source_path=source_path,
            uuid=asset_uuid,
        )
        self._skeleton_registry.register(name, asset, source_path, asset_uuid)

    def get_skeleton(self, name: str) -> Optional["TcSkeleton"]:
        asset = self._skeleton_registry.get_asset(name)
        if asset is None:
            return None
        return self.get_skeleton_by_uuid(asset.uuid)

    def list_skeleton_names(self) -> list[str]:
        return self._skeleton_registry.list_names()

    def find_skeleton_name(self, skeleton: "TcSkeleton") -> Optional[str]:
        return self._skeleton_registry.find_name(skeleton)

    def find_skeleton_uuid(self, skeleton: "TcSkeleton") -> Optional[str]:
        return self._skeleton_registry.find_uuid(skeleton)

    def get_skeleton_by_uuid(self, uuid: str) -> Optional["TcSkeleton"]:
        asset = self._skeleton_registry.get_asset_by_uuid(uuid)
        if asset is None:
            return None
        from termin.skeleton import TcSkeleton

        skeleton = TcSkeleton.from_uuid(uuid)
        if not skeleton.is_valid and asset.ensure_loaded():
            skeleton = TcSkeleton.from_uuid(uuid)
        return skeleton if skeleton.is_valid else None

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

    # --------- Audio Clips ---------
    def get_audio_clip_asset(self, name: str) -> Optional["AudioClipAsset"]:
        return self._audio_clip_registry.get_asset(name)

    def get_audio_clip(self, name: str) -> Optional["AudioClipHandle"]:
        return self._audio_clip_registry.get(name)

    def register_audio_clip_asset(
        self,
        name: str,
        asset: "AudioClipAsset",
        source_path: str | None = None,
        uuid: str | None = None,
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
        self,
        name: str,
        source_path: str | None = None,
        uuid: str | None = None,
    ) -> "AudioClipAsset":
        return self._audio_clip_registry.get_or_create_asset(name=name, source_path=source_path, uuid=uuid)

    def unregister_audio_clip(self, name: str) -> None:
        self._audio_clip_registry.unregister(name)

    # --------- UI Layouts ---------
    def get_ui_asset(self, name: str):
        return self._ui_registry.get_asset(name)

    def get_ui_handle(self, name: str) -> Optional["UIHandle"]:
        from termin.default_assets.ui.handle import UIHandle

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

    def get_texture_asset_by_uuid(self, uuid: str) -> Optional["TextureAsset"]:
        """Get TextureAsset by UUID."""
        from termin.default_assets.render.texture_asset import TextureAsset

        asset = self.get_asset_by_uuid(uuid)
        if isinstance(asset, TextureAsset):
            return asset
        return None

    def get_texture_handle(self, name: str) -> Optional["TcTexture"]:
        return self._texture_registry.get(name)

    def get_texture(self, name: str) -> Optional["Texture"]:
        from termin.render.texture import Texture

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
        self._texture_registry.register(name, asset, source_path, uuid)

    def list_texture_names(self) -> list[str]:
        return self._texture_registry.list_names()

    def find_texture_name(self, texture) -> Optional[str]:
        from tgfx import TcTexture

        if isinstance(texture, TcTexture):
            tex_uuid = texture.uuid
            if tex_uuid:
                for asset in self._texture_registry.iter_assets():
                    if asset.uuid == tex_uuid:
                        return asset.name
            tex_name = texture.name
            if tex_name and self._texture_registry.get_asset(tex_name) is not None:
                return tex_name
            return None
        for name, asset in self._texture_assets.items():
            if asset is texture:
                return name
        return None

    def unregister_texture(self, name: str) -> None:
        self._texture_registry.unregister(name)

    # --------- Render Pipelines ---------
    def register_pipeline(self, name: str, pipeline: "RenderPipeline", uuid: str | None = None) -> None:
        """Register a RenderPipeline by name."""
        from termin.default_assets.render.pipeline_asset import PipelineAsset

        asset = self._pipeline_registry.get_asset(name)
        if asset is not None:
            candidate = asset._candidate_from_pipeline(pipeline, source_format="runtime")
            if not asset._publish_candidate(candidate):
                raise RuntimeError(f"failed to update registered pipeline '{name}'")
            pipeline.destroy()
            return

        asset = PipelineAsset.from_pipeline(pipeline, name=name, uuid=uuid)
        self._pipeline_registry.register(name, asset, uuid=uuid)
        pipeline.destroy()

    def get_pipeline(self, name: str) -> Optional["RenderPipeline"]:
        """Instantiate a mutable RenderPipeline from its canonical resource."""
        asset = self._pipeline_registry.get_asset(name)
        return asset.pipeline if asset is not None else None

    def get_pipeline_asset(self, name: str) -> Optional["PipelineAsset"]:
        """Get PipelineAsset by name."""
        return self._pipeline_registry.get_asset(name)

    def get_pipeline_by_uuid(self, uuid: str) -> Optional["RenderPipeline"]:
        """Instantiate a mutable RenderPipeline by canonical UUID."""
        asset = self._pipeline_registry.get_asset_by_uuid(uuid)
        return asset.pipeline if asset is not None else None

    def list_pipeline_names(self) -> list[str]:
        """List all registered pipeline names."""
        return sorted(self._pipeline_registry.list_names())
