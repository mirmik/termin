"""
Voxel system for navmesh generation.

Provides chunked voxel grid with visualization and serialization support.
"""

from termin.voxels._voxels_native import (
    VoxelChunk,
    VoxelGrid,
    VoxelGridHandle,
    CHUNK_SIZE,
)
from termin.voxels.component import VoxelGridComponent
from termin.voxels.visualization import VoxelVisualizer
from termin.voxels.voxelizer import (
    MeshVoxelizer,
    SceneVoxelizer,
    voxelize_scene,
    VOXEL_EMPTY,
    VOXEL_SOLID,
    VOXEL_SURFACE,
)
from termin.voxels.persistence import (
    VoxelPersistence,
    VOXEL_FILE_EXTENSION,
)
from termin.voxels.voxelizer_component import VoxelizerComponent, VoxelizeMode
from termin.voxels.display_component import VoxelDisplayComponent
from termin.voxels.voxel_shader import voxel_display_shader
from termin.voxels.voxel_mesh import VoxelMesh

__all__ = [
    "VoxelChunk",
    "VoxelGrid",
    "VoxelGridHandle",
    "VoxelGridComponent",
    "VoxelVisualizer",
    "MeshVoxelizer",
    "SceneVoxelizer",
    "voxelize_scene",
    "VoxelPersistence",
    "VoxelizerComponent",
    "VoxelizeMode",
    "VoxelDisplayComponent",
    "VoxelMesh",
    "CHUNK_SIZE",
    "VOXEL_EMPTY",
    "VOXEL_SOLID",
    "VOXEL_SURFACE",
    "VOXEL_FILE_EXTENSION",
    "voxel_display_shader",
]
