"""Texture module for texture data handling."""

from tgfx import (
    TcTexture,
    tc_texture_declare,
    tc_texture_ensure_loaded,
    tc_texture_count,
    tc_texture_get_all_info,
    tc_texture_is_loaded,
    tc_texture_set_load_callback,
    tc_texture_clear_load_callback,
)

__all__ = [
    "TcTexture",
    "tc_texture_declare",
    "tc_texture_ensure_loaded",
    "tc_texture_count",
    "tc_texture_get_all_info",
    "tc_texture_is_loaded",
    "tc_texture_set_load_callback",
    "tc_texture_clear_load_callback",
]
