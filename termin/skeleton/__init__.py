"""Skeleton module for skeletal animation support."""

# Setup DLL paths before importing native extensions
from termin import _dll_setup  # noqa: F401

import os as _os
_sdk_dir = _os.path.join(_os.sep, "opt", "termin", "lib", "python", "termin", "skeleton")
if _os.path.isdir(_sdk_dir) and _sdk_dir not in __path__:
    __path__.append(_sdk_dir)

from termin.skeleton._skeleton_native import (
    TcSkeleton,
    SkeletonInstance,
    SkeletonController,
)
from termin.skeleton.skeleton_asset import SkeletonAsset

__all__ = [
    "TcSkeleton",
    "SkeletonInstance",
    "SkeletonController",
    "SkeletonAsset",
]
