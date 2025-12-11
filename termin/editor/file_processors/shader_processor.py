"""Shader file processor for .shader files."""

from __future__ import annotations

import os
from typing import Set

from termin.editor.project_file_watcher import FileTypeProcessor


class ShaderFileProcessor(FileTypeProcessor):
    """Handles .shader files."""

    @property
    def extensions(self) -> Set[str]:
        return {".shader"}

    @property
    def resource_type(self) -> str:
        return "shader"

    def on_file_added(self, path: str) -> None:
        """Load new shader file."""
        name = os.path.splitext(os.path.basename(path))[0]

        if name in self._resource_manager.shaders:
            return

        try:
            from termin.visualization.render.shader_parser import (
                ShaderMultyPhaseProgramm,
                parse_shader_text,
            )

            with open(path, "r", encoding="utf-8") as f:
                shader_text = f.read()

            tree = parse_shader_text(shader_text)
            program = ShaderMultyPhaseProgramm.from_tree(tree)
            self._resource_manager.register_shader(name, program, source_path=path)

            if path not in self._file_to_resources:
                self._file_to_resources[path] = set()
            self._file_to_resources[path].add(name)

            print(f"[ShaderProcessor] Loaded: {name}")
            self._notify_reloaded(name)

        except Exception as e:
            print(f"[ShaderProcessor] Failed to load {path}: {e}")

    def on_file_changed(self, path: str) -> None:
        """Reload modified shader."""
        name = os.path.splitext(os.path.basename(path))[0]

        if name not in self._resource_manager.shaders:
            return

        try:
            from termin.visualization.render.shader_parser import (
                ShaderMultyPhaseProgramm,
                parse_shader_text,
            )

            with open(path, "r", encoding="utf-8") as f:
                shader_text = f.read()

            tree = parse_shader_text(shader_text)
            program = ShaderMultyPhaseProgramm.from_tree(tree)
            self._resource_manager.register_shader(name, program, source_path=path)

            print(f"[ShaderProcessor] Reloaded: {name}")
            self._notify_reloaded(name)

        except Exception as e:
            print(f"[ShaderProcessor] Failed to reload {name}: {e}")

    def on_file_removed(self, path: str) -> None:
        """Handle shader file deletion."""
        if path in self._file_to_resources:
            del self._file_to_resources[path]
