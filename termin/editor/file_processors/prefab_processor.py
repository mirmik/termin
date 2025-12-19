"""Prefab file pre-loader for .prefab files."""

from __future__ import annotations

import json
from typing import Set

from termin.editor.project_file_watcher import FilePreLoader, PreLoadResult


class PrefabPreLoader(FilePreLoader):
    """Pre-loads .prefab files - reads content and extracts UUID."""

    @property
    def priority(self) -> int:
        # Prefabs depend on materials, meshes, etc.
        return 30

    @property
    def extensions(self) -> Set[str]:
        return {".prefab"}

    @property
    def resource_type(self) -> str:
        return "prefab"

    def preload(self, path: str) -> PreLoadResult | None:
        """
        Pre-load prefab file: read content and extract UUID.

        Prefabs are JSON files, so we can extract UUID without full parsing.
        """
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            # Extract UUID from JSON without full parsing
            uuid = None
            try:
                data = json.loads(content)
                uuid = data.get("uuid")
            except json.JSONDecodeError:
                pass

            return PreLoadResult(
                resource_type=self.resource_type,
                path=path,
                content=content,
                uuid=uuid,
            )

        except Exception as e:
            print(f"[PrefabPreLoader] Failed to read {path}: {e}")
            return None
