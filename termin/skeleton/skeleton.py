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

    @classmethod
    def from_glb_skin(cls, skin, nodes: List) -> "SkeletonData":
        """
        Create SkeletonData from GLB skin data.

        Args:
            skin: GLBSkinData with joint indices and inverse bind matrices
            nodes: List of GLBNodeData for all nodes in the scene
        """
        bones = []

        for bone_idx, node_idx in enumerate(skin.joint_node_indices):
            node = nodes[node_idx]

            # Find parent bone by checking which bone contains this node as child
            parent_bone_idx = -1
            for other_bone_idx, other_node_idx in enumerate(skin.joint_node_indices):
                if node_idx in nodes[other_node_idx].children:
                    parent_bone_idx = other_bone_idx
                    break

            bone = Bone(
                name=node.name,
                index=bone_idx,
                parent_index=parent_bone_idx,
                inverse_bind_matrix=skin.inverse_bind_matrices[bone_idx],
                bind_translation=node.translation.copy(),
                bind_rotation=node.rotation.copy(),
                bind_scale=node.scale.copy(),
            )
            bones.append(bone)

        return cls(bones=bones)

    def __repr__(self) -> str:
        return f"<SkeletonData bones={len(self.bones)} roots={len(self.root_bone_indices)}>"


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
        skeleton_data: SkeletonData,
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

    _DEBUG_NORMALIZE = True

    def update(self) -> None:
        """
        Recompute bone matrices from Entity world transforms.

        Computes bone matrices in skeleton-local space:
        bone_matrix = inv(skeleton_world) @ bone_world @ inverse_bind_matrix

        This allows u_model to be applied uniformly in shaders.
        """
        if self._bone_entities is None:
            return

        # Get inverse of skeleton root world matrix
        skeleton_root = self._get_skeleton_root()
        if skeleton_root is not None:
            skeleton_world = skeleton_root.model_matrix()
            skeleton_world_inv = np.linalg.inv(skeleton_world)
            if self._DEBUG_NORMALIZE:
                print(f"[SkeletonInstance] skeleton_root={skeleton_root.name}")
                print(f"[SkeletonInstance] skeleton_world diagonal: {np.diag(skeleton_world)}")
                self._DEBUG_NORMALIZE = False
        else:
            skeleton_world_inv = np.eye(4, dtype=np.float32)

        for bone in self._data.bones:
            entity = self._bone_entities[bone.index]
            bone_world = entity.model_matrix()
            # Transform to skeleton-local space, then apply inverse bind
            self._bone_matrices[bone.index] = skeleton_world_inv @ bone_world @ bone.inverse_bind_matrix

    _DEBUG_MATRICES = False
    _debug_matrix_frame = 0

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
