from __future__ import annotations

from termin.bootstrap import bootstrap_player, shutdown_player


def test_world_link_fields_and_entity_references_serialize():
    bootstrap_player()
    from termin.geombase import Vec3
    from termin.navmesh import WorldNavMeshLinkComponent
    from termin.scene import TcScene
    scene = TcScene.create('world-link-inspect')
    try:
        a = scene.create_entity('a')
        b = scene.create_entity('b')
        link = WorldNavMeshLinkComponent()
        link.start_surface = a
        link.end_surface = b
        link.start_local = Vec3(1, 2, 3)
        link.end_local = Vec3(4, 5, 6)
        link.snap_radius = .2
        link.bidirectional = False
        data = link.serialize_data()
        assert data['start_surface'] == {'uuid': a.uuid}
        assert data['end_surface'] == {'uuid': b.uuid}
        assert data['start_local'] == [1, 2, 3]
        assert data['end_local'] == [4, 5, 6]
        assert data['snap_radius'] == .2
        assert data['bidirectional'] is False
    finally:
        scene.destroy()
        shutdown_player()
