import pytest

from termin.materials import (
    ShasderStage,
    ShaderMultyPhaseProgramm,
    ShaderPhase,
    SurfaceContractDescriptor,
    SurfaceContractKey,
    SurfaceContractRegistry,
    MaterialProperty,
    create_material_from_parsed,
    parse_shader_text,
    parse_property_directive,
)


def _register_surface_contracts() -> None:
    assert SurfaceContractRegistry.register_builtins()


def _surface_shader(
    *,
    contract: str = "termin.surface.standard-pbr",
    version: int = 1,
    surface_type: str = "TerminStandardSurfaceV1",
    entry: str = "evaluate_surface",
    evaluator_name: str = "evaluate_surface",
) -> str:
    return "\n".join(
        [
            "@program surface-demo",
            "@language slang",
            '@property Texture2D albedo = "white" encoding(srgb)',
            "@property Float roughness = 0.5",
            "@phase opaque",
            (
                f"@surface contract={contract} version={version} "
                f"type={surface_type} entry={entry}"
            ),
            "@surfaceInput world_pos float3",
            "@surfaceInput normal_world float3",
            "@stage vertex vs_main",
            "struct VertexInput { float3 position : POSITION; };",
            "float4 vs_main(VertexInput input) : SV_Position {",
            "    return float4(input.position, 1.0);",
            "}",
            "@endstage",
            "@stage fragment",
            (
                f"{surface_type} {evaluator_name}(FragmentInput input) {{"
            ),
            f"    {surface_type} result;",
            "    result.base_color = albedo.Sample(albedo_sampler, float2(0.0)).rgb;",
            "    result.normal_world = input.normal_world;",
            "    result.metallic = 0.0;",
            "    result.perceptual_roughness = roughness;",
            "    result.occlusion = 1.0;",
            "    result.emission = float3(0.0);",
            "    result.opacity = 1.0;",
            "    return result;",
            "}",
            "@endstage",
            "@endphase",
        ]
    )


