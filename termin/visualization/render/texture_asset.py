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

    def load_from_content(
        self,
        content: bytes | None,
        spec_data: dict | None = None,
        has_uuid_in_spec: bool = False,
    ) -> bool:
        """
        Load texture from binary content.

        Args:
            content: Binary image data (PNG/JPG/etc)
            spec_data: Spec file data with flip_x, flip_y, transpose
            has_uuid_in_spec: If True, spec file already has UUID (don't save)

        Returns:
            True if loaded successfully.
        """
        if content is None:
            return False

        try:
            import io

            import numpy as np
            from PIL import Image

            # Load image from bytes
            image = Image.open(io.BytesIO(content)).convert("RGBA")
            data = np.array(image, dtype=np.uint8)
            width, height = image.size

            # Get flip settings from spec_data
            flip_x = spec_data.get("flip_x", False) if spec_data else False
            flip_y = spec_data.get("flip_y", True) if spec_data else True
            transpose = spec_data.get("transpose", False) if spec_data else False

            self._texture_data = TextureData(
                data=data,
                width=width,
                height=height,
                channels=4,
                flip_x=flip_x,
                flip_y=flip_y,
                transpose=transpose,
                source_path=str(self._source_path) if self._source_path else None,
            )
            self._loaded = True

            # Save spec file if no UUID was in spec
            if not has_uuid_in_spec and self._source_path:
                self._save_spec_file(spec_data)

            return True
        except Exception as e:
            print(f"[TextureAsset] Failed to load content: {e}")
            return False

    def _save_spec_file(self, existing_spec_data: dict | None = None) -> bool:
        """Save UUID to spec file, preserving existing settings."""
        if self._source_path is None:
            return False

        from termin.editor.project_file_watcher import FilePreLoader

        # Merge existing spec data with UUID
        spec_data = dict(existing_spec_data) if existing_spec_data else {}
        spec_data["uuid"] = self.uuid

        if FilePreLoader.write_spec_file(str(self._source_path), spec_data):
            self.mark_just_saved()
            print(f"[TextureAsset] Added UUID to spec: {self._name}")
            return True
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
