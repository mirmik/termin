"""Mesh file pre-loader for 3D model files."""

from __future__ import annotations

from typing import Set

from termin.editor.project_file_watcher import FilePreLoader, PreLoadResult


class MeshPreLoader(FilePreLoader):
    """Pre-loads mesh files - reads content and UUID from spec."""

    @property
    def priority(self) -> int:
        return 10  # Meshes have no dependencies

    @property
    def extensions(self) -> Set[str]:
        return {".stl", ".obj"}

    @property
    def resource_type(self) -> str:
        return "mesh"

    def preload(self, path: str) -> PreLoadResult | None:
        """
        Pre-load mesh file: read binary content and UUID from spec.
        """
        try:
            with open(path, "rb") as f:
                content = f.read()

            # Read spec file (may contain uuid, scale, axis mappings)
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
            print(f"[MeshPreLoader] Failed to read {path}: {e}")
            return None


# Backward compatibility alias
MeshFileProcessor = MeshPreLoader
