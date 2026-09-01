"""Mesh component API."""

from termin.mesh.components.mesh_component import MeshComponent
from termin.mesh.components.procedural_mesh_component import ProceduralMeshComponent
from termin.mesh.components.script_mesh_component import ScriptMeshComponent
from termin.mesh.components.surface_edge_query import (
    SurfaceEdgeHit,
    find_aligned_surface_edge_for_entity,
    find_surface_edge_for_entity,
)

__all__ = [
    "MeshComponent",
    "ProceduralMeshComponent",
    "ScriptMeshComponent",
    "SurfaceEdgeHit",
    "find_surface_edge_for_entity",
    "find_aligned_surface_edge_for_entity",
]
