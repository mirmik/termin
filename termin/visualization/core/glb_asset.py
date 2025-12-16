"""GLBAsset - Asset for GLB 3D model files."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from termin.visualization.core.asset import Asset

if TYPE_CHECKING:
    from termin.loaders.glb_loader import GLBSceneData


class GLBAsset(Asset):
    """
    Asset for GLB model files.

    Stores GLBSceneData which contains meshes, textures, animations, skeleton.
    When instantiated into scene, creates Entity hierarchy via glb_instantiator.
    """

    def __init__(
        self,
        scene_data: "GLBSceneData | None" = None,
        name: str = "glb",
        source_path: Path | str | None = None,
        uuid: str | None = None,
    ):
        """
        Initialize GLBAsset.

        Args:
            scene_data: GLBSceneData (can be None for lazy loading)
            name: Human-readable name
            source_path: Path to source GLB file
            uuid: Existing UUID or None to generate new one
        """
        super().__init__(name=name, source_path=source_path, uuid=uuid)
        self._scene_data: "GLBSceneData | None" = scene_data
        self._loaded = scene_data is not None

    @property
    def scene_data(self) -> "GLBSceneData | None":
        """GLB scene data."""
        return self._scene_data

    def load(self) -> bool:
        """
        Load GLB data from source_path.

        Returns:
            True if loaded successfully.
        """
        if self._source_path is None:
            return False

        try:
            from termin.loaders.glb_loader import load_glb_file

            self._scene_data = load_glb_file(str(self._source_path))
            self._loaded = True
            return True
        except Exception as e:
            print(f"[GLBAsset] Failed to load {self._source_path}: {e}")
            return False

    def load_from_content(
        self,
        content: bytes | None,
        spec_data: dict | None = None,
        has_uuid_in_spec: bool = False,
    ) -> bool:
        """
        Load GLB from binary content.

        Args:
            content: Binary GLB data
            spec_data: Spec file data with normalize_scale, etc.
            has_uuid_in_spec: If True, spec file already has UUID (don't save)

        Returns:
            True if loaded successfully.
        """
        if content is None:
            return False

        try:
            import io

            from termin.loaders.glb_loader import load_glb_file_from_buffer

            # Get normalize_scale setting from spec
            normalize_scale = spec_data.get("normalize_scale", False) if spec_data else False

            self._scene_data = load_glb_file_from_buffer(content, normalize_scale=normalize_scale)
            self._loaded = True

            # Register meshes in ResourceManager (may generate new UUIDs)
            updated_spec, meshes_updated = self._register_meshes(spec_data)

            # Save spec file if:
            # - No UUID was in spec (need to save GLB's own UUID)
            # - Resources were updated with new UUIDs
            if not has_uuid_in_spec or meshes_updated:
                self._save_spec_file(updated_spec)

            return True
        except Exception as e:
            print(f"[GLBAsset] Failed to load content: {e}")
            return False

    def _save_spec_file(self, existing_spec_data: dict | None = None) -> bool:
        """Save UUID to spec file, preserving existing settings."""
        if self._source_path is None:
            return False

        from termin.editor.project_file_watcher import FilePreLoader

        # Merge existing spec data with UUID
        spec_data = dict(existing_spec_data) if existing_spec_data else {}
        spec_data["uuid"] = self.uuid

        if FilePreLoader.write_spec_file(str(self._source_path), spec_data):
            self.mark_just_saved()
            print(f"[GLBAsset] Added UUID to spec: {self._name}")
            return True
        return False

    def _register_meshes(self, spec_data: dict | None) -> tuple[dict, bool]:
        """
        Register all meshes from GLB in ResourceManager.

        Returns:
            (spec_data, updated) - spec_data with mesh UUIDs, and whether new UUIDs were added.
        """
        spec_data = dict(spec_data) if spec_data else {}

        if self._scene_data is None:
            return spec_data, False

        import uuid as uuid_module
        from termin.visualization.core.resources import ResourceManager
        from termin.visualization.core.mesh import MeshDrawable
        from termin.visualization.core.mesh_asset import MeshAsset
        from termin.loaders.glb_instantiator import _glb_mesh_to_mesh3

        rm = ResourceManager.instance()

        # Get or create resources section in spec
        if "resources" not in spec_data:
            spec_data["resources"] = {}
        if "meshes" not in spec_data["resources"]:
            spec_data["resources"]["meshes"] = {}

        mesh_uuids = spec_data["resources"]["meshes"]
        updated = False

        for i, glb_mesh in enumerate(self._scene_data.meshes):
            # Create unique name: glb_name + mesh_name
            mesh_name = f"{self._name}_{glb_mesh.name}"

            # Get or generate UUID for this mesh
            mesh_uuid = mesh_uuids.get(glb_mesh.name)
            if mesh_uuid is None:
                mesh_uuid = str(uuid_module.uuid4())
                mesh_uuids[glb_mesh.name] = mesh_uuid
                updated = True

            # Skip if already registered
            if mesh_name in rm.meshes:
                continue

            mesh3 = _glb_mesh_to_mesh3(glb_mesh)

            # Create MeshAsset with UUID
            asset = MeshAsset(
                mesh_data=mesh3,
                name=mesh_name,
                source_path=str(self._source_path) if self._source_path else None,
                uuid=mesh_uuid,
            )
            rm._mesh_assets[mesh_name] = asset
            rm._assets_by_uuid[mesh_uuid] = asset

            # Create MeshDrawable wrapper
            drawable = MeshDrawable(asset, name=mesh_name)
            rm.meshes[mesh_name] = drawable

        return spec_data, updated

    def unload(self) -> None:
        """Unload GLB data to free memory."""
        self._scene_data = None
        self._loaded = False

    # --- Content info methods ---

    def get_mesh_count(self) -> int:
        """Get number of meshes in the GLB."""
        if self._scene_data is None:
            return 0
        return len(self._scene_data.meshes)

    def get_animation_count(self) -> int:
        """Get number of animations in the GLB."""
        if self._scene_data is None:
            return 0
        return len(self._scene_data.animations)

    def has_skeleton(self) -> bool:
        """Check if GLB has skeleton data."""
        if self._scene_data is None:
            return False
        return len(self._scene_data.skins) > 0

    def get_bone_count(self) -> int:
        """Get total bone count from all skins."""
        if self._scene_data is None:
            return 0
        return sum(s.joint_count for s in self._scene_data.skins)
