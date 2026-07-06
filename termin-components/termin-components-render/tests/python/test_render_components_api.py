from pathlib import Path

import pytest

from termin.bootstrap import bootstrap_player

bootstrap_player()

from termin.materials import TcMaterial
from termin.render_components import (
    Camera,
    CameraController,
    CameraProjection,
    DepthOnlyPass,
    DepthPass,
    LineRenderer,
    LineRenderMode,
    MaterialPass,
    MeshRenderer,
    NormalPass,
    WorldTextAnchor,
    WorldTextComponent,
    WorldTextOrientation,
    get_texture_inputs_for_material,
)


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


def test_render_components_exports_camera_controller_and_material_pass_helpers():
    camera = Camera.perspective_deg(60.0, 16.0 / 9.0)

    assert camera.projection_type == CameraProjection.Perspective
    assert CameraController.__name__ == "CameraController"
    assert MaterialPass.inspect_fields["material"].kind == "tc_material"
    assert MaterialPass.get_texture_inputs_for_material is not None
    assert get_texture_inputs_for_material("(None)") == []


def test_depth_and_normal_passes_expose_explicit_phase_mark():
    from termin.inspect import InspectRegistry

    depth = DepthPass()
    depth_only = DepthOnlyPass()
    normal = NormalPass()

    assert depth.phase_mark == "depth"
    assert depth_only.phase_mark == "depth"
    assert normal.phase_mark == "normal"

    depth.phase_mark = "custom_depth"
    depth_only.phase_mark = "custom_depth_only"
    normal.phase_mark = "custom_normals"

    assert depth.phase_mark == "custom_depth"
    assert depth_only.phase_mark == "custom_depth_only"
    assert normal.phase_mark == "custom_normals"

    registry = InspectRegistry.instance()
    for type_name in ("DepthPass", "DepthOnlyPass", "NormalPass"):
        fields = {field.path: field for field in registry.all_fields(type_name)}
        assert fields["phase_mark"].label == "Phase Mark"
        assert fields["phase_mark"].kind == "string"


def test_depth_and_normal_passes_deserialize_phase_mark():
    default_depth = DepthPass._deserialize_instance({"pass_name": "Depth", "data": {}}, None)
    default_depth_only = DepthOnlyPass._deserialize_instance(
        {"pass_name": "DepthOnly", "data": {}},
        None,
    )
    default_normal = NormalPass._deserialize_instance({"pass_name": "Normal", "data": {}}, None)

    assert default_depth.phase_mark == "depth"
    assert default_depth_only.phase_mark == "depth"
    assert default_normal.phase_mark == "normal"

    depth = DepthPass._deserialize_instance(
        {"pass_name": "Depth", "data": {"phase_mark": "custom_depth"}},
        None,
    )
    depth_only = DepthOnlyPass._deserialize_instance(
        {"pass_name": "DepthOnly", "data": {"phase_mark": "custom_depth_only"}},
        None,
    )
    normal = NormalPass._deserialize_instance(
        {"pass_name": "Normal", "data": {"phase_mark": "custom_normals"}},
        None,
    )

    assert depth.phase_mark == "custom_depth"
    assert depth_only.phase_mark == "custom_depth_only"
    assert normal.phase_mark == "custom_normals"


def test_depth_and_normal_passes_deserialize_legacy_material_phase_mark():
    depth = DepthPass._deserialize_instance(
        {"pass_name": "Depth", "data": {"material_phase_mark": "custom_depth"}},
        None,
    )
    depth_only = DepthOnlyPass._deserialize_instance(
        {"pass_name": "DepthOnly", "data": {"material_phase_mark": "custom_depth_only"}},
        None,
    )
    normal = NormalPass._deserialize_instance(
        {"pass_name": "Normal", "data": {"material_phase_mark": "custom_normals"}},
        None,
    )

    assert depth.phase_mark == "custom_depth"
    assert depth_only.phase_mark == "custom_depth_only"
    assert normal.phase_mark == "custom_normals"


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


def test_mesh_renderer_get_phases_for_mark_returns_non_owning_phase_refs():
    material = create_line_test_material()
    renderer = MeshRenderer(material=material)

    opaque = renderer.get_phases_for_mark("opaque")
    shadow = renderer.get_phases_for_mark("shadow")

    assert [phase.phase_mark for phase in opaque] == ["opaque"]
    assert [phase.phase_mark for phase in shadow] == ["shadow"]
    assert material.phases[0].phase_mark == "opaque"


