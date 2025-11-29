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
