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
    adapter_name: str = "unknown"
    adapter_driver: str = "unknown"
    adapter_class: str = "unknown"


def build_editor_about_info(
    *,
    backend_name: str | None = None,
    adapter_name: str | None = None,
    adapter_driver: str | None = None,
    adapter_class: str | None = None,
) -> EditorAboutInfo:
    try:
        version = metadata.version("termin-app")
    except metadata.PackageNotFoundError:
        version = "development"
    configured = os.environ.get("TERMIN_BACKEND") or "(unset: compiled default)"
    return EditorAboutInfo(
        version=version,
        configured_backend=configured,
        active_backend=backend_name or "unknown",
        adapter_name=adapter_name or "unknown",
        adapter_driver=adapter_driver or "unknown",
        adapter_class=adapter_class or "unknown",
    )


def build_software_renderer_warning(info: EditorAboutInfo) -> str | None:
    if info.active_backend != "vulkan" or info.adapter_class != "cpu":
        return None
    return (
        "Vulkan is using a CPU renderer instead of a hardware GPU.\n\n"
        f"Device: {info.adapter_name}\n"
        f"Driver: {info.adapter_driver}\n\n"
        "Graphics performance may be severely reduced. Termin has kept Vulkan "
        "selected; choose another backend explicitly with TERMIN_BACKEND and "
        "restart the editor."
    )


__all__ = [
    "EditorAboutInfo",
    "build_editor_about_info",
    "build_software_renderer_warning",
]
