from pathlib import Path

from termin.materials import TcMaterial
from termin.render_components import LineRenderer, LineRenderMode


VERTEX = """
#version 450
layout(location=0) in vec3 in_position;
void main() { gl_Position = vec4(in_position, 1.0); }
"""


FRAGMENT = """
#version 450
layout(location=0) out vec4 out_color;
void main() { out_color = vec4(1.0); }
"""


def create_line_test_material() -> TcMaterial:
    material = TcMaterial.create("LineRendererShadowPhaseTest", "")
    assert material.is_valid
    assert material.add_phase_from_sources(
        VERTEX,
        FRAGMENT,
        "",
        "LineRendererShadowPhaseTestShader",
        "opaque",
        0,
    ) is not None
    assert material.add_phase_from_sources(
        VERTEX,
        FRAGMENT,
        "",
        "LineRendererShadowPhaseTestShadowShader",
        "shadow",
        0,
    ) is not None
    return material


def test_line_renderer_defaults_to_world_billboard_mode():
    renderer = LineRenderer(points=[(0, 0, 0), (1, 0, 0)])

    assert renderer.render_mode == LineRenderMode.WorldBillboard
    assert renderer.raw_lines is False
    assert renderer.phase_marks == {"opaque"}


def test_line_renderer_world_mesh_fallback_builds_cpu_mesh():
    renderer = LineRenderer(points=[(0, 0, 0), (1, 0, 0)], render_mode=LineRenderMode.WorldMesh)

    assert renderer.render_mode == LineRenderMode.WorldMesh
    assert bool(renderer.get_mesh()) is True


def test_line_renderer_direct_modes_skip_shadow_material_phase():
    material = create_line_test_material()

    renderer = LineRenderer(points=[(0, 0, 0), (1, 0, 0)], material=material)

    assert renderer.phase_marks == {"opaque"}
    assert renderer.get_geometry_draws("shadow") == []


def test_line_renderer_cast_shadow_enables_shadow_material_phase():
    material = create_line_test_material()

    billboard = LineRenderer(
        points=[(0, 0, 0), (1, 0, 0)],
        material=material,
        cast_shadow=True,
    )
    assert billboard.phase_marks == {"opaque", "shadow"}

    renderer = LineRenderer(
        points=[(0, 0, 0), (1, 0, 0)],
        material=material,
        render_mode=LineRenderMode.WorldMesh,
        cast_shadow=True,
    )
    assert renderer.phase_marks == {"opaque", "shadow"}


def test_line_renderer_cast_shadow_uses_default_shadow_phase_when_material_lacks_one():
    renderer = LineRenderer(points=[(0, 0, 0), (1, 0, 0)], cast_shadow=True)

    assert renderer.phase_marks == {"opaque", "shadow"}


def test_line_renderer_mesh_mode_skips_shadow_when_cast_shadow_is_disabled():
    material = create_line_test_material()

    renderer = LineRenderer(
        points=[(0, 0, 0), (1, 0, 0)],
        material=material,
        render_mode=LineRenderMode.WorldMesh,
    )

    assert renderer.phase_marks == {"opaque"}


def test_line_renderer_world_tube_is_gpu_direct_mode():
    renderer = LineRenderer(
        points=[(0, 0, 0), (1, 0, 0)],
        render_mode=LineRenderMode.WorldTube,
        tube_sides=6,
    )

    assert renderer.render_mode == LineRenderMode.WorldTube
    assert renderer.tube_sides == 6
    assert renderer.get_mesh().is_valid is False


def test_line_renderer_keeps_legacy_raw_lines_constructor_position():
    renderer = LineRenderer([(0, 0, 0), (1, 0, 0)], 0.25, True)

    assert renderer.raw_lines is True
    assert bool(renderer.get_mesh()) is True


def test_line_renderer_points_are_inspectable():
    from termin.inspect import InspectRegistry
    from termin.visualization.core.entity import Entity

    registry = InspectRegistry.instance()
    fields = {field.path: field for field in registry.all_fields("LineRenderer")}

    assert fields["points"].label == "Positions"
    assert fields["points"].kind == "list[vec3]"
    assert fields["cast_shadow"].label == "Cast Shadow"
    assert fields["cast_shadow"].kind == "bool"
    assert fields["tube_sides"].label == "Tube Sides"
    assert fields["tube_sides"].kind == "int"
    assert fields["render_mode"].label == "Render Mode"
    assert fields["render_mode"].kind == "enum"
    assert [(choice.value, choice.label) for choice in fields["render_mode"].choices] == [
        ("0", "World Billboard"),
        ("1", "Screen Space"),
        ("2", "World Mesh"),
        ("3", "Raw Lines"),
        ("4", "World Tube"),
    ]

    entity = Entity(name="line")
    component = entity.add_component_by_name("LineRenderer")
    component.set_field("points", [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
    component.set_field("render_mode", "4")

    assert component.get_field("points") == [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]
    assert component.get_field("render_mode") == 4
    assert component.to_python().points == [(1.0, 2.0, 3.0), (4.0, 5.0, 6.0)]
    assert component.to_python().render_mode == LineRenderMode.WorldTube


def test_depth_conversion_passes_bind_textures_by_reflected_name():
    source = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "depth_pass.cpp"
    ).read_text(encoding="utf-8")

    assert 'bind_texture("u_depth_tex", depth_tex)' in source
    assert 'bind_texture("u_color_tex", color_tex)' in source
    assert "bind_sampled_texture(9" not in source
