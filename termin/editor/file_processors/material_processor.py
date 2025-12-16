"""Material file processor for .material files."""

from __future__ import annotations

import os
from typing import Set

from termin.editor.project_file_watcher import FileTypeProcessor


class MaterialFileProcessor(FileTypeProcessor):
    """Handles .material files."""

    @property
    def priority(self) -> int:
        return 20  # Materials depend on shaders and textures

    @property
    def extensions(self) -> Set[str]:
        return {".material"}

    @property
    def resource_type(self) -> str:
        return "material"

    def on_file_added(self, path: str) -> None:
        """Load new material file."""
        name = os.path.splitext(os.path.basename(path))[0]

        # Check if already loaded
        if name in self._resource_manager.materials:
            return

        try:
            from termin.visualization.core.material_asset import load_material_file

            mat, file_uuid = load_material_file(path)
            mat.name = name
            self._resource_manager.register_material(name, mat, source_path=path, uuid=file_uuid)

            # Track file -> resource mapping
            if path not in self._file_to_resources:
                self._file_to_resources[path] = set()
            self._file_to_resources[path].add(name)

            print(f"[MaterialProcessor] Loaded: {name}")
            self._notify_reloaded(name)

        except Exception as e:
            print(f"[MaterialProcessor] Failed to load {path}: {e}")

    def on_file_changed(self, path: str) -> None:
        """Reload modified material."""
        name = os.path.splitext(os.path.basename(path))[0]

        # Find existing MaterialAsset
        asset = self._resource_manager.get_material_asset(name)
        if asset is None:
            return

        # Only reload .material files
        if asset.source_path is None or not str(asset.source_path).endswith(".material"):
            return

        # Skip reload if this is our own save (not external modification)
        if not asset.should_reload_from_file():
            return

        try:
            from termin.visualization.core.material_asset import load_material_file

            new_mat, _ = load_material_file(path)

            # Update existing material in-place for hot-reload
            if asset.material is not None:
                asset.material.update_from(new_mat)
            else:
                asset.material = new_mat

            # Update materials dict for compatibility
            self._resource_manager.materials[name] = asset.material

            print(f"[MaterialProcessor] Reloaded: {name}")
            self._notify_reloaded(name)

        except Exception as e:
            print(f"[MaterialProcessor] Failed to reload {name}: {e}")

    def on_file_removed(self, path: str) -> None:
        """Handle material file deletion."""
        if path in self._file_to_resources:
            del self._file_to_resources[path]
