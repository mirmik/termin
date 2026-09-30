import pytest

from termin.materials import SurfaceContractRegistry, parse_shader_text
from termin.stdlib import stdlib_root


def test_shader_interface_compare_separates_source_from_inputs():
    from termin.default_assets.render.shader_interface import compare_shader_interface
    from termin.graphics import TcShaderProgram

    def canonical(uuid: str, parsed):
        program = TcShaderProgram.declare(uuid, "test")
        program.set_payload(
            name="test",
            language="slang",
            properties=[
                {
                    "name": prop.name,
                    "property_type": prop.property_type,
                    "expected_encoding": prop.expected_encoding,
                    "default": prop.default,
                }
                for prop in parsed.material_properties
            ],
            phases=[{"phase_mark": phase.phase_mark} for phase in parsed.phases],
        )
        return program

    base = parse_shader_text("\n".join([
        "@program test",
        "@language slang",
        "@phase main",
        "@property Texture2D u_input_tex = \"white\" encoding(srgb)",
        "@stage fragment",
        "[shader(\"fragment\")] float4 main(float2 uv : TEXCOORD0) : SV_Target0 { return u_input_tex.Sample(uv); }",
        "@endstage",
        "@endphase",
    ]))
    source_only = parse_shader_text("\n".join([
        "@program test",
        "@language slang",
        "@phase main",
        "@property Texture2D u_input_tex = \"white\" encoding(srgb)",
        "@stage fragment",
        "[shader(\"fragment\")] float4 main(float2 uv : TEXCOORD0) : SV_Target0 { return u_input_tex.Sample(uv * 0.5); }",
        "@endstage",
        "@endphase",
    ]))
    texture_input_added = parse_shader_text("\n".join([
        "@program test",
        "@language slang",
        "@phase main",
        "@property Texture2D u_input_tex = \"white\" encoding(srgb)",
        "@property Texture2D u_depth_texture = \"white\" encoding(linear)",
        "@stage fragment",
        "[shader(\"fragment\")] float4 main(float2 uv : TEXCOORD0) : SV_Target0 { return u_input_tex.Sample(uv) + u_depth_texture.Sample(uv); }",
        "@endstage",
        "@endphase",
    ]))
    numeric_uniform_added = parse_shader_text("\n".join([
        "@program test",
        "@language slang",
        "@phase main",
        "@property Texture2D u_input_tex = \"white\" encoding(srgb)",
        "@property Float u_factor = 1.0",
        "@stage fragment",
        "[shader(\"fragment\")] float4 main(float2 uv : TEXCOORD0) : SV_Target0 { return u_input_tex.Sample(uv) * material.u_factor; }",
        "@endstage",
        "@endphase",
    ]))
    encoding_changed = parse_shader_text("\n".join([
        "@program test",
        "@language slang",
        "@phase main",
        "@property Texture2D u_input_tex = \"white\" encoding(linear)",
        "@stage fragment",
        "[shader(\"fragment\")] float4 main(float2 uv : TEXCOORD0) : SV_Target0 { return u_input_tex.Sample(uv); }",
        "@endstage",
        "@endphase",
    ]))

    base = canonical("shader-interface-base", base)
    source_only = canonical("shader-interface-source", source_only)
    texture_input_added = canonical("shader-interface-texture", texture_input_added)
    numeric_uniform_added = canonical("shader-interface-numeric", numeric_uniform_added)
    encoding_changed = canonical("shader-interface-encoding", encoding_changed)

    assert base.properties[0]["expected_encoding"] == "srgb"

    no_interface_change = compare_shader_interface(base, source_only)
    assert no_interface_change.material_changed is False
    assert no_interface_change.graph_inputs_changed is False

    graph_input_change = compare_shader_interface(base, texture_input_added)
    assert graph_input_change.material_changed is True
    assert graph_input_change.graph_inputs_changed is True

    material_only_change = compare_shader_interface(base, numeric_uniform_added)
    assert material_only_change.material_changed is True
    assert material_only_change.graph_inputs_changed is False

    encoding_change = compare_shader_interface(base, encoding_changed)
    assert encoding_change.material_changed is True
    assert encoding_change.graph_inputs_changed is True


