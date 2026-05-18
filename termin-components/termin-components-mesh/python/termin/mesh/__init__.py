"""Mesh module — Mesh3, TcMesh (via tgfx) + MeshComponent (nanobind)."""

from termin_nanobind.runtime import preload_sdk_libs

preload_sdk_libs("nanobind", "termin_components_mesh")

from tmesh import Mesh3, TcMesh
from termin.mesh.mesh_component import MeshComponent
from termin.mesh.procedural_mesh_component import ProceduralMeshComponent
from termin.mesh.procedural_mesh_document import (
    ContourDocument,
    OperationDocument,
    ProceduralMeshDocument,
    ProceduralPlane,
    SketchItemDocument,
)
from termin.mesh.script_mesh_component import ScriptMeshComponent
from termin.mesh.surface_edge_query import (
    SurfaceEdgeHit,
    find_aligned_surface_edge_for_entity,
    find_surface_edge_for_entity,
)

__all__ = [
    "Mesh3",
    "TcMesh",
    "MeshComponent",
    "ProceduralMeshComponent",
    "ContourDocument",
    "OperationDocument",
    "ProceduralMeshDocument",
    "ProceduralPlane",
    "SketchItemDocument",
    "ScriptMeshComponent",
    "SurfaceEdgeHit",
    "find_surface_edge_for_entity",
    "find_aligned_surface_edge_for_entity",
]
