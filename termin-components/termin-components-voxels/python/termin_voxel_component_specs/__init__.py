"""Lightweight builtin component specs owned by termin-components-voxels."""

from __future__ import annotations

COMPONENT_SPECS: tuple[tuple[str, str], ...] = (
    ("termin_voxel_components.voxelizer_component", "VoxelizerComponent"),
    ("termin_voxel_components.display_component", "VoxelDisplayComponent"),
)

__all__ = ["COMPONENT_SPECS"]
