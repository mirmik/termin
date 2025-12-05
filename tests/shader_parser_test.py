import pytest

from termin.visualization.render.shader_parser import (
    ShasderStage,
    ShaderMultyPhaseProgramm,
    ShaderPhase,
    UniformProperty,
    parse_shader_text,
    parse_uniform_directive,
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
    assert parsed["program"] == "demo"
    assert len(parsed["phases"]) == 1

    phase = parsed["phases"][0]
    assert phase["phase_mark"] == "main"
    assert phase["priority"] == 3
    assert phase["glDepthMask"] is False
    assert phase["glDepthTest"] is True
    assert phase["glBlend"] is True
    assert phase["glCull"] is False
    assert phase["stages"]["vertex"] == "void main() {}\n"


def test_render_state_directives_require_phase():
    directives = ("@glDepthTest true", "@glBlend true", "@glCull true")
    for directive in directives:
        with pytest.raises(ValueError):
            parse_shader_text(f"{directive}\n")


def test_render_state_directives_require_value():
    directives = ("@glDepthTest", "@glBlend", "@glCull")
    shader_body = "\n".join(["@phase main", "{directive}", "@endphase"])
    for directive in directives:
        with pytest.raises(ValueError):
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
    assert parsed["program"] == "composite"
    assert len(parsed["phases"]) == 2

    geometry = parsed["phases"][0]
    assert geometry["phase_mark"] == "geometry"
    assert geometry["priority"] == 1
    assert geometry["glDepthTest"] is True
    assert geometry["glDepthMask"] is None
    assert geometry["glBlend"] is None
    assert geometry["glCull"] is None
    assert geometry["stages"]["vertex"] == "// vertex stage\nvoid main() {}\n"
    assert geometry["stages"]["fragment"] == "// fragment stage\nvoid main() {\n  gl_FragColor = vec4(1.0);\n}\n"

    overlay = parsed["phases"][1]
    assert overlay["phase_mark"] == "overlay"
    assert overlay["priority"] == 0  # default value
    assert overlay["glDepthMask"] is False
    assert overlay["glDepthTest"] is False
    assert overlay["glBlend"] is True
    assert overlay["glCull"] is None
    assert overlay["stages"]["vertex"] == "// overlay vertex\n"


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


def test_parse_uniform_directive_float():
    """Тест парсинга @uniform директивы для float."""
    prop = parse_uniform_directive("@uniform float u_roughness 0.5")
    assert prop.name == "u_roughness"
    assert prop.uniform_type == "float"
    assert prop.default == 0.5
    assert prop.range_min is None
    assert prop.range_max is None


def test_parse_uniform_directive_float_with_range():
    """Тест парсинга @uniform директивы для float с range."""
    prop = parse_uniform_directive("@uniform float u_metallic 0.0 range(0.0, 1.0)")
    assert prop.name == "u_metallic"
    assert prop.uniform_type == "float"
    assert prop.default == 0.0
    assert prop.range_min == 0.0
    assert prop.range_max == 1.0


def test_parse_uniform_directive_color():
    """Тест парсинга @uniform директивы для color."""
    prop = parse_uniform_directive("@uniform color u_color 1.0 0.5 0.0 1.0")
    assert prop.name == "u_color"
    assert prop.uniform_type == "color"
    assert prop.default == (1.0, 0.5, 0.0, 1.0)


def test_parse_uniform_directive_vec3():
    """Тест парсинга @uniform директивы для vec3."""
    prop = parse_uniform_directive("@uniform vec3 u_lightDir 0.0 1.0 0.0")
    assert prop.name == "u_lightDir"
    assert prop.uniform_type == "vec3"
    assert prop.default == (0.0, 1.0, 0.0)


def test_parse_uniform_directive_texture2d():
    """Тест парсинга @uniform директивы для texture2d."""
    prop = parse_uniform_directive("@uniform texture2d u_mainTex")
    assert prop.name == "u_mainTex"
    assert prop.uniform_type == "texture2d"
    assert prop.default is None


def test_parse_uniform_in_phase():
    """Тест парсинга @uniform внутри @phase."""
    shader_text = "\n".join([
        "@program test",
        "@phase main",
        "@uniform float u_roughness 0.5",
        "@uniform color u_color 1.0 0.0 0.0 1.0",
        "@uniform float u_metallic 0.0 range(0.0, 1.0)",
        "@stage vertex",
        "void main() {}",
        "@endstage",
        "@endphase",
    ])

    parsed = parse_shader_text(shader_text)
    phase = parsed["phases"][0]

    assert len(phase["uniforms"]) == 3

    u_roughness = phase["uniforms"][0]
    assert isinstance(u_roughness, UniformProperty)
    assert u_roughness.name == "u_roughness"
    assert u_roughness.default == 0.5

    u_color = phase["uniforms"][1]
    assert u_color.name == "u_color"
    assert u_color.uniform_type == "color"
    assert u_color.default == (1.0, 0.0, 0.0, 1.0)

    u_metallic = phase["uniforms"][2]
    assert u_metallic.name == "u_metallic"
    assert u_metallic.range_min == 0.0
    assert u_metallic.range_max == 1.0


def test_shader_phase_from_tree_with_uniforms():
    """Тест создания ShaderPhase с uniforms через from_tree."""
    shader_text = "\n".join([
        "@phase opaque",
        "@uniform float u_value 0.7",
        "@stage vertex",
        "void main() {}",
        "@endstage",
        "@stage fragment",
        "void main() {}",
        "@endstage",
        "@endphase",
    ])

    parsed = parse_shader_text(shader_text)
    phase = ShaderPhase.from_tree(parsed["phases"][0])

    assert len(phase.uniforms) == 1
    assert phase.uniforms[0].name == "u_value"
    assert phase.uniforms[0].default == 0.7


def test_uniform_requires_phase():
    """@uniform вне @phase должен бросить ошибку."""
    with pytest.raises(ValueError, match="@uniform вне @phase"):
        parse_shader_text("@uniform float u_value 0.5")
