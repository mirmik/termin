from termin.render_components import LineRenderer, LineRenderMode


def test_line_renderer_defaults_to_world_billboard_mode():
    renderer = LineRenderer(points=[(0, 0, 0), (1, 0, 0)])

    assert renderer.render_mode == LineRenderMode.WorldBillboard
    assert renderer.raw_lines is False
    assert renderer.phase_marks == {"opaque"}


def test_line_renderer_world_mesh_fallback_builds_cpu_mesh():
    renderer = LineRenderer(points=[(0, 0, 0), (1, 0, 0)], render_mode=LineRenderMode.WorldMesh)

    assert renderer.render_mode == LineRenderMode.WorldMesh
    assert bool(renderer.get_mesh()) is True


def test_line_renderer_keeps_legacy_raw_lines_constructor_position():
    renderer = LineRenderer([(0, 0, 0), (1, 0, 0)], 0.25, True)

    assert renderer.raw_lines is True
    assert bool(renderer.get_mesh()) is True
