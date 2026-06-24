"""Lightweight builtin component specs owned by termin-components-voxels."""

from __future__ import annotations

COMPONENT_SPECS: tuple[tuple[str, str], ...] = (
    ("termin.voxels.voxelizer_component", "VoxelizerComponent"),
    ("termin.voxels.display_component", "VoxelDisplayComponent"),
)

__all__ = ["COMPONENT_SPECS"]
