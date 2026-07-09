"""TextureAsset - Asset for texture data."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from termin_assets import DataAsset
from tgfx import TcTexture

if TYPE_CHECKING:
    import numpy as np


class TextureAsset(DataAsset[TcTexture]):
    """
    Asset for texture image data.

    IMPORTANT: Create through ResourceManager, not directly.
    This ensures proper registration and avoids duplicates.

    Stores TcTexture (handle to tc_texture in C registry). Renderer/device-specific
    upload and cache invalidation are handled outside the asset layer.
    """

    _uses_binary = True  # PNG/JPG binary format

    def __init__(
        self,
        texture_data: TcTexture | None = None,
        name: str = "texture",
        source_path: Path | str | None = None,
        uuid: str | None = None,
    ):
        super().__init__(data=texture_data, name=name, source_path=source_path, uuid=uuid)
        # Spec settings (parsed from spec file)
        self._flip_x: bool = False
        self._flip_y: bool = True  # Default import convention: texture origin at bottom-left.
        self._transpose: bool = False

    # --- Convenience property ---

    @property
    def texture_data(self) -> TcTexture | None:
        """Texture data (lazy-loaded)."""
        return self.data

    @texture_data.setter
    def texture_data(self, value: TcTexture | None) -> None:
        """Set texture data and bump version."""
        self.data = value

    @property
    def width(self) -> int:
        """Texture width in pixels."""
        data = self.data
        return data.width if data and data.is_valid else 0

    @property
    def height(self) -> int:
        """Texture height in pixels."""
        data = self.data
        return data.height if data and data.is_valid else 0

    @property
    def channels(self) -> int:
        """Number of color channels."""
        data = self.data
        return data.channels if data and data.is_valid else 0

    @property
    def flip_x(self) -> bool:
        """Texture horizontal flip import flag."""
        return self._flip_x

    @property
    def flip_y(self) -> bool:
        """Texture vertical flip import flag."""
        return self._flip_y

    @property
    def transpose(self) -> bool:
        """Texture transpose import flag."""
        return self._transpose

    # --- Spec parsing ---

    def _parse_spec_fields(self, spec_data: dict) -> None:
        """Parse texture-specific spec fields."""
        self._flip_x = spec_data.get("flip_x", False)
        self._flip_y = spec_data.get("flip_y", True)
        self._transpose = spec_data.get("transpose", False)

    def _build_spec_data(self) -> dict:
        """Build spec data with texture settings."""
        spec = super()._build_spec_data()
        # Only save non-default values
        if self._flip_x:
            spec["flip_x"] = True
        if not self._flip_y:  # Default is True
            spec["flip_y"] = False
        if self._transpose:
            spec["transpose"] = True
        return spec

    # --- Content parsing ---

    def _texture_from_decoded(self, decoded, source_path: str = "") -> TcTexture:
        data = decoded.to_numpy(copy=True)
        return TcTexture.from_data(
            data=data,
            width=decoded.width,
            height=decoded.height,
            channels=decoded.channels,
            flip_x=self._flip_x,
            flip_y=self._flip_y,
            transpose=self._transpose,
            name=self._name,
            source_path=source_path,
            uuid=self.uuid,
        )

    def _parse_content(self, content: bytes) -> TcTexture | None:
        """Parse image bytes into TcTexture."""
        from termin.image import decode_rgba8

        source_path = str(self._source_path) if self._source_path else ""
        decoded = decode_rgba8(content, source_path or self._name)
        return self._texture_from_decoded(decoded, source_path)

    # --- Factory methods ---

    @classmethod
    def from_file(cls, path: str | Path, name: str | None = None) -> "TextureAsset":
        """Create TextureAsset from image file."""
        from termin.default_assets.render.texture_spec import TextureSpec
        from termin.image import decode_rgba8_file

        path = Path(path)
        spec = TextureSpec.for_texture_file(path)
        decoded = decode_rgba8_file(path)

        texture_name = name or path.stem
        asset = cls(
            texture_data=None,
            name=texture_name,
            source_path=path,
        )
        asset._flip_x = spec.flip_x
        asset._flip_y = spec.flip_y
        asset._transpose = spec.transpose
        asset.texture_data = asset._texture_from_decoded(decoded, str(path))
        return asset

    @classmethod
    def from_data(
        cls,
        data: "np.ndarray",
        name: str = "texture",
        flip_x: bool = False,
        flip_y: bool = True,
        transpose: bool = False,
    ) -> "TextureAsset":
        """Create TextureAsset from numpy array."""
        height, width = data.shape[:2]
        channels = data.shape[2] if data.ndim == 3 else 1

        asset = cls(texture_data=None, name=name)
        texture_data = TcTexture.from_data(
            data=data,
            width=width,
            height=height,
            channels=channels,
            flip_x=flip_x,
            flip_y=flip_y,
            transpose=transpose,
            name=name,
            uuid=asset.uuid,
        )
        asset.texture_data = texture_data
        return asset

    @classmethod
    def white_1x1(cls) -> "TextureAsset":
        """Create 1x1 white pixel texture asset."""
        return cls(
            texture_data=TcTexture.white_1x1(),
            name="__white_1x1__",
        )
