import pytest

from termin.visualization.render.shader_parser import (
    ShasderStage,
    ShaderMultyPhaseProgramm,
    ShaderPhase,
    MaterialProperty,
    parse_shader_text,
    parse_property_directive,
)


def test_parse_render_state_directives():
    shader_text = "\n".join(
        [
            "@program demo",
            "@phase main",
            "@priority 3",
            "@glDepthMask false",
            "@glDepthTest true",
            "@glBlend on",
            "@glCull off",
            "@stage vertex",
            "void main() {}",
            "@endstage",
            "@endphase",
        ]
    )

    parsed = parse_shader_text(shader_text)
    assert parsed.program == "demo"
    assert len(parsed.phases) == 1

    phase = parsed.phases[0]
    assert phase.phase_mark == "main"
    assert phase.priority == 3
    assert phase.gl_depth_mask is False
    assert phase.gl_depth_test is True
    assert phase.gl_blend is True
    assert phase.gl_cull is False
    assert phase.stages["vertex"].source == "void main() {}\n"


def test_render_state_directives_require_phase():
    directives = ("@glDepthTest true", "@glBlend true", "@glCull true")
    for directive in directives:
        with pytest.raises(RuntimeError):
            parse_shader_text(f"{directive}\n")


def test_render_state_directives_require_value():
    directives = ("@glDepthTest", "@glBlend", "@glCull")
    shader_body = "\n".join(["@phase main", "{directive}", "@endphase"])
    for directive in directives:
        with pytest.raises(RuntimeError):
            parse_shader_text(shader_body.format(directive=directive))


def test_parse_multiple_phases_and_stages():
    shader_text = "\n".join(
        [
            "@program composite",
            "@phase geometry",
            "@priority 1",
            "@glDepthTest on",
            "@stage vertex",
            "// vertex stage",
            "void main() {}",
            "@endstage",
            "@stage fragment",
            "// fragment stage",
            "void main() {",
            "  gl_FragColor = vec4(1.0);",
            "}",
            "@endstage",
            "@endphase",
            "@phase overlay",
            "@glDepthMask off",
            "@glDepthTest off",
            "@glBlend true",
            "@stage vertex",
            "// overlay vertex",
            "@endstage",
            "@endphase",
        ]
    )

    parsed = parse_shader_text(shader_text)
    assert parsed.program == "composite"
    assert len(parsed.phases) == 2

    geometry = parsed.phases[0]
    assert geometry.phase_mark == "geometry"
    assert geometry.priority == 1
    assert geometry.gl_depth_test is True
    assert geometry.gl_depth_mask is None
    assert geometry.gl_blend is None
    assert geometry.gl_cull is None
    assert geometry.stages["vertex"].source == "// vertex stage\nvoid main() {}\n"
    assert geometry.stages["fragment"].source == "// fragment stage\nvoid main() {\n  gl_FragColor = vec4(1.0);\n}\n"

    overlay = parsed.phases[1]
    assert overlay.phase_mark == "overlay"
    assert overlay.priority == 0  # default value
    assert overlay.gl_depth_mask is False
    assert overlay.gl_depth_test is False
    assert overlay.gl_blend is True
    assert overlay.gl_cull is None
    assert overlay.stages["vertex"].source == "// overlay vertex\n"


def test_tree_builders_have_uniform_signature():
    shader_text = "\n".join(
        [
            "@program mesh",
            "@phase depth",
            "@glDepthTest true",
            "@stage vertex",
            "void main() {}",
            "@endstage",
            "@endphase",
        ]
    )
    tree = parse_shader_text(shader_text)
    program = ShaderMultyPhaseProgramm.from_tree(tree)

    assert program.program == "mesh"
    assert len(program.phases) == 1

    depth_phase = program.phases[0]
    assert isinstance(depth_phase, ShaderPhase)
    assert depth_phase.phase_mark == "depth"
    assert depth_phase.gl_depth_test is True
    assert depth_phase.gl_blend is None
    assert depth_phase.gl_depth_mask is None
    assert depth_phase.stages["vertex"].source == "void main() {}\n"
    assert isinstance(depth_phase.stages["vertex"], ShasderStage)


