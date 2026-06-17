"""Compatibility re-export for render texture helpers."""

from termin.render.texture import (
    Texture,
    get_dummy_shadow_texture,
    get_normal_texture,
    get_white_texture,
    reset_dummy_shadow_texture,
)

__all__ = [
    "Texture",
    "get_dummy_shadow_texture",
    "get_normal_texture",
    "get_white_texture",
    "reset_dummy_shadow_texture",
]