def test_mesh_renderer_rejects_legacy_mesh_constructor_argument():
    with pytest.raises(TypeError):
        MeshRenderer(mesh="Cube")


def test_mesh_renderer_no_longer_exposes_mesh_mutators():
    renderer = MeshRenderer()

    with pytest.raises(AttributeError):
        _ = renderer.set_mesh
    with pytest.raises(AttributeError):
        _ = renderer.set_mesh_by_name
    with pytest.raises(AttributeError):
        _ = renderer.mesh


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
    from termin.scene import Entity

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


def test_world_text_component_defaults_to_transparent_direct_draw():
    text = WorldTextComponent("e4", size=0.5)

    assert text.text == "e4"
    assert text.size == 0.5
    assert text.anchor == WorldTextAnchor.Center
    assert text.anchor_name == "center"
    assert text.orientation == WorldTextOrientation.Billboard
    assert text.orientation_name == "billboard"
    assert text.plane_normal == (0.0, 0.0, 1.0)
    assert text.text_up == (0.0, 1.0, 0.0)
    assert text.depth_test is True
    assert text.depth_write is False
    assert text.blend is True
    assert text.phase_marks == {"transparent"}
    assert text.get_geometry_draws("opaque") == []
    assert len(text.get_geometry_draws("transparent")) == 1


def test_world_text_component_hides_empty_text_from_draw_contract():
    text = WorldTextComponent()

    assert text.phase_marks == set()
    assert text.get_geometry_draws() == []

    text.text = "A"
    text.phase_mark = "overlay"
    assert text.phase_marks == {"overlay"}
    assert len(text.get_geometry_draws()) == 1


def test_world_text_component_is_inspectable():
    from termin.inspect import InspectRegistry
    from termin.scene import Entity

    registry = InspectRegistry.instance()
    fields = {field.path: field for field in registry.all_fields("WorldTextComponent")}

    assert fields["text"].label == "Text"
    assert fields["text"].kind == "string"
    assert fields["local_offset"].label == "Local Offset"
    assert fields["local_offset"].kind == "vec3"
    assert fields["color"].label == "Color"
    assert fields["color"].kind == "color"
    assert fields["anchor"].label == "Anchor"
    assert fields["anchor"].kind == "enum"
    assert [(choice.value, choice.label) for choice in fields["anchor"].choices] == [
        ("0", "Left"),
        ("1", "Center"),
        ("2", "Right"),
    ]
    assert fields["orientation"].label == "Orientation"
    assert fields["orientation"].kind == "enum"
    assert [(choice.value, choice.label) for choice in fields["orientation"].choices] == [
        ("0", "Billboard"),
        ("1", "Fixed"),
    ]
    assert fields["plane_normal"].label == "Plane Normal"
    assert fields["plane_normal"].kind == "vec3"
    assert fields["text_up"].label == "Text Up"
    assert fields["text_up"].kind == "vec3"

    entity = Entity(name="world text")
    component = entity.add_component_by_name("WorldTextComponent")
    component.set_field("text", "Nf3")
    component.set_field("anchor", "2")
    component.set_field("orientation", "1")
    component.set_field("plane_normal", [0.0, 0.0, 1.0])
    component.set_field("text_up", [0.0, 1.0, 0.0])
    component.set_field("size", 0.75)

    assert component.get_field("text") == "Nf3"
    assert component.get_field("anchor") == 2
    assert component.get_field("orientation") == 1
    assert component.get_field("plane_normal") == [0.0, 0.0, 1.0]
    assert component.get_field("text_up") == [0.0, 1.0, 0.0]
    assert component.get_field("size") == 0.75
    assert component.to_python().anchor == WorldTextAnchor.Right
    assert component.to_python().anchor_name == "right"
    assert component.to_python().orientation == WorldTextOrientation.Fixed
    assert component.to_python().orientation_name == "fixed"


def test_depth_conversion_passes_bind_textures_by_reflected_name():
    source = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "depth_pass.cpp"
    ).read_text(encoding="utf-8")

    assert 'bind_texture("u_depth_tex", depth_tex)' in source
    assert 'bind_texture("u_color_tex", color_tex)' in source
    assert "bind_sampled_texture(9" not in source
