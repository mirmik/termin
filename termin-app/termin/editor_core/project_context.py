"""Shared editor project context."""

from __future__ import annotations

from pathlib import Path


_current_project_path: Path | None = None


def set_current_project_path(path: str | Path | None) -> None:
    global _current_project_path
    _current_project_path = Path(path).resolve() if path is not None else None

    from termin.artifacts import ArtifactStore, set_artifact_store

    if _current_project_path is None:
        set_artifact_store(None)
    else:
        set_artifact_store(ArtifactStore(_current_project_path))


def current_project_path() -> Path | None:
    return _current_project_path
