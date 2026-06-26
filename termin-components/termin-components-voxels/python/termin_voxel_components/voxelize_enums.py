from enum import IntEnum


class VoxelizeMode(IntEnum):
    """Voxelization mode/stage."""

    SHELL = 0
    FILLED = 1
    MARKED = 2
    SURFACE_ONLY = 3
    WITH_NORMALS = 4
    FULL_GRID = 5


class VoxelizeSource(IntEnum):
    """Mesh source for voxelization."""

    CURRENT_MESH = 0
    ALL_DESCENDANTS = 1
