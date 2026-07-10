"""Toolkit-neutral About dialog information."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata
import os


@dataclass(frozen=True)
class EditorAboutInfo:
    version: str
    configured_backend: str
    active_backend: str


def build_editor_about_info(*, backend_name: str | None = None) -> EditorAboutInfo:
    try:
        version = metadata.version("termin-app")
    except metadata.PackageNotFoundError:
        version = "development"
    configured = os.environ.get("TERMIN_BACKEND") or "(unset: compiled default)"
    return EditorAboutInfo(
        version=version,
        configured_backend=configured,
        active_backend=backend_name or "unknown",
    )


__all__ = ["EditorAboutInfo", "build_editor_about_info"]
