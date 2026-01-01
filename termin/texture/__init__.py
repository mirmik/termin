"""Texture module for texture data handling."""

# Setup DLL paths before importing native extensions
from termin import _dll_setup  # noqa: F401

from termin.texture._texture_native import (
    TcTexture,
    TcTexture,
    tc_texture_count,
    tc_texture_get_all_info,
)

__all__ = ["TcTexture", "TcTexture", "tc_texture_count", "tc_texture_get_all_info"]