def test_parse_render_state_directives():
    shader_text = "\n".join(
        [
            "@program demo",
            "@language slang",
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
            "@language slang",
            "@phase geometry",
            "@priority 1",
            "@glDepthTest on",
            "@stage vertex",
            "// vertex stage",
            "void main() {}",
            "@endstage",
            "@stage fragment",
            "// fragment stage",
            "float4 main() : SV_Target0 {",
            "  return float4(1.0);",
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
    assert geometry.stages["fragment"].source == "// fragment stage\nfloat4 main() : SV_Target0 {\n  return float4(1.0);\n}\n"

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
            "@language slang",
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


def test_parse_property_directive_srgb_color():
    """SrgbColor keeps its explicit semantic type and constructor."""
    prop = parse_property_directive("@property SrgbColor u_color = SrgbColor(1.0, 0.5, 0.0, 1.0)")
    assert prop.name == "u_color"
    assert prop.property_type == "SrgbColor"
    assert prop.default == (1.0, 0.5, 0.0, 1.0)


def test_parse_property_directive_linear_color_defaults_to_white():
    prop = parse_property_directive("@property LinearColor u_color")
    assert prop.property_type == "LinearColor"
    assert prop.default == (1.0, 1.0, 1.0, 1.0)


@pytest.mark.parametrize(
    "directive",
    [
        "@property Color u_color = Color(1, 1, 1, 1)",
        "@property SrgbColor u_color = Color(1, 1, 1, 1)",
        "@property LinearColor u_color = SrgbColor(1, 1, 1, 1)",
    ],
)
def test_parse_property_directive_rejects_legacy_or_mismatched_color_constructor(directive):
    with pytest.raises(RuntimeError, match="SrgbColor|LinearColor"):
        parse_property_directive(directive)


@pytest.mark.parametrize(
    "directive",
    [
        "@property Float u_value = Color(1, 1, 1, 1)",
        "@property Vec4 u_value = Color(1, 1, 1, 1)",
    ],
)
def test_legacy_color_constructor_is_actionable_for_any_declared_type(directive):
    with pytest.raises(RuntimeError, match="SrgbColor.*LinearColor"):
        parse_property_directive(directive)


@pytest.mark.parametrize(
    "directive",
    [
        "@property Vec3 u_value = Vec3(1, 2)",
        "@property LinearColor u_value = LinearColor(1, 2, 3)",
        "@property SrgbColor u_value = SrgbColor(1, 2, 3, 4, 5)",
        "@property Vec2 u_value = [1, 2, 3]",
    ],
)
def test_parse_property_directive_rejects_wrong_component_count(directive):
    with pytest.raises(RuntimeError, match="exactly"):
        parse_property_directive(directive)


@pytest.mark.parametrize(
    "directive",
    [
        "@property Float u_value = 1.0junk",
        "@property Int u_value = 2.5",
        "@property SrgbColor u_value = SrgbColor(1, 0.5junk, 0, 1)",
    ],
)
def test_parse_property_directive_rejects_partial_numeric_defaults(directive):
    with pytest.raises(RuntimeError, match="Invalid"):
        parse_property_directive(directive)


def test_parse_property_directive_vec3():
    """Тест парсинга @property директивы для Vec3."""
    prop = parse_property_directive("@property Vec3 u_lightDir = Vec3(0.0, 1.0, 0.0)")
    assert prop.name == "u_lightDir"
    assert prop.property_type == "Vec3"
    assert prop.default == (0.0, 1.0, 0.0)


def test_parse_property_directive_texture2d():
    """Тест парсинга @property директивы для Texture."""
    prop = parse_property_directive("@property Texture u_mainTex encoding(srgb)")
    assert prop.name == "u_mainTex"
    assert prop.property_type == "Texture"
    assert prop.default is None
    assert prop.expected_encoding == "srgb"

    linear = parse_property_directive(
        '@property Texture2D u_normal = "normal" encoding(linear)'
    )
    assert linear.property_type == "Texture"
    assert linear.default == "normal"
    assert linear.expected_encoding == "linear"

    unconstrained = parse_property_directive(
        '@property Texture2D u_input = "white"'
    )
    assert unconstrained.property_type == "Texture"
    assert unconstrained.default == "white"
    assert unconstrained.expected_encoding is None

    unconstrained_normal = parse_property_directive(
        '@property Texture2D u_normal = "normal"'
    )
    assert unconstrained_normal.default == "normal"
    assert unconstrained_normal.expected_encoding is None


def test_create_material_from_unconstrained_texture_property_uses_linear_default():
    from termin.graphics import TextureEncoding

    program = parse_shader_text("\n".join([
        "@program unconstrained-texture",
        "@language slang",
        '@property Texture2D u_input = "white"',
        "@phase opaque",
        "@stage vertex vs_main",
        "float4 vs_main(float3 position : POSITION) : SV_Position {",
        "    return float4(position, 1.0);",
        "}",
        "@endstage",
        "@stage fragment fs_main",
        "float4 fs_main(float2 uv : TEXCOORD0) : SV_Target0 {",
        "    return u_input.Sample(uv);",
        "}",
        "@endstage",
        "@endphase",
    ]))

    material = create_material_from_parsed(program)
    texture = material.textures["u_input"]

    assert texture.is_valid
    assert texture.encoding == TextureEncoding.LINEAR


@pytest.mark.parametrize(
    ("directive", "message"),
    [
        (
            '@property Texture2D u_albedo = "white" encoding(display-p3)',
            "Unknown texture encoding",
        ),
        (
            "@property Float u_value = 1.0 encoding(linear)",
            "only valid for Texture2D",
        ),
        (
            '@property Texture2D u_albedo = "white" encoding srgb',
            "Malformed encoding",
        ),
        (
            '@property Texture2D u_albedo = "white" '
            "encoding(srgb) encoding(linear)",
            "Duplicate encoding",
        ),
        (
            '@property Texture2D u_albedo = "checker" encoding(srgb)',
            "default must be",
        ),
        (
            '@property Texture2D u_normal = "normal" encoding(srgb)',
            "normal.*encoding\\(linear\\)",
        ),
    ],
)
def test_parse_property_directive_rejects_invalid_encoding_contract(
    directive: str,
    message: str,
) -> None:
    with pytest.raises(RuntimeError, match=message):
        parse_property_directive(directive)


def test_parse_shader_text_rejects_implicit_glsl_shader():
    shader_text = "\n".join([
        "@program test",
        "@phase main",
        "@property Float u_strength = 0.5",
        "@stage fragment",
        "#version 450 core",
        "uniform float u_strength;",
        "out vec4 FragColor;",
        "void main() { FragColor = vec4(u_strength); }",
        "@endstage",
        "@endphase",
    ])

    with pytest.raises(RuntimeError, match="implicit GLSL .shader programs are no longer supported"):
        parse_shader_text(shader_text)


def test_slang_material_texture_declarations_are_synthesized():
    shader_text = "\n".join([
        "@program test",
        "@language slang",
        "@phase main",
        "@property Texture2D u_tex0 = \"white\" encoding(srgb)",
        "@property Texture2D u_tex1 = \"white\" encoding(srgb)",
        "@property Texture2D u_tex2 = \"white\" encoding(srgb)",
        "@property Texture2D u_tex3 = \"white\" encoding(srgb)",
        "@property Texture2D u_tex4 = \"white\" encoding(srgb)",
        "@stage fragment",
        "[shader(\"fragment\")] float4 main(float2 uv : TEXCOORD0) : SV_Target0 {",
        "    return u_tex0.Sample(uv) + u_tex1.Sample(uv) + u_tex2.Sample(uv) + u_tex3.Sample(uv) + u_tex4.Sample(uv);",
        "}",
        "@endstage",
        "@endphase",
    ])

    program = parse_shader_text(shader_text)
    fragment = program.phases[0].stages["fragment"].source

    assert "Sampler2D u_tex0;" in fragment
    assert "Sampler2D u_tex1;" in fragment
    assert "Sampler2D u_tex2;" in fragment
    assert "Sampler2D u_tex3;" in fragment
    assert "Sampler2D u_tex4;" in fragment
    assert "register(" not in fragment
    assert "layout(" not in fragment


def test_parse_property_in_phase():
    """Тест парсинга @property внутри @phase."""
    shader_text = "\n".join([
        "@program test",
        "@language slang",
        "@phase main",
        "@property Float u_roughness = 0.5",
        "@property SrgbColor u_color = SrgbColor(1.0, 0.0, 0.0, 1.0)",
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
    assert u_color.property_type == "SrgbColor"
    assert u_color.default == (1.0, 0.0, 0.0, 1.0)

    u_metallic = parsed.material_properties[2]
    assert u_metallic.name == "u_metallic"
    assert u_metallic.range_min == 0.0
    assert u_metallic.range_max == 1.0


def test_shader_phase_from_tree_with_properties():
    """Тест создания ShaderPhase с properties через from_tree."""
    shader_text = "\n".join([
        "@language slang",
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
    result = parse_shader_text("@language slang\n@property Float u_value = 0.5")
    assert len(result.phases) == 0
    assert len(result.material_properties) == 1
    assert result.material_properties[0].name == "u_value"


def test_parse_slang_shader_keeps_source_unrewritten():
    shader_text = "\n".join([
        "@program SlangSample",
        "@language slang",
        "@phase opaque",
        "@stage vertex",
        "struct VertexOutput { float4 position : SV_Position; };",
        "[shader(\"vertex\")] VertexOutput main() { VertexOutput o; o.position = float4(0, 0, 0, 1); return o; }",
        "@endstage",
        "@stage fragment",
        "struct FragmentOutput { float4 color : SV_Target0; };",
        "[shader(\"fragment\")] FragmentOutput main() { FragmentOutput o; o.color = float4(1, 0, 0, 1); return o; }",
        "@endstage",
        "@endphase",
    ])

    program = parse_shader_text(shader_text)
    assert program.language == "slang"
    vertex = program.phases[0].stages["vertex"].source
    assert "[shader(\"vertex\")]" in vertex
    assert "#version" not in vertex
    assert "uniform PerFrame" not in vertex


def test_slang_shader_synthesizes_material_params_for_scalar_properties():
    shader_text = "\n".join([
        "@program SlangWithProps",
        "@language slang",
        "@property SrgbColor u_color = SrgbColor(1, 1, 1, 1)",
        "@phase opaque",
        "@stage vertex",
        "struct VertexOutput { float4 position : SV_Position; };",
        "[shader(\"vertex\")] VertexOutput main() {",
        "    VertexOutput output;",
        "    output.position = float4(0, 0, 0, 1);",
        "    return output;",
        "}",
        "@endstage",
        "@stage fragment",
        "struct FragmentOutput { float4 color : SV_Target0; };",
        "[shader(\"fragment\")] FragmentOutput main() {",
        "    FragmentOutput output;",
        "    output.color = material.u_color;",
        "    return output;",
        "}",
        "@endstage",
        "@endphase",
    ])

    program = parse_shader_text(shader_text)
    phase = next(phase for phase in program.phases if phase.phase_mark == "opaque")
    assert [entry.name for entry in phase.material_ubo_layout.entries] == ["u_color"]

    fragment = phase.stages["fragment"].source
    assert "import termin_prelude;" in fragment
    assert "struct MaterialParams" in fragment
    assert "float4 u_color;" in fragment
    assert "[[TerminScope(\"material\")]]" in fragment
    assert "ConstantBuffer<MaterialParams> material;" in fragment
    assert "register(" not in fragment
    assert "output.color = material.u_color;" in fragment
    assert "struct MaterialParams" not in phase.stages["vertex"].source


def test_slang_material_layout_sets_shader_contract_before_sidecar_reflection():
    import termin.graphics  # noqa: F401  # Registers TcShader before TcMaterialPhase.shader casts it.

    shader_text = "\n".join([
        "@program SlangWithRuntimeLayout",
        "@language slang",
        "@property SrgbColor tint = SrgbColor(1, 1, 1, 1)",
        "@phase opaque",
        "@stage vertex",
        "struct VertexInput {",
        "    float3 position : POSITION;",
        "    float3 normal : NORMAL;",
        "};",
        "struct VertexOutput { float4 position : SV_Position; };",
        "[shader(\"vertex\")] VertexOutput main(VertexInput input) {",
        "    VertexOutput output;",
        "    output.position = float4(input.position, 1);",
        "    return output;",
        "}",
        "@endstage",
        "@stage fragment",
        "struct FragmentOutput { float4 color : SV_Target0; };",
        "[shader(\"fragment\")] FragmentOutput main() {",
        "    FragmentOutput output;",
        "    output.color = material.tint;",
        "    return output;",
        "}",
        "@endstage",
        "@endphase",
    ])

    material = create_material_from_parsed(parse_shader_text(shader_text))
    shader = material.get_phase(0).shader

    assert shader.material_ubo_entry_count == 1
    assert shader.material_ubo_block_size == 16
    assert shader.find_resource_binding("material") is None
    assert shader.has_contract

    contract = shader.contract
    assert contract["source_kind"] == 4  # TC_SHADER_CONTRACT_SOURCE_DECLARED
    assert "draw_kind" not in contract
    assert {
        input_desc["semantic"]
        for input_desc in contract["vertex_inputs"]
    } == {"position", "normal"}
    assert "material" in {
        resource["name"]
        for resource in contract["resources"]
    }
    material_requirement = next(
        resource
        for resource in contract["resources"]
        if resource["name"] == "material"
    )
    assert material_requirement["kind_name"] == "constant_buffer"
    assert material_requirement["scope_name"] == "material"
    assert material_requirement["size"] == 16
    assert material_requirement["fields"] == [
        {"name": "tint", "type": "SrgbColor", "offset": 0, "size": 16}
    ]

    shader.set_resource_layout([])
    assert shader.find_resource_binding("material") is None
    contract_after_layout_clear = shader.contract
    assert {
        resource["name"]
        for resource in contract_after_layout_clear["resources"]
    } == {
        resource["name"]
        for resource in contract["resources"]
    }
    material_after_layout_clear = next(
        resource
        for resource in contract_after_layout_clear["resources"]
        if resource["name"] == "material"
    )
    assert material_after_layout_clear["fields"] == material_requirement["fields"]


def test_parse_shader_text_rejects_explicit_glsl_shader():
    shader_text = "\n".join([
        "@program GlslWithRuntimeLayout",
        "@language glsl",
        "@property SrgbColor tint = SrgbColor(1, 1, 1, 1)",
        "@phase opaque",
        "@stage vertex",
        "#version 450",
        "layout(location = 0) in vec3 a_position;",
        "void main() { gl_Position = vec4(a_position, 1.0); }",
        "@endstage",
        "@stage fragment",
        "#version 450",
        "layout(location = 0) out vec4 out_color;",
        "void main() { out_color = tint; }",
        "@endstage",
        "@endphase",
    ])

    with pytest.raises(RuntimeError, match="GLSL .shader programs are no longer supported"):
        parse_shader_text(shader_text)


def test_slang_shader_synthesizes_engine_scope_blocks_for_compact_names():
    shader_text = "\n".join([
        "@program SlangEngineScopes",
        "@language slang",
        "@phase opaque",
        "@stage vertex",
        "struct VertexInput { float3 position : POSITION; };",
        "struct VertexOutput { float4 position : SV_Position; };",
        "[shader(\"vertex\")] VertexOutput main(VertexInput input) {",
        "    VertexOutput output;",
        "    float4 world = mul(u_model, float4(input.position, 1.0));",
        "    output.position = mul(u_projection, mul(u_view, world));",
        "    return output;",
        "}",
        "@endstage",
        "@stage fragment",
        "struct FragmentOutput { float4 color : SV_Target0; };",
        "[shader(\"fragment\")] FragmentOutput main() {",
        "    FragmentOutput output;",
        "    output.color = float4(1, 1, 1, 1);",
        "    return output;",
        "}",
        "@endstage",
        "@endphase",
    ])

    program = parse_shader_text(shader_text)
    vertex = program.phases[0].stages["vertex"].source

    assert "import termin_prelude;" in vertex
    assert "[[TerminScope(\"frame\")]]" in vertex
    assert "ConstantBuffer<PerFrame> per_frame;" in vertex
    assert "#define u_view per_frame.u_view" in vertex
    assert "#define u_projection per_frame.u_projection" in vertex
    assert "[[TerminScope(\"draw\")]]" in vertex
    assert "ConstantBuffer<DrawData> draw_data;" in vertex
    assert "#define u_model draw_data._u_model" in vertex
    assert vertex.count("ConstantBuffer<PerFrame> per_frame;") == 1
    assert vertex.count("ConstantBuffer<DrawData> draw_data;") == 1


def test_slang_shader_synthesizes_sampler2d_for_texture_properties():
    shader_text = "\n".join([
        "@program SlangWithTexture",
        "@language slang",
        "@property Texture2D albedo = \"white\" encoding(srgb)",
        "@phase opaque",
        "@stage fragment",
        "[shader(\"fragment\")] float4 main() : SV_Target0 { return albedo.Sample(float2(0)); }",
        "@endstage",
        "@endphase",
    ])

    program = parse_shader_text(shader_text)
    phase = program.phases[0]
    fragment = phase.stages["fragment"].source

    assert phase.uniforms[0].name == "albedo"
    assert phase.uniforms[0].property_type == "Texture"
    assert phase.material_ubo_layout.entries == []
    assert "import termin_prelude;" in fragment
    assert "[[TerminScope(\"material\")]]" in fragment
    assert "Sampler2D albedo;" in fragment
    assert "register(" not in fragment
    assert fragment.index("Sampler2D albedo;") < fragment.index("[shader(\"fragment\")]")


def test_slang_texture_property_does_not_duplicate_existing_sampler2d_declaration():
    shader_text = "\n".join([
        "@program SlangWithTexture",
        "@language slang",
        "@property Texture2D albedo = \"white\" encoding(srgb)",
        "@phase opaque",
        "@stage fragment",
        "Sampler2D albedo;",
        "[shader(\"fragment\")] float4 main(float2 uv : TEXCOORD0) : SV_Target0 { return albedo.Sample(uv); }",
        "@endstage",
        "@endphase",
    ])

    program = parse_shader_text(shader_text)
    fragment = program.phases[0].stages["fragment"].source

    assert fragment.count("Sampler2D albedo;") == 1
    assert fragment.index("Sampler2D albedo;") < fragment.index("[shader(\"fragment\")]")


def test_surface_producer_metadata_parses_and_publishes_to_tc_shader():
    _register_surface_contracts()

    program = parse_shader_text(_surface_shader())
    producer = program.phases[0].surface_producer
    assert producer is not None
    assert producer.contract_id == "termin.surface.standard-pbr"
    assert producer.contract_version == 1
    assert producer.surface_type_name == "TerminStandardSurfaceV1"
    assert producer.evaluator_entry == "evaluate_surface"
    assert "evaluate_surface(FragmentInput input)" in producer.evaluator_source
    assert producer.source_identity.startswith(
        "termin.surface.standard-pbr@1:evaluator-fnv1a64:"
    )
    assert [
        (item.semantic, item.value_type)
        for item in producer.required_fragment_inputs
    ] == [
        ("world_pos", "float3"),
        ("normal_world", "float3"),
    ]
    assert {resource.name for resource in producer.resources} == {
        "material",
        "albedo",
    }

    material = create_material_from_parsed(program)
    shader = material.phases[0].shader
    assert shader.is_executable is False
    assert shader.program_role.name == "SURFACE_PRODUCER"
    runtime = shader.surface_producer
    assert runtime["contract_id"] == "termin.surface.standard-pbr"
    assert runtime["contract_version"] == 1
    assert runtime["surface_type_name"] == "TerminStandardSurfaceV1"
    assert runtime["evaluator_entry"] == "evaluate_surface"
    assert [item["semantic"] for item in runtime["fragment_inputs"]] == [
        "world_pos",
        "normal_world",
    ]
    assert {resource["name"] for resource in runtime["resources"]} == {
        "material",
        "albedo",
    }


def test_surface_producer_accepts_project_owned_exact_contract():
    descriptor = SurfaceContractDescriptor()
    descriptor.key = SurfaceContractKey("game.surface.weathered", 3)
    descriptor.debug_name = "Weathered Surface v3"
    descriptor.surface_type_name = "GameWeatheredSurfaceV3"
    descriptor.interface_source = (
        "struct GameWeatheredSurfaceV3 { float wetness; };"
    )
    descriptor.source_identity = "game-weathered-v3-a"
    assert SurfaceContractRegistry.register_contract(
        descriptor,
        "shader-parser-project-test",
    )
    try:
        program = parse_shader_text(
            "\n".join(
                [
                    "@program project-surface",
                    "@language slang",
                    "@phase opaque",
                    (
                        "@surface contract=game.surface.weathered version=3 "
                        "type=GameWeatheredSurfaceV3 entry=evaluate_weathered"
                    ),
                    "@surfaceInput world_pos float3",
                    "@stage vertex vs_main",
                    "float4 vs_main(float3 position : POSITION) : SV_Position {",
                    "    return float4(position, 1.0);",
                    "}",
                    "@endstage",
                    "@stage fragment",
                    (
                        "GameWeatheredSurfaceV3 "
                        "evaluate_weathered(FragmentInput input) {"
                    ),
                    "    GameWeatheredSurfaceV3 result;",
                    "    result.wetness = input.world_pos.y;",
                    "    return result;",
                    "}",
                    "@endstage",
                    "@endphase",
                ]
            )
        )
        producer = program.phases[0].surface_producer
        assert producer is not None
        assert producer.contract_id == "game.surface.weathered"
        assert producer.contract_version == 3
    finally:
        assert SurfaceContractRegistry.unregister_contract(
            SurfaceContractKey("game.surface.weathered", 3),
            "shader-parser-project-test",
        )


@pytest.mark.parametrize(
    ("shader_text", "message"),
    [
        (
            _surface_shader(contract="missing.surface.contract"),
            "Unknown surface contract",
        ),
        (
            _surface_shader(surface_type="WrongSurfaceType"),
            "Surface contract type mismatch",
        ),
        (
            _surface_shader(evaluator_name="not_the_declared_entry"),
            "Surface evaluator entry",
        ),
    ],
)
def test_surface_producer_rejects_invalid_contract_or_evaluator(
    shader_text: str,
    message: str,
):
    _register_surface_contracts()
    with pytest.raises(RuntimeError, match=message):
        parse_shader_text(shader_text)


def test_surface_evaluator_rejects_engine_uniforms():
    _register_surface_contracts()
    shader_text = _surface_shader().replace(
        "result.normal_world = input.normal_world;",
        (
            "result.normal_world = input.normal_world;\n"
            "    result.emission = mul(u_model, float4(input.world_pos, 1.0)).xyz;"
        ),
    )
    with pytest.raises(
        RuntimeError,
        match="must receive world/pass data through @surfaceInput",
    ):
        parse_shader_text(shader_text)


def test_surface_input_requires_surface_declaration():
    with pytest.raises(RuntimeError, match="must follow @surface"):
        parse_shader_text(
            "\n".join(
                [
                    "@language slang",
                    "@phase opaque",
                    "@surfaceInput world_pos float3",
                    "@endphase",
                ]
            )
        )


def test_final_color_shader_remains_executable_without_surface_metadata():
    program = parse_shader_text(
        "\n".join(
            [
                "@program final-color",
                "@language slang",
                "@phase opaque",
                "@stage vertex vs_main",
                "float4 vs_main(float3 position : POSITION) : SV_Position {",
                "    return float4(position, 1.0);",
                "}",
                "@endstage",
                "@stage fragment fs_main",
                "float4 fs_main() : SV_Target0 { return float4(1.0); }",
                "@endstage",
                "@endphase",
            ]
        )
    )
    assert program.phases[0].surface_producer is None
    material = create_material_from_parsed(program)
    shader = material.phases[0].shader
    assert shader.is_executable is True
    assert shader.program_role.name == "EXECUTABLE"
    assert shader.surface_producer is None
