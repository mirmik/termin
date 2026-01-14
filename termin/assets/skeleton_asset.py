"""SkeletonAsset - Asset wrapper for TcSkeleton with UUID tracking."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from termin.assets.data_asset import DataAsset

if TYPE_CHECKING:
    from termin.skeleton import TcSkeleton


class SkeletonAsset(DataAsset["TcSkeleton"]):
    """
    Asset wrapper for TcSkeleton with UUID tracking.

    IMPORTANT: Create through ResourceManager.get_or_create_skeleton_asset(),
    not directly. This ensures proper registration and avoids duplicates.

    Used by ResourceManager for skeleton registration and lookup.

    Note: Skeletons are typically loaded from GLB files (embedded),
    not as standalone files.
    """

    _uses_binary = False  # Not used for standalone loading

    def __init__(
        self,
        skeleton_data: "TcSkeleton | None" = None,
        name: str = "skeleton",
        source_path: Path | str | None = None,
        uuid: str | None = None,
    ):
        super().__init__(data=skeleton_data, name=name, source_path=source_path, uuid=uuid)

    # --- Convenience property ---

    @property
    def skeleton_data(self) -> "TcSkeleton | None":
        """Get skeleton data (lazy-loaded via parent's data property)."""
        return self.data

    @skeleton_data.setter
    def skeleton_data(self, value: "TcSkeleton | None") -> None:
        """Set skeleton data and bump version."""
        self.data = value

    # --- Content parsing ---

    def _parse_content(self, content: str) -> "TcSkeleton | None":
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
        return data.bone_count if data and data.is_valid else 0

    # --- Serialization ---

    def serialize(self) -> dict:
        """Serialize skeleton asset to dict."""
        data = {
            "uuid": self.uuid,
            "name": self._name,
        }
        if self._data is not None and self._data.is_valid:
            data["skeleton_uuid"] = self._data.uuid
        return data

    @classmethod
    def deserialize(cls, data: dict) -> "SkeletonAsset":
        """Deserialize skeleton asset from dict."""
        from termin.skeleton import TcSkeleton

        skeleton = None
        if "skeleton_uuid" in data:
            skeleton = TcSkeleton.from_uuid(data["skeleton_uuid"])

        return cls(
            skeleton_data=skeleton,
            name=data.get("name", "skeleton"),
            uuid=data.get("uuid"),
        )

    # --- Factory methods ---

    @classmethod
    def from_tc_skeleton(
        cls,
        skeleton: "TcSkeleton",
        name: str | None = None,
        source_path: str | Path | None = None,
        uuid: str | None = None,
    ) -> "SkeletonAsset":
        """Create SkeletonAsset from existing TcSkeleton."""
        return cls(
            skeleton_data=skeleton,
            name=name or "skeleton",
            source_path=source_path,
            uuid=uuid,
        )

    def __repr__(self) -> str:
        bone_count = self.get_bone_count()
        return f"<SkeletonAsset '{self._name}' bones={bone_count}>"
