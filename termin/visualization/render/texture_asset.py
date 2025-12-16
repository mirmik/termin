"""TextureAsset - Asset for texture data."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from termin.visualization.core.asset import Asset
from termin.visualization.render.texture_data import TextureData

if TYPE_CHECKING:
    import numpy as np


class TextureAsset(Asset):
    """
    Asset for texture image data.

    Stores TextureData (CPU data: pixels, size, format).
    Does NOT handle GPU upload - that's TextureGPU's responsibility.
    """

    def __init__(
        self,
        texture_data: TextureData | None = None,
        name: str = "texture",
        source_path: Path | str | None = None,
        uuid: str | None = None,
    ):
        """
        Initialize TextureAsset.

        Args:
            texture_data: TextureData (can be None for lazy loading)
            name: Human-readable name
            source_path: Path to source file for loading/reloading
            uuid: Existing UUID or None to generate new one
        """
        super().__init__(name=name, source_path=source_path, uuid=uuid)
        self._texture_data: TextureData | None = texture_data
        self._loaded = texture_data is not None

    @property
    def texture_data(self) -> TextureData | None:
        """Texture data."""
        return self._texture_data

    @texture_data.setter
    def texture_data(self, value: TextureData | None) -> None:
        """Set texture data and bump version."""
        self._texture_data = value
        self._loaded = value is not None
        self._bump_version()

    @property
    def width(self) -> int:
        """Texture width in pixels."""
        return self._texture_data.width if self._texture_data else 0

    @property
    def height(self) -> int:
        """Texture height in pixels."""
        return self._texture_data.height if self._texture_data else 0

    @property
    def channels(self) -> int:
        """Number of color channels."""
        return self._texture_data.channels if self._texture_data else 0

    def load(self) -> bool:
        """
        Load texture data from source_path.

        Returns:
            True if loaded successfully.
        """
        if self._source_path is None:
            return False

        try:
            self._texture_data = TextureData.from_file(self._source_path)
            self._loaded = True
            return True
        except Exception:
            return False

    def unload(self) -> None:
        """Unload texture data to free memory."""
        self._texture_data = None
        self._loaded = False

    # --- Factory methods ---

    @classmethod
    def from_file(cls, path: str | Path, name: str | None = None) -> "TextureAsset":
        """Create TextureAsset from image file."""
        texture_data = TextureData.from_file(path)
        return cls(
            texture_data=texture_data,
            name=name or Path(path).stem,
            source_path=path,
        )

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
        texture_data = TextureData.from_array(
            data,
            flip_x=flip_x,
            flip_y=flip_y,
            transpose=transpose,
        )
        return cls(texture_data=texture_data, name=name)

    @classmethod
    def white_1x1(cls) -> "TextureAsset":
        """Create 1x1 white pixel texture asset."""
        return cls(
            texture_data=TextureData.white_1x1(),
            name="__white_1x1__",
        )
