"""Public VoxelGrid runtime type.

The canonical voxel grid implementation is the native C++ class exposed from
``termin.voxels._voxels_native``. This module remains as the stable import path
for existing code.
"""

from __future__ import annotations

try:
    from termin.voxels._voxels_native import VoxelGrid
except ImportError as exc:
    from tcbase import log

    log.error("[termin.voxels.grid] VoxelGrid requires termin.voxels._voxels_native")
    raise ImportError("termin.voxels.grid.VoxelGrid requires termin.voxels._voxels_native") from exc

__all__ = ["VoxelGrid"]
