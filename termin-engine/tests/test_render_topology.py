from __future__ import annotations

from termin.engine import EngineCore, RenderingManager, RenderTopology, SceneManager
from termin.render_framework import render_target_new
from termin.render import scene_render_mount
from termin.scene import PythonComponent


def test_engine_services_are_explicit_and_multiple_engines_are_independent() -> None:
    assert "instance" not in EngineCore.__dict__
    assert "instance" not in SceneManager.__dict__
    assert "instance" not in RenderingManager.__dict__
    assert "instance_or_none" not in RenderingManager.__dict__

    first = EngineCore()
    second = EngineCore()
    try:
        assert first.scene_manager is not second.scene_manager
        assert first.rendering_manager is not second.rendering_manager
        assert first.render_topology is not second.render_topology
    finally:
        del second
        del first


def test_render_engine_shader_configuration_does_not_mutate_legacy_root(tmp_path) -> None:
    import tgfx

    engine = EngineCore()
    tgfx.set_shader_artifact_root("legacy-sentinel")
    try:
        engine.rendering_manager.render_engine.configure_shader_artifacts(
            artifact_root=str(tmp_path / "artifacts"),
            cache_root=str(tmp_path / "cache"),
            compiler_path="",
            dev_compile_enabled=False,
        )
        assert tgfx.get_shader_artifact_root() == "legacy-sentinel"
    finally:
        tgfx.set_shader_artifact_root("")


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


def test_python_render_lifecycle_context_is_scene_scoped_and_call_scoped() -> None:
    class RenderContextProbe(PythonComponent):
        def __init__(self) -> None:
            super().__init__()
            self.attach_context = None
            self.detach_context = None
            self.attach_target = None
            self.detach_target = None
            self.foreign_target = "not-checked"

        def on_render_attach(self, context) -> None:
            assert context.valid
            self.attach_context = context
            self.attach_target = context.find_render_target("ProbeTarget")
            self.foreign_target = context.find_render_target("ForeignTarget")
            assert len(context.render_targets) == 1

        def on_render_detach(self, context) -> None:
            assert context.valid
            self.detach_context = context
            self.detach_target = context.find_render_target("ProbeTarget")

    engine = EngineCore()
    scene = engine.scene_manager.create_scene("context-probe")
    foreign_scene = engine.scene_manager.create_scene("context-foreign")
    entity = scene.create_entity("Probe")
    probe = RenderContextProbe()
    entity.add_component(probe)

    target = render_target_new("ProbeTarget")
    target.scene = scene
    engine.rendering_manager.register_managed_render_target(target)
    foreign_target = render_target_new("ForeignTarget")
    foreign_target.scene = foreign_scene
    engine.rendering_manager.register_managed_render_target(foreign_target)

    engine.rendering_manager.attach_scene(scene)
    assert probe.attach_target is not None
    assert probe.foreign_target is None
    assert not probe.attach_context.valid

    engine.rendering_manager.detach_scene_full(scene)
    assert probe.detach_target is not None
    assert not probe.detach_context.valid

    try:
        _ = probe.detach_context.render_targets
    except RuntimeError as error:
        assert "no longer active" in str(error)
    else:
        raise AssertionError("retained RenderAttachmentContext remained usable")

    engine.rendering_manager.unregister_managed_render_target(foreign_target)
    foreign_target.free()
    engine.scene_manager.close_scene("context-probe")
    engine.scene_manager.close_scene("context-foreign")


def test_scene_manager_forces_detach_before_destroying_attached_scene() -> None:
    engine = EngineCore()
    scene = engine.scene_manager.create_scene("mandatory-detach")
    target = render_target_new("MandatoryDetachTarget")
    target.scene = scene
    engine.rendering_manager.register_managed_render_target(target)
    engine.rendering_manager.attach_scene(scene)

    engine.scene_manager.close_scene("mandatory-detach")

    assert not engine.render_topology.is_attached(scene)
    assert not engine.render_topology.managed_render_targets


def test_scene_render_mount_exposes_only_declarative_recipe() -> None:
    engine = EngineCore()
    scene = engine.scene_manager.create_scene("declarative-mount")
    mount = scene_render_mount(scene)

    assert not hasattr(mount, "get_pipeline")
    assert not hasattr(mount, "get_pipeline_names")
    assert not hasattr(mount, "get_pipeline_targets")

    engine.scene_manager.close_scene("declarative-mount")
