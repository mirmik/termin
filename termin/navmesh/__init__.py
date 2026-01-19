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
from termin.navmesh.material_component import NavMeshMaterialComponent
from termin.navmesh.pathfinding import RegionGraph, NavMeshGraph, Portal
from termin.navmesh.pathfinding_world_component import PathfindingWorldComponent
from termin.navmesh.agent_component import NavMeshAgentComponent
from termin.navmesh.settings import AgentType, NavigationSettings, NavigationSettingsManager
from termin.navmesh.builder_component import NavMeshBuilderComponent
from termin.navmesh.registry import NavMeshRegistry

# Optional C++ components (require _navmesh_native to be built)
try:
    from termin.navmesh._navmesh_native import RecastNavMeshBuilderComponent, RecastBuildResult
except ImportError:
    RecastNavMeshBuilderComponent = None
    RecastBuildResult = None

__all__ = [
    "NavPolygon",
    "NavMesh",
    "NavMeshConfig",
    "PolygonBuilder",
    "NavMeshPersistence",
    "NavMeshDisplayComponent",
    "NavMeshMaterialComponent",
    "RegionGraph",
    "NavMeshGraph",
    "Portal",
    "PathfindingWorldComponent",
    "NavMeshAgentComponent",
    "AgentType",
    "NavigationSettings",
    "NavigationSettingsManager",
    "NavMeshBuilderComponent",
    "NavMeshRegistry",
]

# Add C++ components to __all__ only if available
if RecastNavMeshBuilderComponent is not None:
    __all__.extend(["RecastNavMeshBuilderComponent", "RecastBuildResult"])
