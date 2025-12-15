"""Simple 2D texture wrapper for the graphics backend."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, TYPE_CHECKING

import numpy as np
from PIL import Image
from termin.visualization.platform.backends.base import GraphicsBackend, TextureHandle

if TYPE_CHECKING:
    from PyQt6.QtGui import QPixmap


class Texture:
    """Loads an image via Pillow and uploads it as ``GL_TEXTURE_2D``."""

    def __init__(self, path: Optional[str | Path] = None):
        self._handles: dict[int | None, TextureHandle] = {}
        self._image_data: Optional[np.ndarray] = None  # Original data (not flipped)
        self._size: Optional[tuple[int, int]] = None
        self.source_path: str | None = None
        self.flip_x: bool = False  # Mirror horizontally
        self.flip_y: bool = True  # Flip for OpenGL by default
        self.transpose: bool = False  # Swap X and Y axes
        self._preview_pixmap: Optional["QPixmap"] = None
        if path is not None:
            self.load(path)

    def load(self, path: str | Path):
        from termin.loaders.texture_spec import TextureSpec

        # Load spec for this texture
        spec = TextureSpec.for_texture_file(path)
        self.flip_x = spec.flip_x
        self.flip_y = spec.flip_y
        self.transpose = spec.transpose

        # Load image without flipping - flip happens at GPU upload
        image = Image.open(path).convert("RGBA")
        data = np.array(image, dtype=np.uint8)
        width, height = image.size

        self._image_data = data
        self._size = (width, height)
        self._handles.clear()
        self._preview_pixmap = None  # Invalidate preview
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

        # Apply transformations when uploading to GPU
        data = self._image_data
        size = self._size

        if self.transpose:
            # Swap axes 0 and 1 (height and width)
            data = np.swapaxes(data, 0, 1).copy()
            size = (size[1], size[0])  # Swap width and height

        if self.flip_x:
            data = data[:, ::-1, :].copy()

        if self.flip_y:
            data = data[::-1, :, :].copy()

        handle = graphics.create_texture(data, size, channels=4)
        self._handles[context_key] = handle
        return handle

    def bind(self, graphics: GraphicsBackend, unit: int = 0, context_key: int | None = None):
        handle = self._ensure_handle(graphics, context_key)
        handle.bind(unit)

    def get_preview_pixmap(self, max_size: int = 200) -> Optional["QPixmap"]:
        """
        Get cached preview pixmap for this texture.

        Args:
            max_size: Maximum width/height of the preview.

        Returns:
            QPixmap or None if texture has no data.
        """
        if self._preview_pixmap is not None:
            return self._preview_pixmap

        if self._image_data is None or self._size is None:
            return None

        from PyQt6.QtGui import QImage, QPixmap
        from PyQt6.QtCore import Qt

        width, height = self._size
        data = self._image_data

        # Create QImage from RGBA data (no flip needed - data is original orientation)
        if len(data.shape) == 3 and data.shape[2] == 4:
            qimage = QImage(
                data.data,
                width,
                height,
                width * 4,
                QImage.Format.Format_RGBA8888,
            )
        else:
            return None

        pixmap = QPixmap.fromImage(qimage)

        # Scale to fit max_size
        if pixmap.width() > max_size or pixmap.height() > max_size:
            pixmap = pixmap.scaled(
                max_size,
                max_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

        self._preview_pixmap = pixmap
        return self._preview_pixmap

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
