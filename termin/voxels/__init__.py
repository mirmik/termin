"""
Voxel system for navmesh generation.

Provides chunked voxel grid with visualization and serialization support.
"""

from termin.voxels.chunk import VoxelChunk, CHUNK_SIZE
from termin.voxels.grid import VoxelGrid
from termin.voxels.component import VoxelGridComponent
from termin.voxels.visualization import VoxelVisualizer
from termin.voxels.voxelizer import (
    MeshVoxelizer,
    SceneVoxelizer,
    voxelize_scene,
    VOXEL_EMPTY,
    VOXEL_SURFACE,
)
from termin.voxels.persistence import (
    VoxelPersistence,
    VOXEL_FILE_EXTENSION,
)
from termin.voxels.voxelizer_component import VoxelizerComponent
from termin.voxels.display_component import VoxelDisplayComponent

__all__ = [
    "VoxelChunk",
    "VoxelGrid",
    "VoxelGridComponent",
    "VoxelVisualizer",
    "MeshVoxelizer",
    "SceneVoxelizer",
    "voxelize_scene",
    "VoxelPersistence",
    "VoxelizerComponent",
    "VoxelDisplayComponent",
    "CHUNK_SIZE",
    "VOXEL_EMPTY",
    "VOXEL_SURFACE",
    "VOXEL_FILE_EXTENSION",
]
