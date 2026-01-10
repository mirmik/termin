"""Simple 2D texture wrapper for the graphics backend."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, TYPE_CHECKING

import numpy as np

from termin.visualization.core.texture_handle import TextureHandle
from termin.visualization.render.texture_asset import TextureAsset
from termin.visualization.render.texture_gpu import TextureGPU

if TYPE_CHECKING:
    from PyQt6.QtGui import QPixmap
    from termin.visualization.platform.backends.base import GraphicsBackend


class Texture:
    """
    Loads an image via Pillow and uploads it as ``GL_TEXTURE_2D``.

    This is a wrapper over TextureHandle + TextureGPU.
    """

    def __init__(self, path: Optional[str | Path] = None):
        self._handle: TextureHandle = TextureHandle()
        self._gpu: TextureGPU = TextureGPU()
        self._preview_pixmap: Optional["QPixmap"] = None
        if path is not None:
            self.load(path)

    @property
    def asset(self) -> TextureAsset | None:
        """Get underlying TextureAsset."""
        return self._handle.get_asset()

    @property
    def texture_data(self) -> TcTexture | None:
        """Get underlying TcTexture."""
        return self._handle.get()

    @property
    def source_path(self) -> str | None:
        """Source path of the texture."""
        asset = self._handle.get_asset()
        if asset is not None and asset.source_path is not None:
            return str(asset.source_path)
        return None

    @property
    def _size(self) -> tuple[int, int] | None:
        """Size of the texture (width, height)."""
        td = self._handle.get()
        if td is not None:
            return (td.width, td.height)
        return None

    @property
    def _image_data(self) -> np.ndarray | None:
        """Raw image data (for preview)."""
        td = self._handle.get()
        if td is not None:
            return td.data
        return None

    def load(self, path: str | Path) -> None:
        """Load texture from file."""
        asset = TextureAsset.from_file(path)
        self._handle = TextureHandle.from_asset(asset)
        self._gpu = TextureGPU()
        self._preview_pixmap = None

    def invalidate(self) -> None:
        """
        Invalidate cached GPU handles, forcing texture reload on next use.

        If source_path is set, reloads the texture from disk.
        """
        asset = self._handle.get_asset()
        if asset is not None:
            asset.reload()
        self._gpu.delete()
        self._preview_pixmap = None

    def bind(self, graphics: "GraphicsBackend", unit: int = 0, context_key: int | None = None) -> None:
        """Bind texture to specified unit."""
        texture_data = self._handle.get()
        asset = self._handle.get_asset()
        if texture_data is None:
            return

        version = asset.version if asset else 0
        self._gpu.bind(
            graphics=graphics,
            texture_data=texture_data,
            version=version,
            unit=unit,
            context_key=context_key,
        )

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

        texture_data = self._handle.get()
        if texture_data is None:
            return None

        from PyQt6.QtGui import QImage, QPixmap
        from PyQt6.QtCore import Qt

        width = texture_data.width
        height = texture_data.height
        data = texture_data.data

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
        """Create texture from file."""
        tex = cls()
        tex.load(path)
        return tex

    @classmethod
    def from_asset(cls, asset: TextureAsset) -> "Texture":
        """Create texture from existing TextureAsset."""
        tex = cls()
        tex._handle = TextureHandle.from_asset(asset)
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
        from termin.texture import TcTexture

        texture_data = TcTexture.from_data(
            data=data,
            width=width,
            height=height,
            channels=4,
            flip_x=False,
            flip_y=True,
            transpose=False,
            name=source_path or "texture",
            source_path=source_path or "",
        )
        asset = TextureAsset(
            texture_data=texture_data,
            name=source_path or "texture",
            source_path=source_path,
        )
        tex = cls()
        tex._handle = TextureHandle.from_asset(asset)
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


# --- Normal 1x1 Texture (flat normal) ---

_normal_texture: Texture | None = None


def get_normal_texture() -> Texture:
    """
    Returns a 1x1 normal map texture representing a flat surface (pointing up).

    RGB(128, 128, 255) = tangent space normal (0, 0, 1) after [0,255]->[-1,1] conversion.
    Used as default for normal map slots when no texture is set.
    Singleton — created once.
    """
    global _normal_texture

    if _normal_texture is None:
        # Create 1x1 flat normal (pointing up in tangent space)
        # RGB = (128, 128, 255) → normalized = (0, 0, 1)
        data = np.array([[[128, 128, 255, 255]]], dtype=np.uint8)
        _normal_texture = Texture.from_data(data, width=1, height=1, source_path="__normal_1x1__")

    return _normal_texture


# --- Dummy Shadow Texture (for sampler2DShadow) ---

class _DummyShadowTexture:
    """
    Placeholder depth texture for sampler2DShadow.

    AMD драйверы требуют чтобы sampler2DShadow были привязаны к
    валидным depth текстурам с GL_TEXTURE_COMPARE_MODE, даже если
    они не используются в шейдере.

    Возвращает 1.0 (полностью освещено) при любом сэмплировании.
    """

    def __init__(self):
        self._tex_id: int | None = None

    def _ensure_created(self):
        if self._tex_id is not None:
            return

        from OpenGL import GL as gl

        self._tex_id = gl.glGenTextures(1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self._tex_id)

        # 1x1 depth texture со значением 1.0 (максимальная глубина = нет тени)
        gl.glTexImage2D(
            gl.GL_TEXTURE_2D, 0, gl.GL_DEPTH_COMPONENT24,
            1, 1, 0,
            gl.GL_DEPTH_COMPONENT, gl.GL_FLOAT,
            np.array([1.0], dtype=np.float32)
        )

        # Параметры для sampler2DShadow
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)

        # Hardware depth comparison для sampler2DShadow
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_COMPARE_MODE, gl.GL_COMPARE_REF_TO_TEXTURE)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_COMPARE_FUNC, gl.GL_LEQUAL)

        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)

    def bind(self, unit: int):
        """Bind to texture unit."""
        from OpenGL import GL as gl

        self._ensure_created()
        gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self._tex_id)


_dummy_shadow_texture: _DummyShadowTexture | None = None


def get_dummy_shadow_texture() -> _DummyShadowTexture:
    """
    Returns a 1x1 depth texture for sampler2DShadow placeholders.

    Used when shadow maps are not available but shader expects
    sampler2DShadow to be bound (required by AMD drivers).
    """
    global _dummy_shadow_texture

    if _dummy_shadow_texture is None:
        _dummy_shadow_texture = _DummyShadowTexture()

    return _dummy_shadow_texture


def reset_dummy_shadow_texture() -> None:
    """
    Reset the global dummy shadow texture.

    Call this when OpenGL context changes (e.g., between tests)
    to ensure the texture is recreated in the new context.
    """
    global _dummy_shadow_texture
    _dummy_shadow_texture = None
