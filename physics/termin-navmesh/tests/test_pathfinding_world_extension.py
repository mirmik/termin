from __future__ import annotations

import pytest

import termin.bootstrap
from termin.navmesh import DetourPathfindingWorldComponent, PathfindingWorld
from termin.scene import TcScene


@pytest.fixture(scope="module", autouse=True)
def _bootstrap_runtime_extensions():
    termin.bootstrap.bootstrap_player()
    try:
        yield
    finally:
        termin.bootstrap.shutdown_player()


def test_pathfinding_world_tracks_multiple_components_on_one_entity() -> None:
    scene = TcScene.create("pathfinding-world-multiple-components")
    try:
        entity = scene.create_entity("navmesh-owner")
        world = PathfindingWorld.ensure_scene(scene)
        assert world is not None
        assert world.size == 0
        assert world.candidates_for_world_point((0.0, 0.0, 0.0)) == []

        entity.add_component(DetourPathfindingWorldComponent())
        entity.add_component(DetourPathfindingWorldComponent())

        assert world.size == 2
        world.rebuild_from_scene()
        assert world.size == 2
    finally:
        scene.destroy()
