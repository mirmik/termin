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
    Runtime skeleton state for a specific entity.

    Holds current bone transforms (from animation) and computes
    final bone matrices for GPU upload.

    Usage:
        instance = skeleton_data.create_instance()
        instance.set_bone_transform_by_name("LeftArm", translation, rotation, scale)
        instance.update()
        bone_matrices = instance.get_bone_matrices()  # Upload to GPU
    """

    MAX_BONES = 128  # Matches shader uniform array size

    def __init__(
        self,
        skeleton_data: SkeletonData,
        root_transform: np.ndarray | None = None,
    ):
        """
        Initialize skeleton instance.

        Args:
            skeleton_data: The skeleton template
            root_transform: Optional 4x4 transform of skeleton root (e.g., Armature node)
                           This is applied to all root bones before computing world matrices.
        """
        self._data = skeleton_data
        n = skeleton_data.get_bone_count()

        # Root transform (from parent node like Armature)
        if root_transform is not None:
            self._root_transform = np.asarray(root_transform, dtype=np.float32).reshape(4, 4)
        else:
            self._root_transform = np.eye(4, dtype=np.float32)

        # Current local transforms per bone (set by animation)
        self._local_translations = np.zeros((n, 3), dtype=np.float32)
        self._local_rotations = np.zeros((n, 4), dtype=np.float32)
        self._local_rotations[:, 3] = 1.0  # Identity quaternion (0, 0, 0, 1)
        self._local_scales = np.ones((n, 3), dtype=np.float32)

        # Computed matrices
        self._local_matrices = np.zeros((n, 4, 4), dtype=np.float32)
        self._world_matrices = np.zeros((n, 4, 4), dtype=np.float32)
        self._bone_matrices = np.zeros((n, 4, 4), dtype=np.float32)

        # Initialize to identity
        for i in range(n):
            self._local_matrices[i] = np.eye(4, dtype=np.float32)
            self._world_matrices[i] = np.eye(4, dtype=np.float32)
            self._bone_matrices[i] = np.eye(4, dtype=np.float32)

        self._dirty = True

        # Initialize to bind pose from skeleton data
        self.reset_to_bind_pose()

    @property
    def skeleton_data(self) -> SkeletonData:
        """Get the skeleton template."""
        return self._data

    def set_bone_transform(
        self,
        bone_index: int,
        translation: np.ndarray | None = None,
        rotation: np.ndarray | None = None,
        scale: np.ndarray | float | None = None,
    ) -> None:
        """
        Set local transform for a bone.

        Args:
            bone_index: Index of the bone
            translation: Position (3,) or None to keep current
            rotation: Quaternion (4,) as [x, y, z, w] or None
            scale: Scale (3,) or uniform float, or None
        """
        if bone_index < 0 or bone_index >= len(self._data.bones):
            return

        if translation is not None:
            self._local_translations[bone_index] = np.asarray(translation, dtype=np.float32)

        if rotation is not None:
            self._local_rotations[bone_index] = np.asarray(rotation, dtype=np.float32)

        if scale is not None:
            if isinstance(scale, (int, float)):
                self._local_scales[bone_index] = np.array([scale, scale, scale], dtype=np.float32)
            else:
                self._local_scales[bone_index] = np.asarray(scale, dtype=np.float32)

        self._dirty = True

    def set_bone_transform_by_name(
        self,
        bone_name: str,
        translation: np.ndarray | None = None,
        rotation: np.ndarray | None = None,
        scale: np.ndarray | float | None = None,
    ) -> None:
        """
        Set local transform for a bone by name.

        Args:
            bone_name: Name of the bone
            translation: Position (3,) or None
            rotation: Quaternion (4,) as [x, y, z, w] or None
            scale: Scale (3,) or uniform float, or None
        """
        bone_index = self._data.get_bone_index(bone_name)
        if bone_index >= 0:
            self.set_bone_transform(bone_index, translation, rotation, scale)

    def reset_to_bind_pose(self) -> None:
        """Reset all bones to bind pose from skeleton data."""
        for bone in self._data.bones:
            i = bone.index
            self._local_translations[i] = bone.bind_translation.copy()
            self._local_rotations[i] = bone.bind_rotation.copy()
            self._local_scales[i] = bone.bind_scale.copy()
        self._dirty = True

    def update(self) -> None:
        """
        Recompute world matrices and final bone matrices.

        Call this after setting bone transforms, before get_bone_matrices().

        Algorithm:
        1. Compute local matrix from T * R * S for each bone
        2. Compute world matrix: root_transform * parent_world * local (root_transform for roots)
        3. Compute bone matrix: world * inverse_bind_matrix
        """
        if not self._dirty:
            return

        # Step 1: Compute local matrices
        for i in range(len(self._data.bones)):
            self._local_matrices[i] = self._compute_trs_matrix(
                self._local_translations[i],
                self._local_rotations[i],
                self._local_scales[i],
            )

        # Step 2: Compute world matrices (parent * local)
        # Bones are assumed ordered so parents come before children
        for bone in self._data.bones:
            if bone.parent_index < 0:
                # Root bone: world = root_transform * local
                self._world_matrices[bone.index] = self._root_transform @ self._local_matrices[bone.index]
            else:
                # Child bone: world = parent_world * local
                parent_world = self._world_matrices[bone.parent_index]
                self._world_matrices[bone.index] = parent_world @ self._local_matrices[bone.index]

        # Step 3: Compute final bone matrices (world * inverse_bind)
        for bone in self._data.bones:
            self._bone_matrices[bone.index] = (
                self._world_matrices[bone.index] @ bone.inverse_bind_matrix
            )

        self._dirty = False

    def get_bone_matrices(self) -> np.ndarray:
        """
        Get bone matrices array for GPU upload.

        Returns:
            Array of shape (N, 4, 4) containing final bone matrices.
            These are: CurrentWorldTransform * InverseBindMatrix

        Note: Call update() first if transforms have changed.
        """
        self.update()
        return self._bone_matrices

    def get_bone_world_matrix(self, bone_index: int) -> np.ndarray:
        """Get world matrix for a specific bone."""
        self.update()
        return self._world_matrices[bone_index]

    def _compute_trs_matrix(
        self,
        translation: np.ndarray,
        rotation: np.ndarray,
        scale: np.ndarray,
    ) -> np.ndarray:
        """
        Compute 4x4 transform matrix from Translation, Rotation, Scale.

        Args:
            translation: (3,) position
            rotation: (4,) quaternion [x, y, z, w]
            scale: (3,) scale factors

        Returns:
            4x4 transformation matrix = T * R * S
        """
        # Build rotation matrix from quaternion
        x, y, z, w = rotation
        r = np.array([
            [1 - 2*(y*y + z*z),     2*(x*y - z*w),     2*(x*z + y*w), 0],
            [    2*(x*y + z*w), 1 - 2*(x*x + z*z),     2*(y*z - x*w), 0],
            [    2*(x*z - y*w),     2*(y*z + x*w), 1 - 2*(x*x + y*y), 0],
            [                0,                 0,                 0, 1],
        ], dtype=np.float32)

        # Apply scale
        r[0, :3] *= scale[0]
        r[1, :3] *= scale[1]
        r[2, :3] *= scale[2]

        # Apply translation
        r[0, 3] = translation[0]
        r[1, 3] = translation[1]
        r[2, 3] = translation[2]

        return r

    def __repr__(self) -> str:
        return f"<SkeletonInstance bones={len(self._data.bones)} dirty={self._dirty}>"
