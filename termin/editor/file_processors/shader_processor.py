"""Shader file pre-loader for .shader files."""

from __future__ import annotations

from typing import Set

from termin.editor.project_file_watcher import FilePreLoader, PreLoadResult


class ShaderPreLoader(FilePreLoader):
    """Pre-loads .shader files - reads content and UUID from spec."""

    @property
    def priority(self) -> int:
        return 0  # Shaders have no dependencies, load first

    @property
    def extensions(self) -> Set[str]:
        return {".shader"}

    @property
    def resource_type(self) -> str:
        return "shader"

    def preload(self, path: str) -> PreLoadResult | None:
        """
        Pre-load shader file: read content and UUID from spec.
        """
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            # Read UUID from .spec file
            spec_data = self.read_spec_file(path)
            uuid = spec_data.get("uuid") if spec_data else None

            return PreLoadResult(
                resource_type=self.resource_type,
                path=path,
                content=content,
                uuid=uuid,
                spec_data=spec_data,
            )

        except Exception as e:
            print(f"[ShaderPreLoader] Failed to read {path}: {e}")
            return None


# Backward compatibility alias
ShaderFileProcessor = ShaderPreLoader
