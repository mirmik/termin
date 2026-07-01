from __future__ import annotations

from termin.navmesh import DetourPathfindingWorldComponent, PathfindingWorld
from termin.scene import TcScene


def test_pathfinding_world_tracks_multiple_components_on_one_entity() -> None:
    scene = TcScene.create("pathfinding-world-multiple-components")
    try:
        entity = scene.create_entity("navmesh-owner")
        world = PathfindingWorld.ensure_scene(scene)
        assert world is not None
        assert world.size == 0

        entity.add_component(DetourPathfindingWorldComponent())
        entity.add_component(DetourPathfindingWorldComponent())

        assert world.size == 2
        world.rebuild_from_scene()
        assert world.size == 2
    finally:
        scene.destroy()