def test_stdlib_blinn_phong_uses_slang_scope_model():
    shader_path = stdlib_root() / "shaders" / "BlinnPhong.shader"
    program = parse_shader_text(shader_path.read_text(encoding="utf-8"))

    phase = program.phases[0]
    properties = {prop.name: prop.property_type for prop in program.material_properties}
    assert properties["u_diffuse_color"] == "SrgbColor"
    assert properties["u_specular_color"] == "SrgbColor"
    vertex = phase.stages["vertex"].source
    assert "[[TerminScope(\"frame\")]]" in vertex
    assert "ConstantBuffer<PerFrame> per_frame;" in vertex
    assert "[[TerminScope(\"draw\")]]" in vertex
    assert "ConstantBuffer<DrawData> draw_data;" in vertex
    assert "#version" not in vertex
    assert "layout(" not in vertex

    fragment = phase.stages["fragment"].source
    assert "import termin_lighting;" in fragment
    assert "import termin_shadows;" in fragment
    assert "[[TerminScope(\"material\")]]" in fragment
    assert "ConstantBuffer<MaterialParams> material;" in fragment
    assert "Sampler2D u_diffuse_texture;" in fragment
    assert "#version" not in fragment
    assert "layout(" not in fragment


def test_string_shader_uuid_produces_canonical_distinct_phase_ids():
    from termin.default_assets.render.shader_asset import make_phase_uuid

    opaque = make_phase_uuid("termin-stdlib-shader-blinn-phong", "opaque")
    shadow = make_phase_uuid("termin-stdlib-shader-blinn-phong", "shadow")
    assert opaque.startswith("shader-phase-")
    assert shadow.startswith("shader-phase-")
    assert opaque != shadow


def test_stdlib_slang_material_creates_slang_tc_shader():
    from termin.graphics import ShaderArtifactPolicy, ShaderLanguage
    from termin.default_assets.render.material_asset import MaterialAsset
    from termin.default_assets.render.shader_asset import ShaderAsset
    from termin.default_assets.resource_manager import DefaultResourceManager

    DefaultResourceManager._reset_for_testing()
    rm = DefaultResourceManager.instance()
    stdlib = stdlib_root()

    shader_asset = ShaderAsset.from_file(
        stdlib / "shaders" / "SlangNormalColor.shader",
        name="SlangNormalColor",
    )
    rm.register_shader_asset("SlangNormalColor", shader_asset)

    material_asset = MaterialAsset.from_file(
        stdlib / "materials" / "SlangNormalColor.material",
        name="SlangNormalColor",
    )
    material = material_asset.material

    assert material is not None
    canonical_program = rm.get_shader("SlangNormalColor")
    assert canonical_program is not None
    assert material.shader_program_uuid == canonical_program.uuid
    assert material.shader_program_version == canonical_program.version
    assert material.phase_count == 1
    phase = material.get_phase(0)
    assert phase is not None
    assert phase.shader.uuid == canonical_program.phases[0]["shader"].uuid
    assert phase.shader.language == ShaderLanguage.SLANG
    assert phase.shader.artifact_policy == ShaderArtifactPolicy.REQUIRED
    assert "import termin_prelude;" in phase.shader.vertex_source
    assert "[[TerminScope(\"frame\")]]" in phase.shader.vertex_source
    assert "[[TerminScope(\"draw\")]]" in phase.shader.vertex_source
    assert "[shader(\"vertex\")]" in phase.shader.vertex_source
    assert "#version" not in phase.shader.vertex_source
    assert "[[vk::" not in phase.shader.vertex_source
    assert "register(" not in phase.shader.vertex_source
    assert "draw_data.u_model" in phase.shader.vertex_source


def test_stdlib_slang_textured_normal_material_uses_texture_property():
    from termin.graphics import ShaderArtifactPolicy, ShaderLanguage
    from termin.default_assets.render.material_asset import MaterialAsset
    from termin.default_assets.render.shader_asset import ShaderAsset
    from termin.default_assets.resource_manager import DefaultResourceManager

    DefaultResourceManager._reset_for_testing()
    rm = DefaultResourceManager.instance()
    stdlib = stdlib_root()

    shader_asset = ShaderAsset.from_file(
        stdlib / "shaders" / "SlangTexturedNormal.shader",
        name="SlangTexturedNormal",
    )
    rm.register_shader_asset("SlangTexturedNormal", shader_asset)

    material_asset = MaterialAsset.from_file(
        stdlib / "materials" / "SlangTexturedNormal.material",
        name="SlangTexturedNormal",
    )
    material = material_asset.material

    assert material is not None
    assert material.phase_count == 1
    phase = material.get_phase(0)
    assert phase is not None
    assert phase.shader.language == ShaderLanguage.SLANG
    assert phase.shader.artifact_policy == ShaderArtifactPolicy.REQUIRED
    assert "register(" not in phase.shader.vertex_source
    assert "register(" not in phase.shader.fragment_source
    assert "import termin_prelude;" in phase.shader.vertex_source
    assert "[[TerminScope(\"frame\")]]" in phase.shader.vertex_source
    assert "[[TerminScope(\"draw\")]]" in phase.shader.vertex_source
    assert "import termin_prelude;" in phase.shader.fragment_source
    assert "ConstantBuffer<MaterialParams> material;" in phase.shader.fragment_source
    assert "[[TerminScope(\"material\")]]" in phase.shader.fragment_source
    assert "material.u_tint_color" in phase.shader.fragment_source
    assert "Sampler2D u_tint_texture;" in phase.shader.fragment_source
    assert "u_tint_texture.Sample(input.uv)" in phase.shader.fragment_source
    assert phase.uniform_count == 1
    assert phase.uniforms["u_tint_color"].r == pytest.approx(1.0)
    assert phase.texture_count == 1


