"""Scene/render components for voxel-grid workflows.

The package facade is intentionally lazy: component modules import render,
material and scene bindings, so importing the package itself must not create
native resources.
"""


def __getattr__(name: str):
    if name == "VoxelGridComponent":
        from termin_voxel_components.component import VoxelGridComponent
        return VoxelGridComponent

    if name == "VoxelDisplayComponent":
        from termin_voxel_components.display_component import VoxelDisplayComponent
        return VoxelDisplayComponent

    if name == "VoxelVisualizer":
        from termin_voxel_components.visualization import VoxelVisualizer
        return VoxelVisualizer

    if name in ("VoxelizeMode", "VoxelizeSource", "VoxelizerComponent"):
        from termin_voxel_components.voxelizer_component import (
            VoxelizeMode,
            VoxelizeSource,
            VoxelizerComponent,
        )
        return {
            "VoxelizeMode": VoxelizeMode,
            "VoxelizeSource": VoxelizeSource,
            "VoxelizerComponent": VoxelizerComponent,
        }[name]

    raise AttributeError(f"module 'termin_voxel_components' has no attribute {name!r}")

__all__ = [
    "VoxelGridComponent",
    "VoxelDisplayComponent",
    "VoxelVisualizer",
    "VoxelizeMode",
    "VoxelizeSource",
    "VoxelizerComponent",
]
