from termin.engine import RenderingManager


def test_builtin_default_pipeline_color_fbos_follow_output_render_target():
    pipeline = RenderingManager.instance().create_pipeline("Default")

    formats = {spec.resource: spec.format for spec in pipeline.pipeline_specs}

    assert formats["empty"] == "render_target"
    assert formats["skybox"] == "render_target"
    assert formats["color_opaque"] == "render_target"
    assert formats["color"] == "render_target"
    assert formats["color_bloom"] == "render_target"
    assert formats["color+widgets"] == "render_target"
