from termin.engine import RenderingManager
from termin.render_passes import ResolvePass, UIWidgetPass


def test_builtin_default_pipeline_color_fbos_follow_output_render_target():
    pipeline = RenderingManager.instance().create_pipeline("Default")

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


def test_builtin_default_pipeline_resolves_msaa_before_postfx():
    pipeline = RenderingManager.instance().create_pipeline("Default")

    pass_types = [frame_pass.type_name for frame_pass in pipeline.passes]
    pass_names = [frame_pass.pass_name for frame_pass in pipeline.passes]

    assert "ResolvePass" in pass_types
    assert pass_names.index("Resolve") < pass_names.index("Bloom")


def test_builtin_default_pipeline_uses_python_ui_widget_pass_when_available():
    pipeline = RenderingManager.instance().create_pipeline("Default")

    widget_pass = next(
        frame_pass for frame_pass in pipeline.passes
        if frame_pass.type_name == "UIWidgetPass"
    )

    assert isinstance(widget_pass.to_python(), UIWidgetPass)


def test_resolve_pass_strategy_defaults_to_average():
    frame_pass = ResolvePass()

    frame_pass._tc_pass.deserialize_data({"strategy": "average"})

    assert frame_pass.strategy == "average"
    assert frame_pass._tc_pass.serialize_data()["strategy"] == "average"
