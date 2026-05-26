import pytest

from termin.materials import (
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
    assert phase.stages["vertex"].source == "#version 450 core\nvoid main() {}\n"


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
    assert geometry.stages["vertex"].source == "#version 450 core\n// vertex stage\nvoid main() {}\n"
    assert geometry.stages["fragment"].source == "#version 450 core\n// fragment stage\nvoid main() {\n  gl_FragColor = vec4(1.0);\n}\n"

    overlay = parsed.phases[1]
    assert overlay.phase_mark == "overlay"
    assert overlay.priority == 0  # default value
    assert overlay.gl_depth_mask is False
    assert overlay.gl_depth_test is False
    assert overlay.gl_blend is True
    assert overlay.gl_cull is None
    assert overlay.stages["vertex"].source == "#version 450 core\n// overlay vertex\n"


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
    assert depth_phase.stages["vertex"].source == "#version 450 core\nvoid main() {}\n"
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


def test_plain_uniforms_material_ubo_not_property():
    """Plain GLSL uniforms participate in shader UBO layout but not inspector properties."""
    shader_text = "\n".join([
        "@program test",
        "@phase main",
        "@property Float u_strength = 0.5",
        "@property Texture2D u_depth_texture = \"white\"",
        "@stage fragment",
        "#version 450 core",
        "uniform float u_strength;",
        "uniform mat4 u_fov_view;",
        "uniform sampler2D u_depth_texture;",
        "out vec4 FragColor;",
        "void main() { FragColor = texture(u_depth_texture, vec2(0.5)) * u_strength + vec4(u_fov_view[0][0]); }",
        "@endstage",
        "@endphase",
    ])

    program = parse_shader_text(shader_text)
    phase = program.phases[0]

    assert [prop.name for prop in program.material_properties] == ["u_strength", "u_depth_texture"]
    assert [prop.name for prop in phase.uniforms] == ["u_strength", "u_depth_texture"]
    assert [prop.name for prop in phase.material_uniforms] == ["u_fov_view"]
    assert [entry.name for entry in phase.material_ubo_layout.entries] == ["u_strength", "u_fov_view"]

    fragment = phase.stages["fragment"].source
    assert "layout(std140, binding = 1) uniform MaterialParams" in fragment
    assert "mat4 u_fov_view;" in fragment
    assert "layout(binding = 4) uniform sampler2D u_depth_texture;" in fragment
    assert "uniform mat4 u_fov_view;" not in fragment


def test_material_texture_bindings_skip_shadow_slot():
    shader_text = "\n".join([
        "@program test",
        "@phase main",
        "@property Texture2D u_tex0 = \"white\"",
        "@property Texture2D u_tex1 = \"white\"",
        "@property Texture2D u_tex2 = \"white\"",
        "@property Texture2D u_tex3 = \"white\"",
        "@property Texture2D u_tex4 = \"white\"",
        "@stage fragment",
        "#version 450 core",
        "uniform sampler2D u_tex0;",
        "uniform sampler2D u_tex1;",
        "uniform sampler2D u_tex2;",
        "uniform sampler2D u_tex3;",
        "uniform sampler2D u_tex4;",
        "out vec4 FragColor;",
        "void main() { FragColor = texture(u_tex0, vec2(0.5)) + texture(u_tex1, vec2(0.5)) + texture(u_tex2, vec2(0.5)) + texture(u_tex3, vec2(0.5)) + texture(u_tex4, vec2(0.5)); }",
        "@endstage",
        "@endphase",
    ])

    program = parse_shader_text(shader_text)
    fragment = program.phases[0].stages["fragment"].source

    assert "layout(binding = 4) uniform sampler2D u_tex0;" in fragment
    assert "layout(binding = 5) uniform sampler2D u_tex1;" in fragment
    assert "layout(binding = 6) uniform sampler2D u_tex2;" in fragment
    assert "layout(binding = 7) uniform sampler2D u_tex3;" in fragment
    assert "layout(binding = 9) uniform sampler2D u_tex4;" in fragment
    assert "layout(binding = 8) uniform sampler2D u_tex4;" not in fragment


def test_shader_interface_compare_separates_source_from_inputs():
    from termin.assets.shader_interface import compare_shader_interface

    base = parse_shader_text("\n".join([
        "@program test",
        "@phase main",
        "@property Texture2D u_input_tex = \"white\"",
        "@stage fragment",
        "#version 450 core",
        "uniform sampler2D u_input_tex;",
        "out vec4 FragColor;",
        "void main() { FragColor = texture(u_input_tex, vec2(0.5)); }",
        "@endstage",
        "@endphase",
    ]))
    source_only = parse_shader_text("\n".join([
        "@program test",
        "@phase main",
        "@property Texture2D u_input_tex = \"white\"",
        "@stage fragment",
        "#version 450 core",
        "uniform sampler2D u_input_tex;",
        "out vec4 FragColor;",
        "void main() { FragColor = texture(u_input_tex, vec2(0.25)); }",
        "@endstage",
        "@endphase",
    ]))
    texture_input_added = parse_shader_text("\n".join([
        "@program test",
        "@phase main",
        "@property Texture2D u_input_tex = \"white\"",
        "@property Texture2D u_depth_texture = \"depth_default\"",
        "@stage fragment",
        "#version 450 core",
        "uniform sampler2D u_input_tex;",
        "uniform sampler2D u_depth_texture;",
        "out vec4 FragColor;",
        "void main() { FragColor = texture(u_input_tex, vec2(0.5)) + texture(u_depth_texture, vec2(0.5)); }",
        "@endstage",
        "@endphase",
    ]))
    numeric_uniform_added = parse_shader_text("\n".join([
        "@program test",
        "@phase main",
        "@property Texture2D u_input_tex = \"white\"",
        "@stage fragment",
        "#version 450 core",
        "uniform sampler2D u_input_tex;",
        "uniform float u_factor;",
        "out vec4 FragColor;",
        "void main() { FragColor = texture(u_input_tex, vec2(0.5)) * u_factor; }",
        "@endstage",
        "@endphase",
    ]))

    no_interface_change = compare_shader_interface(base, source_only)
    assert no_interface_change.material_changed is False
    assert no_interface_change.graph_inputs_changed is False

    graph_input_change = compare_shader_interface(base, texture_input_added)
    assert graph_input_change.material_changed is True
    assert graph_input_change.graph_inputs_changed is True

    material_only_change = compare_shader_interface(base, numeric_uniform_added)
    assert material_only_change.material_changed is True
    assert material_only_change.graph_inputs_changed is False


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

    assert len(parsed.material_properties) == 3
    assert len(phase.uniforms) == 0

    u_roughness = parsed.material_properties[0]
    assert isinstance(u_roughness, MaterialProperty)
    assert u_roughness.name == "u_roughness"
    assert u_roughness.default == 0.5

    u_color = parsed.material_properties[1]
    assert u_color.name == "u_color"
    assert u_color.property_type == "Color"
    assert u_color.default == (1.0, 0.0, 0.0, 1.0)

    u_metallic = parsed.material_properties[2]
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

    assert len(parsed.material_properties) == 1
    assert parsed.material_properties[0].name == "u_value"
    assert parsed.material_properties[0].default == 0.7
    assert len(phase.uniforms) == 0


def test_property_outside_phase_accepted():
    """@property вне @phase принимается без ошибки (глобальное свойство)."""
    result = parse_shader_text("@property Float u_value = 0.5")
    assert len(result.phases) == 0
    assert len(result.material_properties) == 1
    assert result.material_properties[0].name == "u_value"
