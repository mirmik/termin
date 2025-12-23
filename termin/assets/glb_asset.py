"""GLBAsset - Asset for GLB 3D model files."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Dict, List

from termin.assets.data_asset import DataAsset

if TYPE_CHECKING:
    from termin.loaders.glb_loader import GLBSceneData
    from termin.visualization.core.mesh_asset import MeshAsset
    from termin.skeleton.skeleton_asset import SkeletonAsset
    from termin.visualization.animation.animation_clip_asset import AnimationClipAsset


class GLBAsset(DataAsset["GLBSceneData"]):
    """
    Asset for GLB model files.

    IMPORTANT: Create through ResourceManager, not directly.
    This ensures proper registration and avoids duplicates.

    GLBAsset is a container that holds:
    - GLBSceneData (raw loaded data)
    - Child MeshAssets for each mesh in the GLB
    - Child SkeletonAssets for each skin
    - Child AnimationClipAssets for each animation

    Child assets are requested from ResourceManager during spec parsing
    (via get_or_create_*_asset methods). GLBAsset never creates assets
    directly - only ResourceManager is allowed to create assets.
    """

    _uses_binary = True  # GLB is binary format

    def __init__(
        self,
        scene_data: "GLBSceneData | None" = None,
        name: str = "glb",
        source_path: Path | str | None = None,
        uuid: str | None = None,
    ):
        super().__init__(data=scene_data, name=name, source_path=source_path, uuid=uuid)

        # Spec settings
        self._normalize_scale: bool = False
        self._convert_to_z_up: bool = True
        self._blender_z_up_fix: bool = False

        # Child assets (created during spec parsing)
        self._mesh_assets: Dict[str, "MeshAsset"] = {}
        self._skeleton_assets: Dict[str, "SkeletonAsset"] = {}
        self._animation_assets: Dict[str, "AnimationClipAsset"] = {}

    # --- Convenience property ---

    @property
    def scene_data(self) -> "GLBSceneData | None":
        """GLB scene data (lazy-loaded)."""
        return self.data

    # --- Spec parsing ---

    def _parse_spec_fields(self, spec_data: dict) -> None:
        """Parse GLB-specific spec fields and create child assets."""
        # Parse settings
        self._normalize_scale = spec_data.get("normalize_scale", False)
        self._convert_to_z_up = spec_data.get("convert_to_z_up", True)
        self._blender_z_up_fix = spec_data.get("blender_z_up_fix", False)

        # Create child assets from resources section
        resources = spec_data.get("resources", {})
        self._create_mesh_assets(resources.get("meshes", {}))
        self._create_skeleton_assets(resources.get("skeletons", {}))
        self._create_animation_assets(resources.get("animations", {}))

    def _create_mesh_assets(self, mesh_uuids: Dict[str, str]) -> None:
        """Get or create child MeshAssets with UUIDs from spec via ResourceManager."""
        from termin.assets.resources import ResourceManager

        rm = ResourceManager.instance()
        for mesh_name, mesh_uuid in mesh_uuids.items():
            full_name = f"{self._name}_{mesh_name}"
            asset = rm.get_or_create_mesh_asset(
                name=full_name,
                source_path=str(self._source_path) if self._source_path else None,
                uuid=mesh_uuid,
                parent=self,
                parent_key=mesh_name,
            )
            self._mesh_assets[mesh_name] = asset

    def _create_skeleton_assets(self, skeleton_uuids: Dict[str, str]) -> None:
        """Get or create child SkeletonAssets with UUIDs from spec via ResourceManager."""
        from termin.assets.resources import ResourceManager

        rm = ResourceManager.instance()
        for skeleton_key, skeleton_uuid in skeleton_uuids.items():
            # skeleton_key is "skeleton" or "skeleton_N"
            idx = 0 if skeleton_key == "skeleton" else int(skeleton_key.split("_")[1])
            skeleton_name = f"{self._name}_skeleton" if idx == 0 else f"{self._name}_skeleton_{idx}"

            asset = rm.get_or_create_skeleton_asset(
                name=skeleton_name,
                source_path=str(self._source_path) if self._source_path else None,
                uuid=skeleton_uuid,
                parent=self,
                parent_key=skeleton_key,
            )
            self._skeleton_assets[skeleton_key] = asset

    def _create_animation_assets(self, animation_uuids: Dict[str, str]) -> None:
        """Get or create child AnimationClipAssets with UUIDs from spec via ResourceManager."""
        from termin.assets.resources import ResourceManager

        rm = ResourceManager.instance()
        for anim_name, anim_uuid in animation_uuids.items():
            full_name = f"{self._name}_{anim_name}"
            asset = rm.get_or_create_animation_clip_asset(
                name=full_name,
                source_path=str(self._source_path) if self._source_path else None,
                uuid=anim_uuid,
                parent=self,
                parent_key=anim_name,
            )
            self._animation_assets[anim_name] = asset

    def _build_spec_data(self) -> dict:
        """Build spec data with GLB settings and child UUIDs."""
        spec = super()._build_spec_data()

        # Settings (only non-defaults)
        if self._normalize_scale:
            spec["normalize_scale"] = True
        if not self._convert_to_z_up:
            spec["convert_to_z_up"] = False
        if self._blender_z_up_fix:
            spec["blender_z_up_fix"] = True

        # Child asset UUIDs
        resources: Dict[str, Dict[str, str]] = {}

        if self._mesh_assets:
            resources["meshes"] = {
                name: asset.uuid for name, asset in self._mesh_assets.items()
            }
        if self._skeleton_assets:
            resources["skeletons"] = {
                key: asset.uuid for key, asset in self._skeleton_assets.items()
            }
        if self._animation_assets:
            resources["animations"] = {
                name: asset.uuid for name, asset in self._animation_assets.items()
            }

        if resources:
            spec["resources"] = resources

        return spec

    # --- Content parsing ---

    def _parse_content(self, content: bytes) -> "GLBSceneData | None":
        """Parse GLB binary content."""
        from termin.loaders.glb_loader import load_glb_file_from_buffer

        return load_glb_file_from_buffer(
            content,
            normalize_scale=self._normalize_scale,
            convert_to_z_up=self._convert_to_z_up,
            blender_z_up_fix=self._blender_z_up_fix,
        )

    def _on_loaded(self) -> None:
        """After loading, create any missing child assets and populate all with data."""
        if self._data is None:
            return

        spec_changed = False

        # Create mesh assets for any meshes not in spec
        for glb_mesh in self._data.meshes:
            if glb_mesh.name not in self._mesh_assets:
                self._create_new_mesh_asset(glb_mesh.name)
                spec_changed = True

        # Create skeleton assets for any skins not in spec
        for i, skin in enumerate(self._data.skins):
            skeleton_key = "skeleton" if i == 0 else f"skeleton_{i}"
            if skeleton_key not in self._skeleton_assets:
                self._create_new_skeleton_asset(skeleton_key, i)
                spec_changed = True

        # Create animation assets for any animations not in spec
        for glb_anim in self._data.animations:
            if glb_anim.name not in self._animation_assets:
                self._create_new_animation_asset(glb_anim.name)
                spec_changed = True

        # Populate all child assets with data
        self._populate_child_assets()

        # Save spec if new child assets were created
        if spec_changed and self._source_path:
            self.save_spec_file()

    def _populate_child_assets(self) -> None:
        """Fill all child assets with extracted data from loaded GLB."""
        from termin.loaders.glb_instantiator import _glb_mesh_to_mesh3
        from termin.visualization.animation.clip import clip_from_glb
        from termin.skeleton import SkeletonData

        glb_mesh_names = {m.name for m in self._data.meshes}

        # Populate mesh assets
        for mesh_name, asset in self._mesh_assets.items():
            if asset._data is None:
                for glb_mesh in self._data.meshes:
                    if glb_mesh.name == mesh_name:
                        asset._data = _glb_mesh_to_mesh3(glb_mesh)
                        asset._loaded = True
                        break

        # Populate skeleton assets
        for skeleton_key, asset in self._skeleton_assets.items():
            if asset._data is None:
                # Parse skeleton_key to get index
                if skeleton_key == "skeleton":
                    index = 0
                else:
                    index = int(skeleton_key.split("_")[-1])
                if index < len(self._data.skins):
                    asset._data = SkeletonData.from_glb_skin(
                        self._data.skins[index],
                        self._data.nodes,
                    )
                    asset._loaded = True

        # Populate animation assets
        for anim_name, asset in self._animation_assets.items():
            if asset._data is None:
                for glb_anim in self._data.animations:
                    if glb_anim.name == anim_name:
                        asset._data = clip_from_glb(glb_anim)
                        asset._loaded = True
                        break

    def _create_new_mesh_asset(self, mesh_name: str) -> "MeshAsset":
        """Get or create a MeshAsset for a mesh discovered during load via ResourceManager."""
        from termin.assets.resources import ResourceManager

        rm = ResourceManager.instance()
        full_name = f"{self._name}_{mesh_name}"
        asset = rm.get_or_create_mesh_asset(
            name=full_name,
            source_path=str(self._source_path) if self._source_path else None,
            uuid=None,  # Will auto-generate
            parent=self,
            parent_key=mesh_name,
        )
        self._mesh_assets[mesh_name] = asset
        return asset

    def _create_new_skeleton_asset(self, skeleton_key: str, index: int) -> "SkeletonAsset":
        """Get or create a SkeletonAsset for a skeleton discovered during load via ResourceManager."""
        from termin.assets.resources import ResourceManager

        rm = ResourceManager.instance()
        skeleton_name = f"{self._name}_skeleton" if index == 0 else f"{self._name}_skeleton_{index}"
        asset = rm.get_or_create_skeleton_asset(
            name=skeleton_name,
            source_path=str(self._source_path) if self._source_path else None,
            uuid=None,  # Will auto-generate
            parent=self,
            parent_key=skeleton_key,
        )
        self._skeleton_assets[skeleton_key] = asset
        return asset

    def _create_new_animation_asset(self, anim_name: str) -> "AnimationClipAsset":
        """Get or create an AnimationClipAsset for an animation discovered during load via ResourceManager."""
        from termin.assets.resources import ResourceManager

        rm = ResourceManager.instance()
        full_name = f"{self._name}_{anim_name}"
        asset = rm.get_or_create_animation_clip_asset(
            name=full_name,
            source_path=str(self._source_path) if self._source_path else None,
            uuid=None,  # Will auto-generate
            parent=self,
            parent_key=anim_name,
        )
        self._animation_assets[anim_name] = asset
        return asset

    # --- Child asset access ---

    def get_mesh_assets(self) -> Dict[str, "MeshAsset"]:
        """Get all child mesh assets."""
        return self._mesh_assets

    def get_skeleton_assets(self) -> Dict[str, "SkeletonAsset"]:
        """Get all child skeleton assets."""
        return self._skeleton_assets

    def get_animation_assets(self) -> Dict[str, "AnimationClipAsset"]:
        """Get all child animation clip assets."""
        return self._animation_assets

    # --- Content info methods ---

    def get_mesh_count(self) -> int:
        """Get number of meshes in the GLB."""
        if self._data is None:
            return len(self._mesh_assets)  # Return spec count if not loaded
        return len(self._data.meshes)

    def get_animation_count(self) -> int:
        """Get number of animations in the GLB."""
        if self._data is None:
            return len(self._animation_assets)
        return len(self._data.animations)

    def has_skeleton(self) -> bool:
        """Check if GLB has skeleton data."""
        if self._data is None:
            return len(self._skeleton_assets) > 0
        return len(self._data.skins) > 0

    def get_bone_count(self) -> int:
        """Get total bone count from all skins."""
        if self._data is None:
            return 0
        return sum(s.joint_count for s in self._data.skins)
