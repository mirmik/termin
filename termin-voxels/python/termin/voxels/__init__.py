"""
Voxel system for navmesh generation.

Provides chunked voxel grid with visualization and serialization support.
"""

from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)


def __getattr__(name: str):
    if name in ("VoxelChunk", "CHUNK_SIZE"):
        from termin.voxels.chunk import CHUNK_SIZE, VoxelChunk

        exports = {
            "VoxelChunk": VoxelChunk,
            "CHUNK_SIZE": CHUNK_SIZE,
        }
        globals().update(exports)
        return exports[name]

    if name == "VoxelGrid":
        from termin.voxels.grid import VoxelGrid

        globals()["VoxelGrid"] = VoxelGrid
        return VoxelGrid

    if name in (
        "MeshVoxelizer",
        "SceneVoxelizer",
        "voxelize_scene",
        "VOXEL_EMPTY",
        "VOXEL_SOLID",
        "VOXEL_SURFACE",
    ):
        from termin.voxels.voxelizer import (
            MeshVoxelizer,
            SceneVoxelizer,
            VOXEL_EMPTY,
            VOXEL_SOLID,
            VOXEL_SURFACE,
            voxelize_scene,
        )

        exports = {
            "MeshVoxelizer": MeshVoxelizer,
            "SceneVoxelizer": SceneVoxelizer,
            "voxelize_scene": voxelize_scene,
            "VOXEL_EMPTY": VOXEL_EMPTY,
            "VOXEL_SOLID": VOXEL_SOLID,
            "VOXEL_SURFACE": VOXEL_SURFACE,
        }
        globals().update(exports)
        return exports[name]

    if name in ("VoxelPersistence", "VOXEL_FILE_EXTENSION"):
        from termin.voxels.persistence import VOXEL_FILE_EXTENSION, VoxelPersistence

        exports = {
            "VoxelPersistence": VoxelPersistence,
            "VOXEL_FILE_EXTENSION": VOXEL_FILE_EXTENSION,
        }
        globals().update(exports)
        return exports[name]

    if name in (
        "TcVoxelGrid",
        "VoxelGridHandle",
        "declare_voxel_grid_asset",
        "set_voxel_grid_asset_data",
        "set_voxel_grid_asset_metadata",
        "tc_voxel_grid_get_all_info",
    ):
        try:
            from termin.voxels._voxels_native import (
                TcVoxelGrid,
                VoxelGridHandle,
                declare_voxel_grid_asset,
                set_voxel_grid_asset_data,
                set_voxel_grid_asset_metadata,
                tc_voxel_grid_get_all_info,
            )
        except ImportError as exc:
            from tcbase import log
            log.error("[termin.voxels] native voxel resources require termin.voxels._voxels_native")
            raise ImportError("termin.voxels native resources require termin.voxels._voxels_native") from exc
        exports = {
            "TcVoxelGrid": TcVoxelGrid,
            "VoxelGridHandle": VoxelGridHandle,
            "declare_voxel_grid_asset": declare_voxel_grid_asset,
            "set_voxel_grid_asset_data": set_voxel_grid_asset_data,
            "set_voxel_grid_asset_metadata": set_voxel_grid_asset_metadata,
            "tc_voxel_grid_get_all_info": tc_voxel_grid_get_all_info,
        }
        globals().update(exports)
        return exports[name]

    if name == "VoxelGridComponent":
        from termin_voxel_components.component import VoxelGridComponent
        return VoxelGridComponent

    if name == "VoxelVisualizer":
        from termin_voxel_components.visualization import VoxelVisualizer
        return VoxelVisualizer

    if name in ("VoxelizeMode", "VoxelizeSource"):
        from termin_voxel_components.voxelize_enums import (
            VoxelizeMode,
            VoxelizeSource,
        )
        return {
            "VoxelizeMode": VoxelizeMode,
            "VoxelizeSource": VoxelizeSource,
        }[name]

    if name == "VoxelizerComponent":
        from termin_voxel_components.voxelizer_component import (
            VoxelizerComponent,
        )
        return VoxelizerComponent

    if name == "VoxelDisplayComponent":
        from termin_voxel_components.display_component import VoxelDisplayComponent
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
    "TcVoxelGrid",
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
    "declare_voxel_grid_asset",
    "set_voxel_grid_asset_data",
    "set_voxel_grid_asset_metadata",
    "tc_voxel_grid_get_all_info",
]
