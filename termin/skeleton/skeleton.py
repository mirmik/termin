"""Skeleton runtime instance class."""

from __future__ import annotations

from typing import List, TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from termin.skeleton._skeleton_native import SkeletonData


class SkeletonInstance:
    """
    Runtime skeleton state that references Entity transforms.

    Instead of storing its own bone transforms, reads world transforms
    directly from Entity hierarchy. Animation updates Entity transforms,
    and this class computes bone matrices for GPU.

    Bone matrices are computed in skeleton-local space (not world space),
    so that u_model can be applied uniformly as with non-skinned meshes.

    Usage:
        instance = SkeletonInstance(skeleton_data, bone_entities, skeleton_root)
        # Animation updates Entity transforms...
        bone_matrices = instance.get_bone_matrices()  # Upload to GPU
    """

    MAX_BONES = 128  # Matches shader uniform array size

    def __init__(
        self,
        skeleton_data: "SkeletonData",
        bone_entities: List = None,
        skeleton_root_entity=None,
    ):
        """
        Initialize skeleton instance.

        Args:
            skeleton_data: The skeleton template
            bone_entities: List of Entity objects for each bone (same order as bones in skeleton_data).
                          If None, skeleton works in legacy mode with internal transforms.
            skeleton_root_entity: Root entity of the skeleton hierarchy. Used to compute
                                 bone matrices in local space. If None, will try to find
                                 parent of root bones.
        """
        self._data = skeleton_data
        self._bone_entities = bone_entities  # List[Entity] or None
        self._skeleton_root_entity = skeleton_root_entity
        n = skeleton_data.get_bone_count()

        # Computed matrices
        self._bone_matrices = np.zeros((n, 4, 4), dtype=np.float32)

        # Initialize to identity
        for i in range(n):
            self._bone_matrices[i] = np.eye(4, dtype=np.float32)

    @property
    def skeleton_data(self) -> "SkeletonData":
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
        from termin.geombase import GeneralPose3

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

    def _get_skeleton_root(self):
        """Get skeleton root entity, finding it if not explicitly set."""
        if self._skeleton_root_entity is not None:
            return self._skeleton_root_entity

        # Try to find root as parent of root bone entities
        if self._bone_entities and self._data.root_bone_indices:
            root_bone_idx = self._data.root_bone_indices[0]
            root_bone_entity = self._bone_entities[root_bone_idx]
            if root_bone_entity.transform.parent is not None:
                self._skeleton_root_entity = root_bone_entity.transform.parent.entity
                return self._skeleton_root_entity

        return None

    def update(self) -> None:
        """
        Recompute bone matrices from Entity world transforms.

        Computes bone matrices in skeleton-local space:
        bone_matrix = inv(skeleton_world) @ bone_world @ inverse_bind_matrix

        This allows u_model to be applied uniformly in shaders.
        """
        if self._bone_entities is None:
            return

        # Get inverse of skeleton root world matrix (cached in GeneralPose3)
        skeleton_root = self._get_skeleton_root()
        if skeleton_root is not None:
            skeleton_world_inv = skeleton_root.inverse_model_matrix()
        else:
            skeleton_world_inv = np.eye(4, dtype=np.float32)

        for bone in self._data.bones:
            entity = self._bone_entities[bone.index]
            bone_world = entity.model_matrix()
            # Transform to skeleton-local space, then apply inverse bind
            self._bone_matrices[bone.index] = skeleton_world_inv @ bone_world @ bone.inverse_bind_matrix


    def get_bone_matrices(self) -> np.ndarray:
        """
        Get bone matrices array for GPU upload.

        Returns:
            Array of shape (N, 4, 4) containing bone matrices in skeleton-local space.
            These are: inv(SkeletonWorld) @ BoneWorld @ InverseBindMatrix

            Shader should apply u_model to transform to world space.
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
