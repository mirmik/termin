"""Core mesh API: native mesh handles and primitive constructors."""

from termin_nanobind.runtime import preload_sdk_libs

preload_sdk_libs("nanobind", "termin_mesh")

from termin.mesh._mesh_native import *  # noqa: F403
from termin.mesh._mesh_native import log as log
from termin.mesh.primitives import (
    CubeMesh,
    TexturedCubeMesh,
    UVSphereMesh,
    IcoSphereMesh,
    PlaneMesh,
    CylinderMesh,
    ConeMesh,
    TorusMesh,
    RingMesh,
)

__all__ = [
    "CubeMesh", "TexturedCubeMesh", "UVSphereMesh", "IcoSphereMesh",
    "PlaneMesh", "CylinderMesh", "ConeMesh", "TorusMesh", "RingMesh",
]
