"""Material file pre-loader for .material files."""

from __future__ import annotations

import json
from typing import Set

from tcbase import log
from termin.editor.project_file_watcher import FilePreLoader, PreLoadResult


class MaterialPreLoader(FilePreLoader):
    """Pre-loads .material files - reads content and extracts UUID."""

    @property
    def priority(self) -> int:
        return 20  # Materials depend on shaders and textures

    @property
    def extensions(self) -> Set[str]:
        return {".material"}

    @property
    def resource_type(self) -> str:
        return "material"

    def preload(self, path: str) -> PreLoadResult | None:
        """
        Pre-load material file: read content and extract UUID.

        Materials are JSON files, so we can extract UUID without full parsing.
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

        except Exception:
            log.error(f"[MaterialPreLoader] Failed to read {path}", exc_info=True)
            return None
