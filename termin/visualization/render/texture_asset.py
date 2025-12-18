"""TextureAsset - Asset for texture data."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from termin.visualization.core.data_asset import DataAsset
from termin.visualization.render.texture_data import TextureData

if TYPE_CHECKING:
    import numpy as np
    from termin.visualization.render.texture_gpu import TextureGPU


class TextureAsset(DataAsset[TextureData]):
    """
    Asset for texture image data.

    IMPORTANT: Create through ResourceManager, not directly.
    This ensures proper registration and avoids duplicates.

    Stores TextureData (CPU data: pixels, size, format) and TextureGPU (GPU resources).
    GPU resources are created on demand when .gpu property is accessed.
    """

    _uses_binary = True  # PNG/JPG binary format

    def __init__(
        self,
        texture_data: TextureData | None = None,
        name: str = "texture",
        source_path: Path | str | None = None,
        uuid: str | None = None,
    ):
        super().__init__(data=texture_data, name=name, source_path=source_path, uuid=uuid)
        # Spec settings (parsed from spec file)
        self._flip_x: bool = False
        self._flip_y: bool = True  # Default: flip Y for OpenGL
        self._transpose: bool = False
        # GPU resources (created on demand)
        self._gpu: "TextureGPU | None" = None

    # --- Convenience property ---

    @property
    def texture_data(self) -> TextureData | None:
        """Texture data (lazy-loaded)."""
        return self.data

    @texture_data.setter
    def texture_data(self, value: TextureData | None) -> None:
        """Set texture data and bump version."""
        self.data = value

    @property
    def width(self) -> int:
        """Texture width in pixels."""
        data = self.data
        return data.width if data else 0

    @property
    def height(self) -> int:
        """Texture height in pixels."""
        data = self.data
        return data.height if data else 0

    @property
    def channels(self) -> int:
        """Number of color channels."""
        data = self.data
        return data.channels if data else 0

    # --- GPU resources ---

    @property
    def gpu(self) -> "TextureGPU":
        """Get or create TextureGPU for rendering."""
        if self._gpu is None:
            from termin.visualization.render.texture_gpu import TextureGPU
            self._gpu = TextureGPU()
        return self._gpu

    def delete_gpu(self) -> None:
        """Delete GPU resources."""
        if self._gpu is not None:
            self._gpu.delete()
            self._gpu = None

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

    def _parse_content(self, content: bytes) -> TextureData | None:
        """Parse image bytes into TextureData."""
        import io

        import numpy as np
        from PIL import Image

        image = Image.open(io.BytesIO(content)).convert("RGBA")
        data = np.array(image, dtype=np.uint8)
        width, height = image.size

        return TextureData(
            data=data,
            width=width,
            height=height,
            channels=4,
            flip_x=self._flip_x,
            flip_y=self._flip_y,
            transpose=self._transpose,
            source_path=str(self._source_path) if self._source_path else None,
        )

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
