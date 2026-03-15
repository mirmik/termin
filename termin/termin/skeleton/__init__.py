"""Skeleton module for skeletal animation support."""

# Setup DLL paths before importing native extensions
from termin import _dll_setup  # noqa: F401

_dll_setup.extend_package_path(__path__, "skeleton")

from termin.skeleton._skeleton_native import (
    TcSkeleton,
    SkeletonInstance,
)
from termin.skeleton.skeleton_asset import SkeletonAsset

__all__ = [
    "TcSkeleton",
    "SkeletonInstance",
    "SkeletonAsset",
]
