"""AnimationClipAsset - Asset for animation clip data."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from termin.assets.data_asset import DataAsset

if TYPE_CHECKING:
    from termin.visualization.animation.clip import AnimationClip


class AnimationClipAsset(DataAsset["AnimationClip"]):
    """
    Asset for animation clip data.

    IMPORTANT: Create through ResourceManager.get_or_create_animation_clip_asset(),
    not directly. This ensures proper registration and avoids duplicates.

    Stores AnimationClip (channels, duration, etc).

    Can be loaded from:
    - Standalone .anim files
    - GLB files (embedded, via parent asset)
    """

    _uses_binary = False  # .anim files are text/JSON

    def __init__(
        self,
        clip: "AnimationClip | None" = None,
        name: str = "animation",
        source_path: Path | str | None = None,
        uuid: str | None = None,
    ):
        super().__init__(data=clip, name=name, source_path=source_path, uuid=uuid)

    # --- Convenience property ---

    @property
    def clip(self) -> "AnimationClip | None":
        """AnimationClip data (lazy-loaded via parent's data property)."""
        return self.data

    @clip.setter
    def clip(self, value: "AnimationClip | None") -> None:
        """Set clip and bump version."""
        self.data = value

    @property
    def duration(self) -> float:
        """Animation duration in seconds."""
        data = self.data
        return data.duration if data else 0.0

    # --- Content parsing ---

    def _parse_content(self, content: str) -> "AnimationClip | None":
        """Parse animation content from file."""
        from termin.visualization.animation.clip_io import parse_animation_content

        return parse_animation_content(content)

    # --- Factory methods ---

    @classmethod
    def from_clip(
        cls,
        clip: "AnimationClip",
        name: str | None = None,
        source_path: Path | str | None = None,
    ) -> "AnimationClipAsset":
        """Create AnimationClipAsset from existing AnimationClip."""
        asset_name = name or clip.name or "animation"
        return cls(clip=clip, name=asset_name, source_path=source_path)
