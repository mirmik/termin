"""Viewport module - TcViewport with reference counting."""

from termin import _dll_setup  # noqa: F401

import os as _os
_sdk_dir = _os.path.join(_os.sep, "opt", "termin", "lib", "python", "termin", "viewport")
if _os.path.isdir(_sdk_dir) and _sdk_dir not in __path__:
    __path__.append(_sdk_dir)

from termin.viewport._viewport_native import Viewport

__all__ = ["Viewport"]
