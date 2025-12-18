"""SkeletonAsset - Asset wrapper for skeleton data with UUID tracking."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from termin.visualization.core.data_asset import DataAsset

if TYPE_CHECKING:
    from .skeleton import SkeletonData


class SkeletonAsset(DataAsset["SkeletonData"]):
    """
    Asset wrapper for SkeletonData with UUID tracking.

    IMPORTANT: Create through ResourceManager.get_or_create_skeleton_asset(),
    not directly. This ensures proper registration and avoids duplicates.

    Used by ResourceManager for skeleton registration and lookup.

    Note: Skeletons are typically loaded from GLB files (embedded),
    not as standalone files.
    """

    _uses_binary = False  # Not used for standalone loading

    def __init__(
        self,
        skeleton_data: "SkeletonData | None" = None,
        name: str = "skeleton",
        source_path: Path | str | None = None,
        uuid: str | None = None,
    ):
        super().__init__(data=skeleton_data, name=name, source_path=source_path, uuid=uuid)

    # --- Convenience property ---

    @property
    def skeleton_data(self) -> "SkeletonData | None":
        """Get skeleton data (lazy-loaded via parent's data property)."""
        return self.data

    @skeleton_data.setter
    def skeleton_data(self, value: "SkeletonData | None") -> None:
        """Set skeleton data and bump version."""
        self.data = value

    # --- Content parsing ---

    def _parse_content(self, content: str) -> "SkeletonData | None":
        """
        Parse skeleton from content.

        Note: Skeletons are typically loaded from GLB, not standalone files.
        This method exists for potential future standalone skeleton format.
        """
        return None

    # --- Convenience methods ---

    def get_bone_count(self) -> int:
        """Get number of bones in skeleton."""
        data = self.data
        return data.get_bone_count() if data else 0

    # --- Serialization ---

    def serialize(self) -> dict:
        """Serialize skeleton asset to dict."""
        data = {
            "uuid": self.uuid,
            "name": self._name,
        }
        if self._data is not None:
            data["skeleton_data"] = self._data.serialize()
        return data

    @classmethod
    def deserialize(cls, data: dict) -> "SkeletonAsset":
        """Deserialize skeleton asset from dict."""
        from .skeleton import SkeletonData

        skeleton_data = None
        if "skeleton_data" in data:
            skeleton_data = SkeletonData.deserialize(data["skeleton_data"])

        return cls(
            skeleton_data=skeleton_data,
            name=data.get("name", "skeleton"),
            uuid=data.get("uuid"),
        )

    # --- Factory methods ---

    @classmethod
    def from_skeleton_data(
        cls,
        skeleton_data: "SkeletonData",
        name: str | None = None,
        source_path: str | Path | None = None,
        uuid: str | None = None,
    ) -> "SkeletonAsset":
        """Create SkeletonAsset from existing SkeletonData."""
        return cls(
            skeleton_data=skeleton_data,
            name=name or "skeleton",
            source_path=source_path,
            uuid=uuid,
        )

    def __repr__(self) -> str:
        bone_count = self.get_bone_count()
        return f"<SkeletonAsset '{self._name}' bones={bone_count}>"
