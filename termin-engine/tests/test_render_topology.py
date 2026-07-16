from __future__ import annotations

from termin.engine import EngineCore, RenderTopology
from termin.render_framework import render_target_new


def test_engine_owned_render_topology_isolates_same_named_scene_targets() -> None:
    engine = EngineCore()
    scene_a = engine.scene_manager.create_scene("topology-a")
    scene_b = engine.scene_manager.create_scene("topology-b")
    target_a = render_target_new("SharedTarget")
    target_b = render_target_new("SharedTarget")
    target_a.scene = scene_a
    target_b.scene = scene_b

    try:
        assert isinstance(engine.render_topology, RenderTopology)
        engine.rendering_manager.register_managed_render_target(target_a)
        engine.rendering_manager.register_managed_render_target(target_b)

        found_a = engine.render_topology.find_render_target(scene_a, "SharedTarget")
        found_b = engine.render_topology.find_render_target(scene_b, "SharedTarget")
        assert found_a is not None
        assert found_b is not None
        assert (found_a.index, found_a.generation) == (target_a.index, target_a.generation)
        assert (found_b.index, found_b.generation) == (target_b.index, target_b.generation)
        assert len(engine.render_topology.render_targets(scene_a)) == 1
        assert len(engine.render_topology.render_targets(scene_b)) == 1
    finally:
        engine.rendering_manager.unregister_managed_render_target(target_a)
        engine.rendering_manager.unregister_managed_render_target(target_b)
        target_a.free()
        target_b.free()
        engine.scene_manager.close_scene("topology-a")
        engine.scene_manager.close_scene("topology-b")
