"""SkeletonAsset - Asset wrapper for skeleton data with UUID tracking."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from termin.visualization.core.asset import Asset

if TYPE_CHECKING:
    from .skeleton import SkeletonData


class SkeletonAsset(Asset):
    """
    Asset wrapper for SkeletonData with UUID tracking.

    Used by ResourceManager for skeleton registration and lookup.
    """

    def __init__(
        self,
        skeleton_data: "SkeletonData | None" = None,
        name: str = "skeleton",
        source_path: Path | str | None = None,
        uuid: str | None = None,
    ):
        """
        Initialize SkeletonAsset.

        Args:
            skeleton_data: The skeleton data (can be None for lazy loading)
            name: Human-readable name
            source_path: Path to source file (GLB)
            uuid: Existing UUID or None to generate new one
        """
        super().__init__(name=name, source_path=source_path, uuid=uuid)
        self._skeleton_data: "SkeletonData | None" = skeleton_data
        self._loaded = skeleton_data is not None

    @property
    def skeleton_data(self) -> "SkeletonData | None":
        """Get skeleton data."""
        return self._skeleton_data

    @skeleton_data.setter
    def skeleton_data(self, value: "SkeletonData | None") -> None:
        """Set skeleton data and bump version."""
        self._skeleton_data = value
        self._loaded = value is not None
        self._bump_version()

    def load(self) -> bool:
        """
        Load skeleton from source.

        Note: Skeletons are typically loaded as part of GLB files,
        not standalone. This is a placeholder for future use.
        """
        return self._loaded

    def unload(self) -> None:
        """Unload skeleton data to free memory."""
        self._skeleton_data = None
        self._loaded = False

    def get_bone_count(self) -> int:
        """Get number of bones in skeleton."""
        if self._skeleton_data is None:
            return 0
        return self._skeleton_data.get_bone_count()

    def serialize(self) -> dict:
        """Serialize skeleton asset to dict."""
        data = {
            "uuid": self.uuid,
            "name": self._name,
        }
        if self._skeleton_data is not None:
            data["skeleton_data"] = self._skeleton_data.serialize()
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
