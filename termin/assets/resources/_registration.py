"""PreLoadResult-based file registration mixin."""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin._native import log

if TYPE_CHECKING:
    from termin.editor.project_file_watcher import PreLoadResult
    from termin.assets.glb_asset import GLBAsset


class RegistrationMixin:
    """Mixin for PreLoadResult-based file registration."""

    def register_file(self, result: "PreLoadResult") -> None:
        """
        Register a file from PreLoadResult.

        If UUID exists and is registered -> uses existing Asset.
        Otherwise -> creates new Asset.
        Then calls Asset.ensure_loaded() with content from result.
        """
        import os

        # For glsl files, keep the extension (used in #include "lighting.glsl")
        if result.resource_type == "glsl":
            name = os.path.basename(result.path)
        else:
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
        elif result.resource_type == "prefab":
            self._register_prefab_file(name, result)
        elif result.resource_type == "audio_clip":
            self._register_audio_clip_file(name, result)
        elif result.resource_type == "ui":
            self._register_ui_file(name, result)
        elif result.resource_type == "pipeline":
            self._register_pipeline_file(name, result)
        elif result.resource_type == "scene_pipeline":
            self._register_scene_pipeline_file(name, result)
        else:
            log.warn(f"[ResourceManager] Unknown resource type: {result.resource_type}")

    def reload_file(self, result: "PreLoadResult") -> None:
        """
        Reload a file from PreLoadResult.

        Finds existing Asset and calls load() with new content.
        """
        import os

        # For glsl files, keep the extension (used in #include "lighting.glsl")
        if result.resource_type == "glsl":
            name = os.path.basename(result.path)
        else:
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
        elif result.resource_type == "prefab":
            self._reload_prefab_file(name, result)
        elif result.resource_type == "audio_clip":
            self._reload_audio_clip_file(name, result)
        elif result.resource_type == "ui":
            self._reload_ui_file(name, result)
        elif result.resource_type == "pipeline":
            self._reload_pipeline_file(name, result)
        elif result.resource_type == "scene_pipeline":
            self._reload_scene_pipeline_file(name, result)
        else:
            log.warn(f"[ResourceManager] Unknown resource type for reload: {result.resource_type}")

    def _register_material_file(self, name: str, result: "PreLoadResult") -> None:
        """Register material from PreLoadResult."""
        from termin.assets.material_asset import MaterialAsset

        if name in self._material_assets:
            return

        asset = None
        if result.uuid:
            asset = self._assets_by_uuid.get(result.uuid)
            if asset is not None and not isinstance(asset, MaterialAsset):
                asset = None

        if asset is None:
            asset = MaterialAsset(
                material=None,
                name=name,
                source_path=result.path,
                uuid=result.uuid,
            )
            self._assets_by_uuid[asset.uuid] = asset

        self._material_assets[name] = asset
        asset.load_from_content(result.content)

        if asset.material is not None:
            self.materials[name] = asset.material

    def _reload_material_file(self, name: str, result: "PreLoadResult") -> None:
        """Reload material from PreLoadResult."""
        asset = self._material_assets.get(name)
        if asset is None:
            return

        if not asset.is_loaded:
            return

        if not asset.should_reload_from_file():
            return

        asset.reload()

        if asset.material is not None:
            self.materials[name] = asset.material

    def _register_shader_file(self, name: str, result: "PreLoadResult") -> None:
        """Register shader from PreLoadResult (lazy loading)."""
        from termin.assets.shader_asset import ShaderAsset

        if name in self._shader_assets:
            return

        asset = None
        if result.uuid:
            asset = self._assets_by_uuid.get(result.uuid)
            if asset is not None and not isinstance(asset, ShaderAsset):
                asset = None

        if asset is None:
            asset = ShaderAsset(
                program=None,
                name=name,
                source_path=result.path,
            )

        asset.parse_spec(result.spec_data)
        self._assets_by_uuid[asset.uuid] = asset
        self._shader_assets[name] = asset

    def _reload_shader_file(self, name: str, result: "PreLoadResult") -> None:
        """Reload shader from PreLoadResult."""
        asset = self._shader_assets.get(name)
        if asset is None:
            return

        if not asset.is_loaded:
            return

        if not asset.should_reload_from_file():
            return

        asset.parse_spec(result.spec_data)
        asset.reload()

        if asset.program is not None:
            self.shaders[name] = asset.program

    def _register_texture_file(self, name: str, result: "PreLoadResult") -> None:
        """Register texture from PreLoadResult (lazy loading)."""
        from termin.assets.texture_asset import TextureAsset

        if name in self._texture_assets:
            return

        asset = None
        if result.uuid:
            asset = self._assets_by_uuid.get(result.uuid)
            if asset is not None and not isinstance(asset, TextureAsset):
                asset = None

        if asset is None:
            asset = TextureAsset(
                texture_data=None,
                name=name,
                source_path=result.path,
            )

        asset.parse_spec(result.spec_data)
        self._assets_by_uuid[asset.uuid] = asset
        self._texture_assets[name] = asset

    def _reload_texture_file(self, name: str, result: "PreLoadResult") -> None:
        """Reload texture from PreLoadResult."""
        asset = self._texture_assets.get(name)
        if asset is None:
            return

        if not asset.is_loaded:
            return

        if not asset.should_reload_from_file():
            return

        asset.parse_spec(result.spec_data)
        asset.reload()
        asset.delete_gpu()

    def _register_mesh_file(self, name: str, result: "PreLoadResult") -> None:
        """Register mesh from PreLoadResult."""
        from termin.assets.mesh_asset import MeshAsset

        if name in self._mesh_assets:
            return

        asset = None
        if result.uuid:
            asset = self._assets_by_uuid.get(result.uuid)
            if asset is not None and not isinstance(asset, MeshAsset):
                asset = None

        if asset is None:
            asset = MeshAsset(
                mesh_data=None,
                name=name,
                source_path=result.path,
            )

        asset.parse_spec(result.spec_data)
        self._assets_by_uuid[asset.uuid] = asset
        self._mesh_assets[name] = asset

    def _reload_mesh_file(self, name: str, result: "PreLoadResult") -> None:
        """Reload mesh from PreLoadResult."""
        asset = self._mesh_assets.get(name)
        if asset is None:
            return

        if not asset.is_loaded:
            return

        if not asset.should_reload_from_file():
            return

        asset.parse_spec(result.spec_data)
        asset.reload()
        asset.delete_gpu()

    def _register_voxel_grid_file(self, name: str, result: "PreLoadResult") -> None:
        """Register voxel grid from PreLoadResult."""
        from termin.assets.voxel_grid_asset import VoxelGridAsset

        if name in self._voxel_grid_assets:
            return

        asset = None
        if result.uuid:
            asset = self._assets_by_uuid.get(result.uuid)
            if asset is not None and not isinstance(asset, VoxelGridAsset):
                asset = None

        if asset is None:
            asset = VoxelGridAsset(
                grid=None,
                name=name,
                source_path=result.path,
            )

        asset.parse_spec(result.spec_data)
        self._assets_by_uuid[asset.uuid] = asset
        self._voxel_grid_assets[name] = asset

    def _reload_voxel_grid_file(self, name: str, result: "PreLoadResult") -> None:
        """Reload voxel grid from PreLoadResult."""
        asset = self._voxel_grid_assets.get(name)
        if asset is None:
            return

        if not asset.is_loaded:
            return

        if not asset.should_reload_from_file():
            return

        asset.parse_spec(result.spec_data)
        asset.reload()

        if asset.grid is not None:
            self.voxel_grids[name] = asset.grid

    def _register_navmesh_file(self, name: str, result: "PreLoadResult") -> None:
        """Register navmesh from PreLoadResult."""
        from termin.assets.navmesh_asset import NavMeshAsset

        if name in self._navmesh_assets:
            return

        asset = None
        if result.uuid:
            asset = self._assets_by_uuid.get(result.uuid)
            if asset is not None and not isinstance(asset, NavMeshAsset):
                asset = None

        if asset is None:
            asset = NavMeshAsset(
                navmesh=None,
                name=name,
                source_path=result.path,
            )

        asset.parse_spec(result.spec_data)
        self._assets_by_uuid[asset.uuid] = asset
        self._navmesh_assets[name] = asset

    def _reload_navmesh_file(self, name: str, result: "PreLoadResult") -> None:
        """Reload navmesh from PreLoadResult."""
        asset = self._navmesh_assets.get(name)
        if asset is None:
            return

        if not asset.is_loaded:
            return

        if not asset.should_reload_from_file():
            return

        asset.parse_spec(result.spec_data)
        asset.reload()

        if asset.navmesh is not None:
            self.navmeshes[name] = asset.navmesh

    def _register_glb_file(self, name: str, result: "PreLoadResult") -> None:
        """Register GLB from PreLoadResult."""
        from termin.assets.glb_asset import GLBAsset

        if name in self._glb_assets:
            return

        asset = None
        if result.uuid:
            asset = self._assets_by_uuid.get(result.uuid)
            if asset is not None and not isinstance(asset, GLBAsset):
                asset = None

        if asset is None:
            asset = GLBAsset(
                scene_data=None,
                name=name,
                source_path=result.path,
            )

        asset.parse_spec(result.spec_data)
        self._assets_by_uuid[asset.uuid] = asset
        self._glb_assets[name] = asset
        self._register_glb_child_assets(asset)

    def _register_glb_child_assets(self, glb_asset: "GLBAsset") -> None:
        """Register child assets from GLBAsset (meshes, skeletons, animations)."""
        mesh_assets = glb_asset.get_mesh_assets()
        for mesh_name, mesh_asset in mesh_assets.items():
            full_name = mesh_asset.name
            if full_name not in self._mesh_assets:
                self._mesh_assets[full_name] = mesh_asset
                self._assets_by_uuid[mesh_asset.uuid] = mesh_asset

        for skeleton_key, skeleton_asset in glb_asset.get_skeleton_assets().items():
            skeleton_name = skeleton_asset.name
            if skeleton_name not in self._skeleton_assets:
                self._skeleton_assets[skeleton_name] = skeleton_asset
                self._assets_by_uuid[skeleton_asset.uuid] = skeleton_asset

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

        if not asset.is_loaded:
            return

        if not asset.should_reload_from_file():
            return

        asset.parse_spec(result.spec_data)
        asset.reload()
        self._register_glb_child_assets(asset)

    def _register_glsl_file(self, name: str, result: "PreLoadResult") -> None:
        """Register GLSL include file from PreLoadResult."""
        from termin.assets.glsl_asset import GlslAsset

        uuid = result.spec_data.get("uuid") if result.spec_data else None
        if uuid and uuid in self._assets_by_uuid:
            asset = self._assets_by_uuid[uuid]
            if isinstance(asset, GlslAsset):
                self._glsl_registry.assets[name] = asset
                asset.parse_spec(result.spec_data)
                return

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

        if not asset.should_reload_from_file():
            return

        asset.parse_spec(result.spec_data)
        if not asset.is_loaded:
            asset.ensure_loaded()
        else:
            asset.reload()

    def _register_prefab_file(self, name: str, result: "PreLoadResult") -> None:
        """Register prefab from PreLoadResult."""
        from termin.assets.prefab_asset import PrefabAsset

        if name in self._prefab_assets:
            return

        asset = None
        if result.uuid:
            asset = self._assets_by_uuid.get(result.uuid)
            if asset is not None and not isinstance(asset, PrefabAsset):
                asset = None

        if asset is None:
            asset = PrefabAsset(
                data=None,
                name=name,
                source_path=result.path,
                uuid=result.uuid,
            )
            self._assets_by_uuid[asset.uuid] = asset

        self._prefab_assets[name] = asset

    def _reload_prefab_file(self, name: str, result: "PreLoadResult") -> None:
        """Reload prefab from PreLoadResult (hot-reload)."""
        from termin.assets.prefab_asset import PrefabAsset

        asset = self._prefab_assets.get(name)
        if asset is None:
            return

        if not asset.is_loaded:
            return

        if not asset.should_reload_from_file():
            return

        new_asset = PrefabAsset.from_file(result.path, name=name)
        asset.update_from(new_asset)

    def _register_audio_clip_file(self, name: str, result: "PreLoadResult") -> None:
        """Register audio clip from PreLoadResult (lazy loading)."""
        from termin.assets.audio_clip_asset import AudioClipAsset

        if name in self._audio_clip_assets:
            return

        asset = None
        if result.uuid:
            asset = self._assets_by_uuid.get(result.uuid)
            if asset is not None and not isinstance(asset, AudioClipAsset):
                asset = None

        if asset is None:
            asset = AudioClipAsset(
                name=name,
                source_path=result.path,
                uuid=result.uuid,
            )
            self._assets_by_uuid[asset.uuid] = asset

        self._audio_clip_assets[name] = asset

    def _reload_audio_clip_file(self, name: str, result: "PreLoadResult") -> None:
        """Reload audio clip from PreLoadResult."""
        asset = self._audio_clip_assets.get(name)
        if asset is None:
            return

        if not asset.is_loaded:
            return

        if not asset.should_reload_from_file():
            return

        asset.reload()

    def _register_ui_file(self, name: str, result: "PreLoadResult") -> None:
        """Register UI layout from PreLoadResult."""
        from termin.assets.ui_asset import UIAsset

        if name in self._ui_assets:
            return

        asset = None
        if result.uuid:
            asset = self._assets_by_uuid.get(result.uuid)
            if asset is not None and not isinstance(asset, UIAsset):
                asset = None

        if asset is None:
            asset = UIAsset(
                widget=None,
                name=name,
                source_path=result.path,
            )

        asset.parse_spec(result.spec_data)
        self._assets_by_uuid[asset.uuid] = asset
        self._ui_assets[name] = asset

    def _reload_ui_file(self, name: str, result: "PreLoadResult") -> None:
        """Reload UI layout from PreLoadResult."""
        asset = self._ui_assets.get(name)
        if asset is None:
            return

        if not asset.is_loaded:
            return

        if not asset.should_reload_from_file():
            return

        asset.reload()

    def _register_pipeline_file(self, name: str, result: "PreLoadResult") -> None:
        """Register pipeline from PreLoadResult."""
        from termin.assets.pipeline_asset import PipelineAsset

        uuid = result.spec_data.get("uuid") if result.spec_data else None
        if uuid and uuid in self._assets_by_uuid:
            asset = self._assets_by_uuid[uuid]
            if isinstance(asset, PipelineAsset):
                self._pipeline_registry.assets[name] = asset
                asset.parse_spec(result.spec_data)
                return

        asset = self._pipeline_registry.get_or_create_asset(
            name=name,
            source_path=result.path,
            uuid=uuid,
        )
        asset.parse_spec(result.spec_data)

    def _reload_pipeline_file(self, name: str, result: "PreLoadResult") -> None:
        """Reload pipeline from PreLoadResult."""
        asset = self._pipeline_registry.get_asset(name)
        if asset is None:
            return

        if not asset.is_loaded:
            return

        if not asset.should_reload_from_file():
            return

        asset.parse_spec(result.spec_data)
        asset.reload()

    def _register_scene_pipeline_file(self, name: str, result: "PreLoadResult") -> None:
        """Register scene pipeline from PreLoadResult."""
        from termin.assets.scene_pipeline_asset import ScenePipelineAsset

        # UUID may be in the JSON content (already extracted by preloader)
        uuid = result.uuid
        if uuid and uuid in self._assets_by_uuid:
            asset = self._assets_by_uuid[uuid]
            if isinstance(asset, ScenePipelineAsset):
                self._scene_pipeline_registry.assets[name] = asset
                if result.content:
                    asset.load_from_content(result.content, result.spec_data)
                return

        asset = self._scene_pipeline_registry.get_or_create_asset(
            name=name,
            source_path=result.path,
            uuid=uuid,
        )
        if result.content:
            asset.load_from_content(result.content, result.spec_data)

    def _reload_scene_pipeline_file(self, name: str, result: "PreLoadResult") -> None:
        """Reload scene pipeline from PreLoadResult."""
        asset = self._scene_pipeline_registry.get_asset(name)
        if asset is None:
            return

        if not asset.is_loaded:
            return

        if not asset.should_reload_from_file():
            return

        if result.content:
            asset.load_from_content(result.content, result.spec_data)
        else:
            asset.reload()
