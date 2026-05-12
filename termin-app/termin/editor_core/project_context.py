"""Shared editor project context."""

from __future__ import annotations

from pathlib import Path


_current_project_path: Path | None = None


def set_current_project_path(path: str | Path | None) -> None:
    global _current_project_path
    _current_project_path = Path(path).resolve() if path is not None else None


def current_project_path() -> Path | None:
    return _current_project_path