def test_builtin_pbr_shader_uses_slang_scope_model():
    assert SurfaceContractRegistry.register_builtins()
    expected_material_textures = [
        "u_albedo_texture",
        "u_normal_texture",
        "u_metallic_roughness_texture",
        "u_occlusion_texture",
        "u_emissive_texture",
    ]

    stdlib = stdlib_root()
    program = parse_shader_text(
        (stdlib / "shaders" / "CookTorrancePBR.shader").read_text(encoding="utf-8")
    )
    assert program.program == "CookTorrancePBR"
    assert program.language == "slang"
    properties = {prop.name: prop.property_type for prop in program.material_properties}
    assert properties["u_color"] == "SrgbColor"
    assert properties["u_emission_color"] == "SrgbColor"
    assert "lighting_ubo" not in program.features
    assert len(program.phases) == 2

    phase = next(phase for phase in program.phases if phase.phase_mark == "opaque")
    assert phase.phase_mark == "opaque"
    assert phase.available_marks == ["opaque", "transparent"]
    assert not phase.material_ubo_layout.empty()
    assert phase.material_texture_resources == expected_material_textures

    vertex = phase.stages["vertex"].source
    assert "import termin_prelude;" in vertex
    assert "[[TerminScope(\"frame\")]]" in vertex
    assert "ConstantBuffer<PerFrame> per_frame;" in vertex
    assert "[[TerminScope(\"draw\")]]" in vertex
    assert "ConstantBuffer<DrawData> draw_data;" in vertex
    assert "#version" not in vertex
    assert "layout(" not in vertex

    fragment = phase.stages["fragment"].source
    assert "import termin_prelude;" in fragment
    assert "[[TerminScope(\"material\")]]" in fragment
    assert "ConstantBuffer<MaterialParams> material;" in fragment
    assert "Sampler2D u_albedo_texture;" in fragment
    assert "Sampler2D u_normal_texture;" in fragment
    assert "Sampler2D u_metallic_roughness_texture;" in fragment
    assert "import termin_lighting;" not in fragment
    assert "import termin_shadows;" not in fragment
    assert "struct LightingBlock" not in fragment
    assert "struct ShadowBlock" not in fragment
    assert "material.u_metallic" in fragment
    assert "material.u_subsurface" not in fragment
    assert "material.u_diffuse_mul" not in fragment
    assert phase.surface_producer is not None
    assert phase.surface_producer.contract_id == "termin.surface.standard-pbr"
    assert phase.surface_producer.contract_version == 1
    assert phase.surface_producer.evaluator_entry == "evaluate_standard_surface"
    assert "#version" not in fragment
    assert "layout(" not in fragment

    shadow_phase = next(phase for phase in program.phases if phase.phase_mark == "shadow")
    assert shadow_phase.phase_mark == "shadow"
    assert "[[TerminScope(\"frame\")]]" in shadow_phase.stages["vertex"].source
    assert "[[TerminScope(\"draw\")]]" in shadow_phase.stages["vertex"].source


def test_subsurface_pbr_preserves_the_artistic_final_color_model():
    stdlib = stdlib_root()
    program = parse_shader_text(
        (
            stdlib / "shaders" / "CookTorrancePBRSubsurface.shader"
        ).read_text(encoding="utf-8")
    )
    assert program.program == "CookTorrancePBRSubsurface"
    properties = {prop.name: prop.property_type for prop in program.material_properties}
    assert properties["u_color"] == "SrgbColor"
    assert properties["u_emission_color"] == "SrgbColor"
    assert "lighting_ubo" in program.features
    assert len(program.phases) == 2

    phase = next(phase for phase in program.phases if phase.phase_mark == "opaque")
    assert phase.surface_producer is None
    assert {prop.name for prop in program.material_properties} >= {
        "u_subsurface",
        "u_diffuse_mul",
    }
    fragment = phase.stages["fragment"].source
    assert "import termin_lighting;" in fragment
    assert "import termin_shadows;" in fragment
    assert "material.u_subsurface" in fragment
    assert "material.u_diffuse_mul" in fragment
    assert "wrap_diffuse" in fragment
