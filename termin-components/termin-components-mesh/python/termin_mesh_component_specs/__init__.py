"""Lightweight builtin component specs owned by termin-components-mesh."""

from __future__ import annotations

COMPONENT_SPECS: tuple[tuple[str, str], ...] = (
    ("termin.mesh.mesh_component", "MeshComponent"),
    ("termin.mesh.script_mesh_component", "ScriptMeshComponent"),
    ("termin.mesh.procedural_mesh_component", "ProceduralMeshComponent"),
)

__all__ = ["COMPONENT_SPECS"]
