"""Skeleton data and runtime instance classes."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np

from .bone import Bone


class SkeletonData:
    """
    Immutable skeleton definition (bones hierarchy and inverse bind matrices).

    This is the "template" loaded from GLB/FBX files.
    SkeletonInstance holds mutable runtime state.
    """

    def __init__(
        self,
        bones: List[Bone],
        root_bone_indices: List[int] | None = None,
    ):
        """
        Initialize skeleton data.

        Args:
            bones: List of bones, ordered so that parents come before children
            root_bone_indices: Indices of root bones (computed if not provided)
        """
        self.bones = bones
        self._bone_name_map: Dict[str, int] = {b.name: b.index for b in bones}

        # Compute root bones if not provided
        if root_bone_indices is not None:
            self.root_bone_indices = root_bone_indices
        else:
            self.root_bone_indices = [b.index for b in bones if b.is_root]

    def get_bone_by_name(self, name: str) -> Bone | None:
        """Find bone by name."""
        idx = self._bone_name_map.get(name)
        return self.bones[idx] if idx is not None else None

    def get_bone_index(self, name: str) -> int:
        """Get bone index by name. Returns -1 if not found."""
        return self._bone_name_map.get(name, -1)

    def get_bone_count(self) -> int:
        """Number of bones in skeleton."""
        return len(self.bones)

    def serialize(self) -> dict:
        """Serialize skeleton data to dict."""
        return {
            "bones": [b.serialize() for b in self.bones],
            "root_bone_indices": self.root_bone_indices,
        }

    @classmethod
    def deserialize(cls, data: dict) -> "SkeletonData":
        """Deserialize skeleton data from dict."""
        bones = [Bone.deserialize(b) for b in data["bones"]]
        return cls(
            bones=bones,
            root_bone_indices=data.get("root_bone_indices"),
        )

    def __repr__(self) -> str:
        return f"<SkeletonData bones={len(self.bones)} roots={len(self.root_bone_indices)}>"


class SkeletonInstance:
    """
    Runtime skeleton state that references Entity transforms.

    Instead of storing its own bone transforms, reads world transforms
    directly from Entity hierarchy. Animation updates Entity transforms,
    and this class computes bone matrices for GPU.

    Usage:
        instance = SkeletonInstance(skeleton_data, bone_entities)
        # Animation updates Entity transforms...
        bone_matrices = instance.get_bone_matrices()  # Upload to GPU
    """

    MAX_BONES = 128  # Matches shader uniform array size

    def __init__(
        self,
        skeleton_data: SkeletonData,
        bone_entities: List = None,
    ):
        """
        Initialize skeleton instance.

        Args:
            skeleton_data: The skeleton template
            bone_entities: List of Entity objects for each bone (same order as bones in skeleton_data).
                          If None, skeleton works in legacy mode with internal transforms.
        """
        self._data = skeleton_data
        self._bone_entities = bone_entities  # List[Entity] or None
        n = skeleton_data.get_bone_count()

        # Computed matrices
        self._bone_matrices = np.zeros((n, 4, 4), dtype=np.float32)

        # Initialize to identity
        for i in range(n):
            self._bone_matrices[i] = np.eye(4, dtype=np.float32)

    @property
    def skeleton_data(self) -> SkeletonData:
        """Get the skeleton template."""
        return self._data

    def get_bone_entity(self, bone_index: int):
        """Get Entity for a bone by index."""
        if self._bone_entities and 0 <= bone_index < len(self._bone_entities):
            return self._bone_entities[bone_index]
        return None

    def get_bone_entity_by_name(self, bone_name: str):
        """Get Entity for a bone by name."""
        bone_index = self._data.get_bone_index(bone_name)
        return self.get_bone_entity(bone_index)

    def set_bone_transform_by_name(
        self,
        bone_name: str,
        translation: np.ndarray | None = None,
        rotation: np.ndarray | None = None,
        scale: np.ndarray | float | None = None,
    ) -> None:
        """
        Set local transform for a bone by name.

        Updates the Entity transform directly.

        Args:
            bone_name: Name of the bone
            translation: Position (3,) or None
            rotation: Quaternion (4,) as [x, y, z, w] or None
            scale: Scale (3,) or uniform float, or None
        """
        from termin.geombase.general_pose3 import GeneralPose3

        entity = self.get_bone_entity_by_name(bone_name)
        if entity is None:
            return

        # Update Entity transform
        pose = entity.transform.local_pose()
        new_lin = np.asarray(translation, dtype=np.float64) if translation is not None else pose.lin
        new_ang = np.asarray(rotation, dtype=np.float64) if rotation is not None else pose.ang

        if scale is not None:
            if isinstance(scale, (int, float)):
                new_scale = np.full(3, float(scale), dtype=np.float64)
            else:
                new_scale = np.asarray(scale, dtype=np.float64)
        else:
            new_scale = pose.scale

        new_pose = GeneralPose3(lin=new_lin, ang=new_ang, scale=new_scale)
        entity.transform.relocate(new_pose)

    def update(self) -> None:
        """
        Recompute bone matrices from Entity world transforms.

        Reads world matrix from each bone Entity and computes:
        bone_matrix = entity.model_matrix() @ inverse_bind_matrix
        """
        if self._bone_entities is None:
            return

        for bone in self._data.bones:
            entity = self._bone_entities[bone.index]
            world_matrix = entity.model_matrix()
            self._bone_matrices[bone.index] = world_matrix @ bone.inverse_bind_matrix

    _DEBUG_MATRICES = False
    _debug_matrix_frame = 0

    def get_bone_matrices(self) -> np.ndarray:
        """
        Get bone matrices array for GPU upload.

        Returns:
            Array of shape (N, 4, 4) containing final bone matrices.
            These are: EntityWorldTransform * InverseBindMatrix
        """
        self.update()
        return self._bone_matrices

    def get_bone_world_matrix(self, bone_index: int) -> np.ndarray:
        """Get world matrix for a specific bone."""
        if self._bone_entities and 0 <= bone_index < len(self._bone_entities):
            return self._bone_entities[bone_index].model_matrix()
        return np.eye(4, dtype=np.float32)

    def __repr__(self) -> str:
        has_entities = self._bone_entities is not None
        return f"<SkeletonInstance bones={len(self._data.bones)} has_entities={has_entities}>"
