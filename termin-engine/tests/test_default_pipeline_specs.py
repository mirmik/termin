from termin.bootstrap import bootstrap_player

bootstrap_player()

import pytest

from termin.engine import EngineCore, RenderingManager
from termin.render_passes import ResolvePass, UIWidgetPass


@pytest.fixture
def rendering_manager():
    engine = EngineCore()
    try:
        yield RenderingManager.instance()
    finally:
        del engine


def test_rendering_manager_instance_or_none_without_engine():
    assert RenderingManager.instance_or_none() is None


def test_builtin_default_pipeline_color_fbos_follow_output_render_target(rendering_manager):
    pipeline = rendering_manager.create_pipeline("Default")

    formats = {spec.resource: spec.format for spec in pipeline.pipeline_specs}
    samples = {spec.resource: spec.samples for spec in pipeline.pipeline_specs}

    assert formats["empty"] == "render_target"
    assert formats["skybox"] == "render_target"
    assert formats["color_opaque"] == "render_target"
    assert formats["color"] == "render_target"
    assert formats["color_resolved"] == "render_target"
    assert formats["color_bloom"] == "render_target"
    assert formats["color+widgets"] == "render_target"

    assert samples["empty"] == 4
    assert samples["skybox"] == 4
    assert samples["color_opaque"] == 4
    assert samples["color"] == 4
    assert samples["color_resolved"] == 1


def test_builtin_default_pipeline_resolves_msaa_before_postfx(rendering_manager):
    pipeline = rendering_manager.create_pipeline("Default")

    pass_types = [frame_pass.type_name for frame_pass in pipeline.passes]
    pass_names = [frame_pass.pass_name for frame_pass in pipeline.passes]

    assert "ResolvePass" in pass_types
    assert pass_names.index("Resolve") < pass_names.index("Bloom")


def test_builtin_default_pipeline_uses_python_ui_widget_pass_when_available(rendering_manager):
    pipeline = rendering_manager.create_pipeline("Default")

    widget_pass = next(
        frame_pass for frame_pass in pipeline.passes
        if frame_pass.type_name == "UIWidgetPass"
    )

    assert isinstance(widget_pass.to_python(), UIWidgetPass)


def test_resolve_pass_serialized_schema_has_no_strategy():
    frame_pass = ResolvePass()

    with pytest.raises(AttributeError):
        _ = frame_pass.strategy
    assert "strategy" not in frame_pass._tc_pass.serialize_data()

    frame_pass._tc_pass.deserialize_data({"strategy": "average"})

    assert "strategy" not in frame_pass._tc_pass.serialize_data()


def test_rendering_manager_nullable_callbacks_accept_none(rendering_manager):
    rendering_manager.set_make_current_callback(None)
    rendering_manager.set_display_factory(None)
    rendering_manager.set_pipeline_factory(None)
    rendering_manager.set_render_request_callback(None)
    rendering_manager.set_display_removed_callback(None)