def test_parse_property_directive_float():
    """Тест парсинга @property директивы для Float."""
    prop = parse_property_directive("@property Float u_roughness = 0.5")
    assert prop.name == "u_roughness"
    assert prop.property_type == "Float"
    assert prop.default == 0.5
    assert prop.range_min is None
    assert prop.range_max is None


def test_parse_property_directive_float_with_range():
    """Тест парсинга @property директивы для Float с range."""
    prop = parse_property_directive("@property Float u_metallic = 0.0 range(0.0, 1.0)")
    assert prop.name == "u_metallic"
    assert prop.property_type == "Float"
    assert prop.default == 0.0
    assert prop.range_min == 0.0
    assert prop.range_max == 1.0


def test_parse_property_directive_color():
    """Тест парсинга @property директивы для Color."""
    prop = parse_property_directive("@property Color u_color = Color(1.0, 0.5, 0.0, 1.0)")
    assert prop.name == "u_color"
    assert prop.property_type == "Color"
    assert prop.default == (1.0, 0.5, 0.0, 1.0)


def test_parse_property_directive_vec3():
    """Тест парсинга @property директивы для Vec3."""
    prop = parse_property_directive("@property Vec3 u_lightDir = Vec3(0.0, 1.0, 0.0)")
    assert prop.name == "u_lightDir"
    assert prop.property_type == "Vec3"
    assert prop.default == (0.0, 1.0, 0.0)


def test_parse_property_directive_texture2d():
    """Тест парсинга @property директивы для Texture."""
    prop = parse_property_directive("@property Texture u_mainTex")
    assert prop.name == "u_mainTex"
    assert prop.property_type == "Texture"
    assert prop.default is None


def test_parse_property_in_phase():
    """Тест парсинга @property внутри @phase."""
    shader_text = "\n".join([
        "@program test",
        "@phase main",
        "@property Float u_roughness = 0.5",
        "@property Color u_color = Color(1.0, 0.0, 0.0, 1.0)",
        "@property Float u_metallic = 0.0 range(0.0, 1.0)",
        "@stage vertex",
        "void main() {}",
        "@endstage",
        "@endphase",
    ])

    parsed = parse_shader_text(shader_text)
    phase = parsed.phases[0]

    assert len(phase.uniforms) == 3

    u_roughness = phase.uniforms[0]
    assert isinstance(u_roughness, MaterialProperty)
    assert u_roughness.name == "u_roughness"
    assert u_roughness.default == 0.5

    u_color = phase.uniforms[1]
    assert u_color.name == "u_color"
    assert u_color.property_type == "Color"
    assert u_color.default == (1.0, 0.0, 0.0, 1.0)

    u_metallic = phase.uniforms[2]
    assert u_metallic.name == "u_metallic"
    assert u_metallic.range_min == 0.0
    assert u_metallic.range_max == 1.0


def test_shader_phase_from_tree_with_properties():
    """Тест создания ShaderPhase с properties через from_tree."""
    shader_text = "\n".join([
        "@phase opaque",
        "@property Float u_value = 0.7",
        "@stage vertex",
        "void main() {}",
        "@endstage",
        "@stage fragment",
        "void main() {}",
        "@endstage",
        "@endphase",
    ])

    parsed = parse_shader_text(shader_text)
    phase = ShaderPhase.from_tree(parsed.phases[0])

    assert len(phase.uniforms) == 1
    assert phase.uniforms[0].name == "u_value"
    assert phase.uniforms[0].default == 0.7


def test_property_outside_phase_accepted():
    """@property вне @phase принимается без ошибки (глобальное свойство)."""
    result = parse_shader_text("@property Float u_value = 0.5")
    assert len(result.phases) == 0
