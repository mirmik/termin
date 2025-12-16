"""Texture file processor for image files."""

from __future__ import annotations

import os
from typing import Set

from termin.editor.project_file_watcher import FileTypeProcessor


class TextureFileProcessor(FileTypeProcessor):
    """Handles texture files (.png, .jpg, .jpeg, .tga, .bmp)."""

    @property
    def priority(self) -> int:
        return 10  # Textures have no dependencies

    @property
    def extensions(self) -> Set[str]:
        return {".png", ".jpg", ".jpeg", ".tga", ".bmp"}

    @property
    def resource_type(self) -> str:
        return "texture"

    def on_file_added(self, path: str) -> None:
        """Load new texture file."""
        name = os.path.splitext(os.path.basename(path))[0]

        if name in self._resource_manager.textures:
            return

        try:
            from termin.visualization.render.texture import Texture

            texture = Texture.from_file(path)
            self._resource_manager.register_texture(name, texture, source_path=path)

            if path not in self._file_to_resources:
                self._file_to_resources[path] = set()
            self._file_to_resources[path].add(name)

            print(f"[TextureProcessor] Loaded: {name}")
            self._notify_reloaded(name)

        except Exception as e:
            print(f"[TextureProcessor] Failed to load {path}: {e}")

    def on_file_changed(self, path: str) -> None:
        """Reload modified texture."""
        name = os.path.splitext(os.path.basename(path))[0]

        # Find texture by source_path or name
        texture = None
        found_name = name
        for tex_name, tex in self._resource_manager.textures.items():
            if tex.source_path == path:
                texture = tex
                found_name = tex_name
                break

        if texture is None:
            texture = self._resource_manager.get_texture(name)

        if texture is None:
            return

        try:
            # Invalidate forces texture reload on next use
            texture.invalidate()
            print(f"[TextureProcessor] Reloaded: {found_name}")
            self._notify_reloaded(found_name)
        except Exception as e:
            print(f"[TextureProcessor] Failed to reload {found_name}: {e}")

    def on_file_removed(self, path: str) -> None:
        """Handle texture file deletion."""
        if path in self._file_to_resources:
            for name in self._file_to_resources[path]:
                self._resource_manager.unregister_texture(name)
                print(f"[TextureProcessor] Removed: {name}")
            del self._file_to_resources[path]

    def _notify_reloaded(self, name: str) -> None:
        """Notify listeners about resource reload."""
        if self._on_resource_reloaded is not None:
            self._on_resource_reloaded(self.resource_type, name)
