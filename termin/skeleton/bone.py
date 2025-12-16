"""Bone class for skeletal animation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class Bone:
    """
    Single bone in a skeleton hierarchy.

    Attributes:
        name: Human-readable bone name (e.g., "LeftArm", "Spine")
        index: Index in skeleton bone array (used for GPU upload)
        parent_index: Index of parent bone (-1 for root bones)
        inverse_bind_matrix: 4x4 matrix transforming from mesh space to bone local space
    """

    name: str
    index: int
    parent_index: int
    inverse_bind_matrix: np.ndarray  # (4, 4) float32

    def __post_init__(self):
        """Ensure inverse_bind_matrix is proper shape and type."""
        self.inverse_bind_matrix = np.asarray(
            self.inverse_bind_matrix, dtype=np.float32
        ).reshape(4, 4)

    @property
    def is_root(self) -> bool:
        """True if this bone has no parent."""
        return self.parent_index < 0

    def serialize(self) -> dict:
        """Serialize bone to dict for JSON storage."""
        return {
            "name": self.name,
            "index": self.index,
            "parent_index": self.parent_index,
            "inverse_bind_matrix": self.inverse_bind_matrix.tolist(),
        }

    @classmethod
    def deserialize(cls, data: dict) -> "Bone":
        """Deserialize bone from dict."""
        return cls(
            name=data["name"],
            index=data["index"],
            parent_index=data["parent_index"],
            inverse_bind_matrix=np.array(data["inverse_bind_matrix"], dtype=np.float32),
        )

    def __repr__(self) -> str:
        parent_str = f"parent={self.parent_index}" if self.parent_index >= 0 else "root"
        return f"<Bone {self.index}: '{self.name}' ({parent_str})>"
