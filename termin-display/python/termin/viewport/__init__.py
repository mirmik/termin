"""Viewport module - TcViewport with reference counting."""

from termin_nanobind.runtime import preload_sdk_libs

preload_sdk_libs("termin_display")

from termin.viewport._viewport_native import Viewport

__all__ = ["Viewport"]
