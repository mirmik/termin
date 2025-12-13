"""Simple 2D texture wrapper for the graphics backend."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image
from termin.visualization.platform.backends.base import GraphicsBackend, TextureHandle


class Texture:
    """Loads an image via Pillow and uploads it as ``GL_TEXTURE_2D``."""

    def __init__(self, path: Optional[str | Path] = None):
        self._handles: dict[int | None, TextureHandle] = {}
        self._image_data: Optional[np.ndarray] = None
        self._size: Optional[tuple[int, int]] = None
        self.source_path: str | None = None
        if path is not None:
            self.load(path)

    def load(self, path: str | Path):
        image = Image.open(path).convert("RGBA")
        image = image.transpose(Image.FLIP_TOP_BOTTOM)
        data = np.array(image, dtype=np.uint8)
        width, height = image.size

        self._image_data = data
        self._size = (width, height)
        self._handles.clear()
        self.source_path = str(path)

    def invalidate(self) -> None:
        """
        Invalidate cached GPU handles, forcing texture reload on next use.

        If source_path is set, reloads the texture from disk.
        """
        self._handles.clear()
        if self.source_path is not None:
            self.load(self.source_path)

    def _ensure_handle(self, graphics: GraphicsBackend, context_key: int | None) -> TextureHandle:
        handle = self._handles.get(context_key)
        if handle is not None:
            return handle
        if self._image_data is None or self._size is None:
            raise RuntimeError("Texture has no image data to upload.")
        handle = graphics.create_texture(self._image_data, self._size, channels=4)
        self._handles[context_key] = handle
        return handle

    def bind(self, graphics: GraphicsBackend, unit: int = 0, context_key: int | None = None):
        handle = self._ensure_handle(graphics, context_key)
        handle.bind(unit)

    @classmethod
    def from_file(cls, path: str | Path) -> "Texture":
        tex = cls()
        tex.load(path)
        return tex

    @classmethod
    def from_data(
        cls,
        data: np.ndarray,
        width: int,
        height: int,
        source_path: str | None = None,
    ) -> "Texture":
        """
        Create texture from raw RGBA data.

        Args:
            data: Numpy array of shape (height, width, 4) with uint8 RGBA values.
            width: Texture width in pixels.
            height: Texture height in pixels.
            source_path: Optional source path for identification.

        Returns:
            Texture instance with the provided data.
        """
        tex = cls()
        tex._image_data = data
        tex._size = (width, height)
        tex.source_path = source_path
        return tex


# --- White 1x1 Texture ---

_white_texture: Texture | None = None


def get_white_texture() -> Texture:
    """
    Returns a white 1x1 texture.

    Used as default for optional texture slots (like albedo when no texture is set).
    Singleton — created once.
    """
    global _white_texture

    if _white_texture is None:
        # Create 1x1 white pixel (RGBA = 255, 255, 255, 255)
        data = np.array([[[255, 255, 255, 255]]], dtype=np.uint8)
        _white_texture = Texture.from_data(data, width=1, height=1, source_path="__white_1x1__")

    return _white_texture
