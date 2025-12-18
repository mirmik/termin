"""AnimationClipAsset - Asset for animation clip data."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from termin.visualization.core.data_asset import DataAsset

if TYPE_CHECKING:
    from termin.visualization.animation.clip import AnimationClip


class AnimationClipAsset(DataAsset["AnimationClip"]):
    """
    Asset for animation clip data.

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
        """AnimationClip data (lazy-loaded)."""
        if self._data is None and not self._loaded:
            self.ensure_loaded()
        return self._data

    @clip.setter
    def clip(self, value: "AnimationClip | None") -> None:
        """Set clip and bump version."""
        self.data = value

    @property
    def duration(self) -> float:
        """Animation duration in seconds."""
        return self._data.duration if self._data else 0.0

    # --- Content parsing ---

    def _parse_content(self, content: str) -> "AnimationClip | None":
        """Parse animation content from file."""
        from termin.visualization.animation.clip_io import parse_animation_content

        return parse_animation_content(content)

    # --- Embedded asset support (from GLB) ---

    def _extract_from_parent(self) -> bool:
        """Extract animation data from parent GLBAsset (parent already loaded by base class)."""
        if self._parent_asset is None or self._parent_key is None:
            return False

        from termin.visualization.core.glb_asset import GLBAsset
        from termin.visualization.animation.clip import AnimationClip

        if not isinstance(self._parent_asset, GLBAsset):
            return False

        glb = self._parent_asset
        if glb.scene_data is None:
            return False

        # Find animation by name in parent's GLB data
        for glb_anim in glb.scene_data.animations:
            if glb_anim.name == self._parent_key:
                self._data = AnimationClip.from_glb_clip(glb_anim)
                if self._data is not None:
                    self._loaded = True
                    return True
        return False

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
