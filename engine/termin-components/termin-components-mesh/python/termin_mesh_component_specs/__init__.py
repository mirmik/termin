"""Lightweight builtin component specs owned by termin-components-mesh."""

from __future__ import annotations

COMPONENT_SPECS: tuple[tuple[str, str], ...] = (
    ("termin.mesh.components.mesh_component", "MeshComponent"),
    ("termin.mesh.components.script_mesh_component", "ScriptMeshComponent"),
    ("termin.mesh.components.procedural_mesh_component", "ProceduralMeshComponent"),
)

__all__ = ["COMPONENT_SPECS"]
