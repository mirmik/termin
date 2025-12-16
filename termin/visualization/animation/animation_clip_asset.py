"""AnimationClipAsset - Asset for animation clip data."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from termin.visualization.core.asset import Asset

if TYPE_CHECKING:
    from termin.visualization.animation.clip import AnimationClip


class AnimationClipAsset(Asset):
    """
    Asset for animation clip data.

    Stores AnimationClip (channels, duration, etc).
    """

    def __init__(
        self,
        clip: "AnimationClip | None" = None,
        name: str = "animation",
        source_path: Path | str | None = None,
        uuid: str | None = None,
    ):
        """
        Initialize AnimationClipAsset.

        Args:
            clip: AnimationClip data (can be None for lazy loading)
            name: Human-readable name
            source_path: Path to source file for loading/reloading
            uuid: Existing UUID or None to generate new one
        """
        super().__init__(name=name, source_path=source_path, uuid=uuid)
        self._clip: "AnimationClip | None" = clip
        self._loaded = clip is not None

    @property
    def clip(self) -> "AnimationClip | None":
        """AnimationClip data."""
        return self._clip

    @clip.setter
    def clip(self, value: "AnimationClip | None") -> None:
        """Set clip and bump version."""
        self._clip = value
        self._loaded = value is not None
        self._bump_version()

    @property
    def duration(self) -> float:
        """Animation duration in seconds."""
        return self._clip.duration if self._clip else 0.0

    def load(self) -> bool:
        """
        Load animation clip from source_path.

        Returns:
            True if loaded successfully.
        """
        if self._source_path is None:
            return False

        try:
            from termin.visualization.animation.io import load_animation_clip

            self._clip = load_animation_clip(str(self._source_path))
            if self._clip is not None:
                self._loaded = True
                return True
        except Exception:
            pass
        return False

    def unload(self) -> None:
        """Unload clip to free memory."""
        self._clip = None
        self._loaded = False

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
