"""GLB file pre-loader for 3D model files with animations."""

from __future__ import annotations

from typing import Set

from termin.editor.project_file_watcher import FilePreLoader, PreLoadResult


class GLBPreLoader(FilePreLoader):
    """Pre-loads GLB files - reads content and UUID from spec."""

    @property
    def priority(self) -> int:
        return 10  # GLB files have no dependencies

    @property
    def extensions(self) -> Set[str]:
        return {".glb", ".gltf"}

    @property
    def resource_type(self) -> str:
        return "glb"

    def preload(self, path: str) -> PreLoadResult | None:
        """
        Pre-load GLB file: read binary content and UUID from spec.
        """
        try:
            with open(path, "rb") as f:
                content = f.read()

            # Read spec file (may contain uuid, normalize_scale, etc.)
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
            print(f"[GLBPreLoader] Failed to read {path}: {e}")
            return None
