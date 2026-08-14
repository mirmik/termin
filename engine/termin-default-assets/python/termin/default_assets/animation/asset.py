"""Asset adapter for portable animation clip data."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from termin_assets import DataAsset

if TYPE_CHECKING:
    from termin.animation import TcAnimationClip


class AnimationClipAsset(DataAsset["TcAnimationClip"]):
    """Termin asset wrapper for a portable ``TcAnimationClip``."""

    _uses_binary = False

    def __init__(
        self,
        clip: "TcAnimationClip | None" = None,
        name: str = "animation",
        source_path: Path | str | None = None,
        uuid: str | None = None,
    ):
        super().__init__(data=clip, name=name, source_path=source_path, uuid=uuid)

    @property
    def clip(self) -> "TcAnimationClip | None":
        return self.data

    @clip.setter
    def clip(self, value: "TcAnimationClip | None") -> None:
        self.data = value

    @property
    def duration(self) -> float:
        data = self.data
        return data.duration if data else 0.0

    def _parse_content(self, content: str) -> "TcAnimationClip | None":
        from termin.animation.clip_io import parse_animation_content

        return parse_animation_content(content)

    @classmethod
    def from_clip(
        cls,
        clip: "TcAnimationClip",
        name: str | None = None,
        source_path: Path | str | None = None,
    ) -> "AnimationClipAsset":
        return cls(clip=clip, name=name or clip.name or "animation", source_path=source_path)
