"""
Voxel system for navmesh generation.

Provides chunked voxel grid with visualization and serialization support.
"""

from termin.voxels.chunk import VoxelChunk, CHUNK_SIZE
from termin.voxels.grid import VoxelGrid
from termin.voxels.voxelizer import (
    MeshVoxelizer,
    SceneVoxelizer,
    voxelize_scene,
    VOXEL_EMPTY,
    VOXEL_SOLID,
    VOXEL_SURFACE,
)
from termin.voxels.persistence import VoxelPersistence, VOXEL_FILE_EXTENSION


def __getattr__(name: str):
    if name == "VoxelGridHandle":
        try:
            from termin.voxels._voxels_native import VoxelGridHandle
        except ImportError as exc:
            from tcbase import log
            log.error("[termin.voxels] VoxelGridHandle requires termin.voxels._voxels_native")
            raise ImportError("VoxelGridHandle requires termin.voxels._voxels_native") from exc
        return VoxelGridHandle

    if name == "VoxelGridComponent":
        from termin.voxels.component import VoxelGridComponent
        return VoxelGridComponent

    if name == "VoxelVisualizer":
        from termin.voxels.visualization import VoxelVisualizer
        return VoxelVisualizer

    if name in ("VoxelizerComponent", "VoxelizeMode", "VoxelizeSource"):
        from termin.voxels.voxelizer_component import (
            VoxelizerComponent,
            VoxelizeMode,
            VoxelizeSource,
        )
        return {
            "VoxelizerComponent": VoxelizerComponent,
            "VoxelizeMode": VoxelizeMode,
            "VoxelizeSource": VoxelizeSource,
        }[name]

    if name == "VoxelDisplayComponent":
        from termin.voxels.display_component import VoxelDisplayComponent
        return VoxelDisplayComponent

    if name == "voxel_display_shader":
        from termin.voxels.voxel_shader import voxel_display_shader
        return voxel_display_shader

    if name == "create_voxel_mesh":
        from termin.voxels.voxel_mesh import create_voxel_mesh
        return create_voxel_mesh

    raise AttributeError(f"module 'termin.voxels' has no attribute {name!r}")

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
    "VoxelizeSource",
    "VoxelDisplayComponent",
    "create_voxel_mesh",
    "CHUNK_SIZE",
    "VOXEL_EMPTY",
    "VOXEL_SOLID",
    "VOXEL_SURFACE",
    "VOXEL_FILE_EXTENSION",
    "voxel_display_shader",
]
