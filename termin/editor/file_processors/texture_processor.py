"""Texture file processor for image files."""

from __future__ import annotations

import os
from typing import Set

from termin.editor.project_file_watcher import FileTypeProcessor


class TextureFileProcessor(FileTypeProcessor):
    """Handles texture files (.png, .jpg, .jpeg)."""

    @property
    def extensions(self) -> Set[str]:
        return {".png", ".jpg", ".jpeg"}

    @property
    def resource_type(self) -> str:
        return "texture"

    def on_file_added(self, path: str) -> None:
        """
        Track new texture file.

        Note: Textures are lazily loaded when needed by materials,
        so we just track the file here.
        """
        if path not in self._file_to_resources:
            self._file_to_resources[path] = set()
        # Texture name would be added when actually loaded

    def on_file_changed(self, path: str) -> None:
        """
        Invalidate textures loaded from this file.

        Looks up textures in ResourceManager that were loaded from this path
        and invalidates them for reload.
        """
        # Find textures using this path
        for name, tex in self._resource_manager.textures.items():
            if tex.source_path == path:
                try:
                    tex.invalidate()
                    print(f"[TextureProcessor] Invalidated: {name}")
                    self._notify_reloaded(name)
                except Exception as e:
                    print(f"[TextureProcessor] Failed to invalidate {name}: {e}")

    def on_file_removed(self, path: str) -> None:
        """Handle texture file deletion."""
        if path in self._file_to_resources:
            del self._file_to_resources[path]
