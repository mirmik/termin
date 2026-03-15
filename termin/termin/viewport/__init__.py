"""Viewport module - TcViewport with reference counting."""

from termin import _dll_setup  # noqa: F401

_dll_setup.extend_package_path(__path__, "viewport")

from termin.viewport._viewport_native import Viewport

__all__ = ["Viewport"]
