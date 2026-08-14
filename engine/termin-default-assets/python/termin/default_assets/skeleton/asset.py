"""Asset adapter for portable skeleton data."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from termin_assets import DataAsset

if TYPE_CHECKING:
    from termin.skeleton import TcSkeleton


class SkeletonAsset(DataAsset["TcSkeleton"]):
    """Termin asset wrapper for a portable ``TcSkeleton``."""

    _uses_binary = False

    def __init__(
        self,
        skeleton_data: "TcSkeleton | None" = None,
        name: str = "skeleton",
        source_path: Path | str | None = None,
        uuid: str | None = None,
    ):
        super().__init__(data=skeleton_data, name=name, source_path=source_path, uuid=uuid)

    @property
    def skeleton_data(self) -> "TcSkeleton | None":
        return self.data

    @skeleton_data.setter
    def skeleton_data(self, value: "TcSkeleton | None") -> None:
        self.data = value

    def _parse_content(self, content: str) -> "TcSkeleton | None":
        return None

    def get_bone_count(self) -> int:
        data = self.data
        return data.bone_count if data and data.is_valid else 0

    def serialize(self) -> dict:
        data = {
            "uuid": self.uuid,
            "name": self._name,
        }
        if self._data is not None and self._data.is_valid:
            data["skeleton_uuid"] = self._data.uuid
        return data

    @classmethod
    def deserialize(cls, data: dict) -> "SkeletonAsset":
        from termin.skeleton import TcSkeleton

        skeleton = None
        if "skeleton_uuid" in data:
            skeleton = TcSkeleton.from_uuid(data["skeleton_uuid"])
        return cls(
            skeleton_data=skeleton,
            name=data.get("name", "skeleton"),
            uuid=data.get("uuid"),
        )

    @classmethod
    def from_tc_skeleton(
        cls,
        skeleton: "TcSkeleton",
        name: str | None = None,
        source_path: str | Path | None = None,
        uuid: str | None = None,
    ) -> "SkeletonAsset":
        return cls(
            skeleton_data=skeleton,
            name=name or "skeleton",
            source_path=source_path,
            uuid=uuid,
        )

    def __repr__(self) -> str:
        return f"<SkeletonAsset '{self._name}' bones={self.get_bone_count()}>"
