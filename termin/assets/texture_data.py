"""TextureData - raw image data container."""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np


@dataclass
class TextureData:
    """
    Raw image data container.

    Similar to Mesh3 for meshes - holds CPU data without GPU knowledge.

    Attributes:
        data: Numpy array of shape (height, width, channels) with uint8 values.
        width: Texture width in pixels.
        height: Texture height in pixels.
        channels: Number of color channels (typically 4 for RGBA).
        flip_x: Mirror horizontally when uploading to GPU.
        flip_y: Flip vertically when uploading to GPU (default True for OpenGL).
        transpose: Swap X and Y axes when uploading to GPU.
        source_path: Path to source file (not used in operation, for serialization).
    """

    data: np.ndarray
    width: int
    height: int
    channels: int = 4
    flip_x: bool = False
    flip_y: bool = True  # OpenGL default
    transpose: bool = False
    source_path: str | None = None

    @classmethod
    def from_file(cls, path: str | Path) -> "TextureData":
        """
        Load texture data from image file.

        Args:
            path: Path to image file (PNG, JPG, etc.)

        Returns:
            TextureData with loaded image.
        """
        from PIL import Image
        from termin.loaders.texture_spec import TextureSpec

        # Load spec for this texture
        spec = TextureSpec.for_texture_file(path)

        # Load image
        image = Image.open(path).convert("RGBA")
        data = np.array(image, dtype=np.uint8)
        width, height = image.size

        return cls(
            data=data,
            width=width,
            height=height,
            channels=4,
            flip_x=spec.flip_x,
            flip_y=spec.flip_y,
            transpose=spec.transpose,
        )

    @classmethod
    def from_array(
        cls,
        data: np.ndarray,
        flip_x: bool = False,
        flip_y: bool = True,
        transpose: bool = False,
    ) -> "TextureData":
        """
        Create texture data from numpy array.

        Args:
            data: Numpy array of shape (height, width, channels).
            flip_x: Mirror horizontally.
            flip_y: Flip vertically.
            transpose: Swap X and Y axes.

        Returns:
            TextureData with provided data.
        """
        if len(data.shape) != 3:
            raise ValueError(f"Expected 3D array (height, width, channels), got shape {data.shape}")

        height, width, channels = data.shape
        return cls(
            data=data,
            width=width,
            height=height,
            channels=channels,
            flip_x=flip_x,
            flip_y=flip_y,
            transpose=transpose,
        )

    @classmethod
    def white_1x1(cls) -> "TextureData":
        """Create 1x1 white pixel texture."""
        data = np.array([[[255, 255, 255, 255]]], dtype=np.uint8)
        return cls(data=data, width=1, height=1, channels=4, flip_y=False)

    def get_upload_data(self) -> tuple[np.ndarray, tuple[int, int]]:
        """
        Get data ready for GPU upload (with transformations applied).

        Returns:
            Tuple of (transformed_data, (width, height)).
        """
        data = self.data
        size = (self.width, self.height)

        if self.transpose:
            data = np.swapaxes(data, 0, 1).copy()
            size = (size[1], size[0])

        if self.flip_x:
            data = data[:, ::-1, :].copy()

        if self.flip_y:
            data = data[::-1, :, :].copy()

        return data, size

    # ----------------------------------------------------------------
    # Сериализация
    # ----------------------------------------------------------------

    def direct_serialize(self) -> dict:
        """
        Сериализует текстуру в словарь.

        Если source_path задан, возвращает ссылку на файл.
        Иначе сериализует данные в base64.
        """
        if self.source_path is not None:
            return {
                "type": "path",
                "path": self.source_path,
            }

        # Inline сериализация через base64
        data_bytes = self.data.tobytes()
        data_b64 = base64.b64encode(data_bytes).decode("ascii")

        return {
            "type": "inline",
            "width": self.width,
            "height": self.height,
            "channels": self.channels,
            "flip_x": self.flip_x,
            "flip_y": self.flip_y,
            "transpose": self.transpose,
            "data_b64": data_b64,
        }

    @classmethod
    def direct_deserialize(cls, data: dict) -> "TextureData":
        """Десериализует текстуру из словаря."""
        width = data["width"]
        height = data["height"]
        channels = data.get("channels", 4)

        data_bytes = base64.b64decode(data["data_b64"])
        pixels = np.frombuffer(data_bytes, dtype=np.uint8).reshape(height, width, channels)

        source_path = data.get("path") if data.get("type") == "path" else None

        return cls(
            data=pixels,
            width=width,
            height=height,
            channels=channels,
            flip_x=data.get("flip_x", False),
            flip_y=data.get("flip_y", True),
            transpose=data.get("transpose", False),
            source_path=source_path,
        )
