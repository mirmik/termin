"""Skeleton module for skeletal animation support."""

from termin.skeleton._skeleton_native import Bone, SkeletonData, SkeletonHandle
from termin._native.skeleton import SkeletonInstance
from termin.skeleton.skeleton_asset import SkeletonAsset

__all__ = [
    "Bone",
    "SkeletonData",
    "SkeletonHandle",
    "SkeletonInstance",
    "SkeletonAsset",
]
