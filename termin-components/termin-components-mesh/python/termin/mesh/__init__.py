"""Mesh module — Mesh3, TcMesh (via tgfx) + MeshComponent (nanobind)."""

from pkgutil import extend_path

from termin_nanobind.runtime import preload_sdk_libs

__path__ = extend_path(__path__, __name__)

preload_sdk_libs("nanobind", "termin_components_mesh")

from tmesh import Mesh3, TcMesh
from termin.mesh.mesh_component import MeshComponent
from termin.mesh.procedural_mesh_component import ProceduralMeshComponent
from termin.mesh.script_mesh_component import ScriptMeshComponent
from termin.mesh.surface_edge_query import (
    SurfaceEdgeHit,
    find_aligned_surface_edge_for_entity,
    find_surface_edge_for_entity,
)


def __getattr__(name: str):
    if name == "MeshAsset":
        from termin.default_assets.mesh.asset import MeshAsset

        globals()["MeshAsset"] = MeshAsset
        return MeshAsset

    raise AttributeError(f"module 'termin.mesh' has no attribute {name!r}")


__all__ = [
    "Mesh3",
    "TcMesh",
    "MeshComponent",
    "ProceduralMeshComponent",
    "ScriptMeshComponent",
    "SurfaceEdgeHit",
    "find_surface_edge_for_entity",
    "find_aligned_surface_edge_for_entity",
]
