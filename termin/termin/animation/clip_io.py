"""I/O functions for TcAnimationClip (.tanim files)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from termin.visualization.animation._animation_native import TcAnimationClip


def save_animation_clip(clip: "TcAnimationClip", path: str | Path) -> None:
    """Save TcAnimationClip to .tanim file."""
    path = Path(path)
    data = clip.serialize()
    py_data = dict(data)
    path.write_text(json.dumps(py_data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_animation_clip(path: str | Path) -> "TcAnimationClip":
    """Load TcAnimationClip from .tanim file."""
    from termin.visualization.animation._animation_native import TcAnimationClip

    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))

    if "uuid" in data:
        clip = TcAnimationClip.from_uuid(data["uuid"])
        if clip.is_valid:
            return clip

    name = data.get("name", "")
    uuid = data.get("uuid", "")
    clip = TcAnimationClip.create(name, uuid)

    if "channels" in data:
        clip.set_channels(data["channels"])
        if "tps" in data:
            clip.set_tps(data["tps"])
        if "loop" in data:
            clip.set_loop(data["loop"])

    return clip


def parse_animation_content(content: str) -> "TcAnimationClip":
    """Parse TcAnimationClip from JSON content string."""
    from termin.visualization.animation._animation_native import TcAnimationClip

    data = json.loads(content)

    if "uuid" in data:
        clip = TcAnimationClip.from_uuid(data["uuid"])
        if clip.is_valid:
            return clip

    name = data.get("name", "")
    uuid = data.get("uuid", "")
    clip = TcAnimationClip.create(name, uuid)

    if "channels" in data:
        clip.set_channels(data["channels"])
        if "tps" in data:
            clip.set_tps(data["tps"])
        if "loop" in data:
            clip.set_loop(data["loop"])

    return clip


__all__ = ["save_animation_clip", "load_animation_clip", "parse_animation_content"]
