"""Lightweight builtin component specs owned by termin-navmesh."""

from __future__ import annotations

COMPONENT_SPECS: tuple[tuple[str, str], ...] = (
    ("termin.navmesh.display_component", "NavMeshDisplayComponent"),
    ("termin.navmesh.material_component", "NavMeshMaterialComponent"),
    ("termin.navmesh.pathfinding_world_component", "PathfindingWorldComponent"),
    ("termin.navmesh.agent_component", "NavMeshAgentComponent"),
    ("termin.navmesh.builder_component", "NavMeshBuilderComponent"),
    ("termin.navmesh", "DetourPathfindingWorldComponent"),
    ("termin.navmesh", "NavMeshKeeperComponent"),
    ("termin.navmesh", "RecastNavMeshBuilderComponent"),
)

__all__ = ["COMPONENT_SPECS"]
