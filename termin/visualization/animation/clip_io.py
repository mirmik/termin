# termin/visualization/animation/clip_io.py
"""I/O functions for AnimationClip (.tanim files)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .clip import AnimationClip


def save_animation_clip(clip: "AnimationClip", path: str | Path) -> None:
    """
    Save AnimationClip to .tanim file (JSON format).

    Args:
        clip: AnimationClip to save
        path: Path to output file
    """
    path = Path(path)
    data = clip.serialize()
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_animation_clip(path: str | Path) -> "AnimationClip":
    """
    Load AnimationClip from .tanim file.

    Args:
        path: Path to .tanim file

    Returns:
        Loaded AnimationClip
    """
    from .clip import deserialize_clip

    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    return deserialize_clip(data)


def parse_animation_content(content: str) -> "AnimationClip":
    """
    Parse AnimationClip from JSON content string.

    Args:
        content: JSON content of .tanim file

    Returns:
        Parsed AnimationClip
    """
    from .clip import deserialize_clip

    data = json.loads(content)
    return deserialize_clip(data)


__all__ = ["save_animation_clip", "load_animation_clip", "parse_animation_content"]
