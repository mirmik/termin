"""Texture module for texture data handling."""

# Setup DLL paths before importing native extensions
from termin import _dll_setup  # noqa: F401

from termin.texture._texture_native import TextureData

__all__ = ["TextureData"]
