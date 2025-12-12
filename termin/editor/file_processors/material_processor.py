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
        keeper = self._resource_manager.get_keeper(name)
        if keeper is not None and keeper.has_material:
            return

        try:
            from termin.visualization.core.material import Material

            mat = Material.load_from_material_file(path)
            mat.name = name
            self._resource_manager.register_material(name, mat, source_path=path)

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
        keeper = self._resource_manager.get_keeper(name)

        if keeper is None or keeper.source_path is None:
            return

        # Only reload .material files (not .shader dependencies)
        if not keeper.source_path.endswith(".material"):
            return

        try:
            from termin.visualization.core.material import Material

            new_mat = Material.load_from_material_file(path)
            keeper.update_material(new_mat)

            # Update materials dict for compatibility
            if keeper.material is not None:
                self._resource_manager.materials[name] = keeper.material

            print(f"[MaterialProcessor] Reloaded: {name}")
            self._notify_reloaded(name)

        except Exception as e:
            print(f"[MaterialProcessor] Failed to reload {name}: {e}")

    def on_file_removed(self, path: str) -> None:
        """Handle material file deletion."""
        if path in self._file_to_resources:
            del self._file_to_resources[path]
