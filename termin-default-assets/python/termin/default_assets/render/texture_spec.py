# termin/loaders/texture_spec.py
"""Texture import specification - settings for loading texture files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from tcbase import log


@dataclass
class TextureSpec:
    """
    Import settings for texture files.

    Stored as .meta file next to the texture (e.g., image.png.meta).
    """

    # Flip texture horizontally (mirror X)
    flip_x: bool = False
    # Flip texture vertically to use the engine's bottom-left texture origin convention.
    flip_y: bool = True
    # Transpose texture (swap X and Y axes)
    transpose: bool = False
    # Default sampler used by scene-level textured renderers.
    filter: str = "linear"
    mipmaps: bool = False
    wrap: str = "clamp"
    # Pixel interpretation. Textures remain straight-alpha in CPU storage.
    color_space: str = "srgb"
    alpha_mode: str = "straight"

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
                filter=data.get("filter", "linear"),
                mipmaps=data.get("mipmaps", False),
                wrap=data.get("wrap", "clamp"),
                color_space=data.get("color_space", "srgb"),
                alpha_mode=data.get("alpha_mode", "straight"),
            )
        except Exception:
            log.warning(f"[TextureSpec] Failed to load spec from {spec_path}", exc_info=True)
            return cls()

    @classmethod
    def for_texture_file(cls, texture_path: str | Path) -> "TextureSpec":
        """Load spec for a texture file from texture_path.meta."""
        meta_path = Path(str(texture_path) + ".meta")
        return cls.load(meta_path)

    def save(self, spec_path: str | Path, preserve_existing: bool = False) -> None:
        """Save spec to file.

        Args:
            spec_path: Path to save the spec file.
            preserve_existing: If True, preserve fields from existing file (like uuid).
        """
        path = Path(spec_path)

        # Read existing data to preserve fields like uuid
        existing_data = {}
        if preserve_existing and path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
            except Exception:
                log.warning(f"[TextureSpec] Failed to read existing spec {path}", exc_info=True)

        # Update with our fields
        data = existing_data.copy()
        data.update({
            "flip_x": self.flip_x,
            "flip_y": self.flip_y,
            "transpose": self.transpose,
            "filter": self.filter,
            "mipmaps": self.mipmaps,
            "wrap": self.wrap,
            "color_space": self.color_space,
            "alpha_mode": self.alpha_mode,
        })
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def save_for_texture(self, texture_path: str | Path) -> None:
        """Save spec next to texture file (.meta format).

        Preserves existing fields like uuid from the .meta file.
        """
        meta_path = Path(str(texture_path) + ".meta")
        self.save(meta_path, preserve_existing=True)
