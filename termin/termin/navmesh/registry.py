"""
NavMesh registry for centralized NavMesh management per scene.

Components register their NavMesh data here. Other components
(agents, pathfinding) query NavMesh by agent type.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional
from weakref import WeakValueDictionary

if TYPE_CHECKING:
    from termin.navmesh.types import NavMesh
    from termin.visualization.core.scene import Scene
    from termin.visualization.core.entity import Entity

# Entry: (NavMesh, Entity)
NavMeshEntry = tuple["NavMesh", "Entity"]


class NavMeshRegistry:
    """
    Centralized NavMesh storage for a scene.

    Does not know about builders - only stores NavMesh data.
    Builders register their NavMesh, agents query it.

    Structure:
        agent_type -> {source_uuid -> (NavMesh, Entity)}

    Entity is stored for coordinate transformations (NavMesh is in local coords).
    """

    _instances: Dict[str, "NavMeshRegistry"] = {}

    # agent_type -> {source_uuid -> (NavMesh, Entity)}
    _meshes: Dict[str, Dict[str, NavMeshEntry]]

    # Cached merged meshes per agent type (invalidated on register/unregister)
    _merged_cache: Dict[str, "NavMesh"]

    def __init__(self) -> None:
        self._meshes = {}
        self._merged_cache = {}

    @classmethod
    def for_scene(cls, scene: "Scene") -> "NavMeshRegistry":
        """Get registry instance for a scene."""
        scene_uuid = scene.uuid
        if scene_uuid not in cls._instances:
            cls._instances[scene_uuid] = NavMeshRegistry()
        return cls._instances[scene_uuid]

    @classmethod
    def clear_instance(cls, scene_uuid: str) -> None:
        """Remove cached instance for scene."""
        cls._instances.pop(scene_uuid, None)

    def register(self, agent_type: str, navmesh: "NavMesh", entity: "Entity") -> None:
        """
        Register NavMesh from a source.

        Args:
            agent_type: Agent type name (e.g. "Human", "Vehicle").
            navmesh: NavMesh data (in entity local coordinates).
            entity: Source entity (for coordinate transformations).
        """
        if agent_type not in self._meshes:
            self._meshes[agent_type] = {}
        self._meshes[agent_type][entity.uuid] = (navmesh, entity)
        self._merged_cache.pop(agent_type, None)

    def unregister(self, agent_type: str, source_uuid: str) -> None:
        """
        Remove NavMesh from a source.

        Args:
            agent_type: Agent type name.
            source_uuid: UUID of the source entity.
        """
        if agent_type in self._meshes:
            self._meshes[agent_type].pop(source_uuid, None)
            if not self._meshes[agent_type]:
                del self._meshes[agent_type]
            self._merged_cache.pop(agent_type, None)

    def unregister_all(self, source_uuid: str) -> None:
        """
        Remove all NavMesh from a source (when entity is removed).

        Args:
            source_uuid: UUID of the source entity.
        """
        for agent_type in list(self._meshes.keys()):
            if source_uuid in self._meshes[agent_type]:
                del self._meshes[agent_type][source_uuid]
                self._merged_cache.pop(agent_type, None)
                if not self._meshes[agent_type]:
                    del self._meshes[agent_type]

    def get(self, agent_type: str) -> Optional["NavMesh"]:
        """
        Get merged NavMesh for an agent type.

        If multiple sources registered NavMesh for this agent type,
        returns a merged NavMesh containing all polygons.

        Args:
            agent_type: Agent type name.

        Returns:
            Merged NavMesh or None if no NavMesh registered.
        """
        if agent_type not in self._meshes:
            return None

        sources = self._meshes[agent_type]
        if not sources:
            return None

        # Single source - return directly
        if len(sources) == 1:
            return next(iter(sources.values()))

        # Multiple sources - return merged (with caching)
        if agent_type in self._merged_cache:
            return self._merged_cache[agent_type]

        merged = self._merge_navmeshes(list(sources.values()))
        self._merged_cache[agent_type] = merged
        return merged

    def get_all(self, agent_type: str) -> List[NavMeshEntry]:
        """
        Get all NavMesh for an agent type without merging.

        Args:
            agent_type: Agent type name.

        Returns:
            List of (NavMesh, Entity) tuples.
        """
        if agent_type not in self._meshes:
            return []
        return list(self._meshes[agent_type].values())

    def get_for_source(self, agent_type: str, source_uuid: str) -> Optional[NavMeshEntry]:
        """
        Get NavMesh from a specific source.

        Args:
            agent_type: Agent type name.
            source_uuid: UUID of the source entity.

        Returns:
            (NavMesh, Entity) or None.
        """
        if agent_type not in self._meshes:
            return None
        return self._meshes[agent_type].get(source_uuid)

    def list_agent_types(self) -> List[str]:
        """List all agent types with registered NavMesh."""
        return list(self._meshes.keys())

    def list_sources(self, agent_type: str) -> List[str]:
        """List all source UUIDs for an agent type."""
        if agent_type not in self._meshes:
            return []
        return list(self._meshes[agent_type].keys())

    def clear(self) -> None:
        """Clear all registered NavMesh."""
        self._meshes.clear()
        self._merged_cache.clear()

    def _merge_navmeshes(self, meshes: List["NavMesh"]) -> "NavMesh":
        """
        Merge multiple NavMesh into one.

        Simply concatenates all polygons. Neighbor indices need adjustment.
        """
        from termin.navmesh.types import NavMesh, NavPolygon
        import numpy as np

        if not meshes:
            return NavMesh(cell_size=0.25, origin=np.zeros(3, dtype=np.float32), name="merged")

        # Use first mesh as base
        base = meshes[0]
        merged = NavMesh(
            cell_size=base.cell_size,
            origin=base.origin.copy(),
            name="merged",
        )

        polygon_offset = 0
        for mesh in meshes:
            for polygon in mesh.polygons:
                # Adjust neighbor indices
                new_neighbors = [n + polygon_offset if n >= 0 else n for n in polygon.neighbors]
                new_polygon = NavPolygon(
                    vertices=polygon.vertices.copy(),
                    triangles=polygon.triangles.copy(),
                    normal=polygon.normal.copy(),
                    voxel_coords=list(polygon.voxel_coords),
                    neighbors=new_neighbors,
                    outer_contour=list(polygon.outer_contour) if polygon.outer_contour else None,
                    holes=[list(h) for h in polygon.holes] if polygon.holes else [],
                )
                merged.polygons.append(new_polygon)
            polygon_offset += len(mesh.polygons)

        return merged
