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
        bind_translation: Local translation in bind pose (from GLB node)
        bind_rotation: Local rotation quaternion [x,y,z,w] in bind pose
        bind_scale: Local scale in bind pose
    """

    name: str
    index: int
    parent_index: int
    inverse_bind_matrix: np.ndarray  # (4, 4) float32
    bind_translation: np.ndarray = None  # (3,) float32
    bind_rotation: np.ndarray = None  # (4,) float32 [x,y,z,w]
    bind_scale: np.ndarray = None  # (3,) float32

    def __post_init__(self):
        """Ensure arrays are proper shape and type."""
        self.inverse_bind_matrix = np.asarray(
            self.inverse_bind_matrix, dtype=np.float32
        ).reshape(4, 4)

        # Default bind pose to identity if not provided
        if self.bind_translation is None:
            self.bind_translation = np.zeros(3, dtype=np.float32)
        else:
            self.bind_translation = np.asarray(self.bind_translation, dtype=np.float32)

        if self.bind_rotation is None:
            self.bind_rotation = np.array([0, 0, 0, 1], dtype=np.float32)
        else:
            self.bind_rotation = np.asarray(self.bind_rotation, dtype=np.float32)

        if self.bind_scale is None:
            self.bind_scale = np.ones(3, dtype=np.float32)
        else:
            self.bind_scale = np.asarray(self.bind_scale, dtype=np.float32)

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
            "bind_translation": self.bind_translation.tolist(),
            "bind_rotation": self.bind_rotation.tolist(),
            "bind_scale": self.bind_scale.tolist(),
        }

    @classmethod
    def deserialize(cls, data: dict) -> "Bone":
        """Deserialize bone from dict."""
        return cls(
            name=data["name"],
            index=data["index"],
            parent_index=data["parent_index"],
            inverse_bind_matrix=np.array(data["inverse_bind_matrix"], dtype=np.float32),
            bind_translation=np.array(data.get("bind_translation", [0, 0, 0]), dtype=np.float32),
            bind_rotation=np.array(data.get("bind_rotation", [0, 0, 0, 1]), dtype=np.float32),
            bind_scale=np.array(data.get("bind_scale", [1, 1, 1]), dtype=np.float32),
        )

    def __repr__(self) -> str:
        parent_str = f"parent={self.parent_index}" if self.parent_index >= 0 else "root"
        return f"<Bone {self.index}: '{self.name}' ({parent_str})>"
