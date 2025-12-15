# termin/loaders/texture_spec.py
"""Texture import specification - settings for loading texture files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TextureSpec:
    """
    Import settings for texture files.

    Stored as .spec file next to the texture (e.g., image.png.spec).
    """

    # Flip texture horizontally (mirror X)
    flip_x: bool = False
    # Flip texture vertically for OpenGL (origin at bottom-left)
    flip_y: bool = True
    # Transpose texture (swap X and Y axes)
    transpose: bool = False

    @classmethod
    def load(cls, spec_path: str | Path) -> "TextureSpec":
        """Load spec from file."""
        path = Path(spec_path)
        if not path.exists():
            return cls()

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls(
                flip_x=data.get("flip_x", False),
                flip_y=data.get("flip_y", True),
                transpose=data.get("transpose", False),
            )
        except Exception:
            return cls()

    @classmethod
    def for_texture_file(cls, texture_path: str | Path) -> "TextureSpec":
        """Load spec for a texture file (looks for texture_path.spec)."""
        spec_path = Path(str(texture_path) + ".spec")
        return cls.load(spec_path)

    def save(self, spec_path: str | Path) -> None:
        """Save spec to file."""
        path = Path(spec_path)
        data = {
            "flip_x": self.flip_x,
            "flip_y": self.flip_y,
            "transpose": self.transpose,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def save_for_texture(self, texture_path: str | Path) -> None:
        """Save spec next to texture file."""
        spec_path = Path(str(texture_path) + ".spec")
        self.save(spec_path)
