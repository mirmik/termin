"""Skeleton module for skeletal animation support."""

# Setup DLL paths before importing native extensions
from termin import _dll_setup  # noqa: F401

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
