"""UI layout file pre-loader for .ui.yaml files."""

from __future__ import annotations

from typing import Set

from termin.editor.project_file_watcher import FilePreLoader, PreLoadResult


class UIPreLoader(FilePreLoader):
    """Pre-loads UI layout files - reads content and UUID from spec."""

    @property
    def priority(self) -> int:
        return 10  # UI files have no dependencies

    @property
    def extensions(self) -> Set[str]:
        return {".uiscript"}

    @property
    def resource_type(self) -> str:
        return "ui"

    def preload(self, path: str) -> PreLoadResult | None:
        """
        Pre-load UI file: only read UUID from spec (lazy loading).
        """
        # Read spec file (may contain uuid)
        spec_data = self.read_spec_file(path)
        uuid = spec_data.get("uuid") if spec_data else None

        return PreLoadResult(
            resource_type=self.resource_type,
            path=path,
            content=None,  # Lazy loading - don't read content
            uuid=uuid,
            spec_data=spec_data,
        )


# Backward compatibility alias
UIProcessor = UIPreLoader
