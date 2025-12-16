"""TextureData - raw image data container."""

from __future__ import annotations

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
    """

    data: np.ndarray
    width: int
    height: int
    channels: int = 4
    flip_x: bool = False
    flip_y: bool = True  # OpenGL default
    transpose: bool = False

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
