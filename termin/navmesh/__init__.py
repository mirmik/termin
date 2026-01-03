"""
NavMesh generation from voxel grids.

Алгоритм:
1. Берём поверхностные воксели с нормалями
2. Region Growing — группируем связные воксели с похожими нормалями
3. Для каждой группы строим контур (полигон)
4. Триангулируем полигоны
"""

from termin.navmesh.types import NavPolygon, NavMesh, NavMeshConfig
from termin.navmesh.polygon_builder import PolygonBuilder
from termin.navmesh.persistence import NavMeshPersistence
from termin.navmesh.display_component import NavMeshDisplayComponent
from termin.navmesh.pathfinding import RegionGraph, NavMeshGraph, Portal
from termin.navmesh.pathfinding_world_component import PathfindingWorldComponent
from termin.navmesh.agent_component import NavMeshAgentComponent

__all__ = [
    "NavPolygon",
    "NavMesh",
    "NavMeshConfig",
    "PolygonBuilder",
    "NavMeshPersistence",
    "NavMeshDisplayComponent",
    "RegionGraph",
    "NavMeshGraph",
    "Portal",
    "PathfindingWorldComponent",
    "NavMeshAgentComponent",
]
