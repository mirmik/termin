"""Compatibility re-export for texture handles."""

from termin.render.texture_handle import (
    TextureHandle,
    get_normal_texture_handle,
    get_white_texture_handle,
)

__all__ = ["TextureHandle", "get_white_texture_handle", "get_normal_texture_handle"]
