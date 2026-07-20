from pathlib import Path
import gc


def _shader_source(
    color_expr: str,
    property_source: str = "",
    *,
    include_shadow_phase: bool = False,
) -> str:
    shadow_phase = """
@phase shadow
@priority 10
@stage vertex
[shader("vertex")]
float4 main(float3 position : POSITION) : SV_Position
{
    return float4(position, 1.0);
}
@endstage
@stage fragment
[shader("fragment")]
float4 main() : SV_Target0
{
    return float4(1.0);
}
@endstage
@endphase
""" if include_shadow_phase else ""
    return f"""@program HotReload
@language slang
{property_source}

@phase opaque
@priority 0

@stage vertex
struct VertexInput
{{
    float3 position : POSITION;
}};

struct VertexOutput
{{
    float4 position : SV_Position;
}};

[shader("vertex")]
VertexOutput main(VertexInput input)
{{
    VertexOutput output;
    output.position = float4(input.position, 1.0);
    return output;
}}
@endstage

@stage fragment
struct FragmentInput
{{
    float4 screen_pos : SV_Position;
}};

struct FragmentOutput
{{
    float4 color : SV_Target0;
}};

[shader("fragment")]
FragmentOutput main(FragmentInput input)
{{
    FragmentOutput output;
    output.color = {color_expr};
    return output;
}}
@endstage
@endphase
{shadow_phase}
"""


def test_shader_runtime_reload_updates_existing_phase_tc_shader(tmp_path: Path) -> None:
    import tgfx
    from termin.default_assets.render.shader_asset import make_phase_uuid
    from termin.default_assets.render.shader_plugin import ShaderImportPlugin
    from termin.default_assets.resource_manager import DefaultResourceManager

    DefaultResourceManager._reset_for_testing()
    rm = DefaultResourceManager.instance()
    plugin = ShaderImportPlugin()

    shader_path = tmp_path / "HotReload.shader"
    shader_path.write_text(_shader_source("float4(1.0, 0.0, 0.0, 1.0)"), encoding="utf-8")
    shader_path.with_suffix(".shader.meta").write_text(
        '{"uuid": "hot-reload-shader"}\n',
        encoding="utf-8",
    )

    result = plugin.preload(str(shader_path))
    assert result is not None
    rm.register_file(result)
    program = rm.get_shader("HotReload")
    assert program is not None
    assert program.uuid == "hot-reload-shader"
    old_program_version = program.version

    from termin.default_assets.render.material_asset import MaterialAsset

    material_path = tmp_path / "HotReload.material"
    material_path.write_text(
        '{"uuid": "hot-reload-material", "shader": "HotReload", '
        '"shader_uuid": "hot-reload-shader"}\n',
        encoding="utf-8",
    )
    material_asset = MaterialAsset.from_file(material_path, name="HotReloadMaterial")
    rm.register_material_asset("HotReloadMaterial", material_asset)
    material = material_asset.material
    assert material is not None
    assert material.shader_program_version == old_program_version

    phase_uuid = make_phase_uuid("hot-reload-shader", "opaque")
    tc_shader = tgfx.TcShader.from_uuid(phase_uuid)
    assert tc_shader.is_valid
    old_version = tc_shader.version
    old_hash = tc_shader.source_hash
    assert "float4(1.0, 0.0, 0.0, 1.0)" in tc_shader.fragment_source

    shader_path.write_text(_shader_source("float4(0.0, 1.0, 0.0, 1.0)"), encoding="utf-8")
    reload_result = plugin.preload(str(shader_path))
    assert reload_result is not None
    rm.reload_file(reload_result)

    reloaded = tgfx.TcShader.from_uuid(phase_uuid)
    assert reloaded.is_valid
    assert reloaded.uuid == phase_uuid
    assert reloaded.version > old_version
    assert reloaded.source_hash != old_hash
    assert "float4(0.0, 1.0, 0.0, 1.0)" in reloaded.fragment_source
    same_program = rm.get_shader("HotReload")
    assert same_program is not None
    assert same_program.uuid == program.uuid
    assert same_program.version > old_program_version
    assert rm.get_shader_asset("HotReload").program.uuid == program.uuid
    assert material.shader_program_version == same_program.version

    shader_path.write_text(
        _shader_source(
            "float4(0.0, 0.0, 1.0, 1.0)",
            "@property Float u_factor = 0.25",
        ),
        encoding="utf-8",
    )
    interface_result = plugin.preload(str(shader_path))
    assert interface_result is not None
    rm.reload_file(interface_result)
    after_interface_change = rm.get_shader("HotReload")
    assert after_interface_change is not None
    assert material.shader_program_version == after_interface_change.version
    assert material.default_phase().uniforms["u_factor"] == 0.25

    shader_path.write_text(
        _shader_source(
            "float4(0.0, 0.0, 1.0, 1.0)",
            "@property Float u_factor = 0.25",
            include_shadow_phase=True,
        ),
        encoding="utf-8",
    )
    phase_add_result = plugin.preload(str(shader_path))
    assert phase_add_result is not None
    rm.reload_file(phase_add_result)
    with_shadow = rm.get_shader("HotReload")
    assert with_shadow is not None
    shadow_uuid = make_phase_uuid("hot-reload-shader", "shadow")
    assert with_shadow.find_phase("shadow")["shader"].uuid == shadow_uuid
    shadow_shader = tgfx.TcShader.from_uuid(shadow_uuid)
    assert shadow_shader.is_valid

    shader_path.write_text(
        _shader_source(
            "float4(0.0, 0.0, 1.0, 1.0)",
            "@property Float u_factor = 0.25",
        ),
        encoding="utf-8",
    )
    phase_remove_result = plugin.preload(str(shader_path))
    assert phase_remove_result is not None
    rm.reload_file(phase_remove_result)
    without_shadow = rm.get_shader("HotReload")
    assert without_shadow is not None
    assert without_shadow.find_phase("shadow") is None
    assert shadow_shader.is_valid

    published_version = without_shadow.version
    published_hash = tgfx.TcShader.from_uuid(phase_uuid).source_hash
    shader_path.write_text("@program Broken\n@language slang\n", encoding="utf-8")
    failed_result = plugin.preload(str(shader_path))
    assert failed_result is not None
    rm.reload_file(failed_result)

    after_failure = rm.get_shader("HotReload")
    assert after_failure is not None
    assert after_failure.version == published_version
    assert tgfx.TcShader.from_uuid(phase_uuid).source_hash == published_hash


def test_shader_asset_round_trips_and_applies_matrix_defaults(tmp_path: Path) -> None:
    from termin.default_assets.render.material_asset import MaterialAsset
    from termin.default_assets.render.shader_plugin import ShaderImportPlugin
    from termin.default_assets.resource_manager import DefaultResourceManager
    from termin.geombase import Mat44f

    DefaultResourceManager._reset_for_testing()
    rm = DefaultResourceManager.instance()

    shader_path = tmp_path / "HotReload.shader"
    shader_path.write_text(
        _shader_source(
            "float4(1.0, 1.0, 1.0, 1.0)",
            "@property Mat4 u_transform\n"
            "@property Vec2 u_texel_size = Vec2(0.25, 0.5)",
        ),
        encoding="utf-8",
    )
    shader_path.with_suffix(".shader.meta").write_text(
        '{"uuid": "typed-default-shader"}\n',
        encoding="utf-8",
    )

    result = ShaderImportPlugin().preload(str(shader_path))
    assert result is not None
    rm.register_file(result)

    program = rm.get_shader("HotReload")
    assert program is not None
    properties = {prop["name"]: prop for prop in program.properties}
    assert properties["u_transform"]["default"] == (
        1.0, 0.0, 0.0, 0.0,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        0.0, 0.0, 0.0, 1.0,
    )
    assert properties["u_texel_size"]["default"] == (0.25, 0.5)

    material_path = tmp_path / "HotReload.material"
    material_path.write_text(
        '{"uuid": "typed-default-material", "shader": "HotReload", '
        '"shader_uuid": "typed-default-shader"}\n',
        encoding="utf-8",
    )
    material = MaterialAsset.from_file(material_path, name="TypedDefaultMaterial").material
    assert material is not None
    uniforms = material.default_phase().uniforms

    matrix = uniforms["u_transform"]
    assert isinstance(matrix, Mat44f)
    for column in range(4):
        for row in range(4):
            assert matrix[column, row] == (1.0 if column == row else 0.0)
    assert uniforms["u_texel_size"] == (0.25, 0.5)


def test_shader_asset_releases_program_without_invalidating_live_handles(tmp_path: Path) -> None:
    import tgfx
    from termin.default_assets.render.shader_plugin import ShaderImportPlugin
    from termin.default_assets.resource_manager import DefaultResourceManager

    DefaultResourceManager._reset_for_testing()
    rm = DefaultResourceManager.instance()
    shader_path = tmp_path / "Lifetime.shader"
    shader_path.write_text(_shader_source("float4(1.0, 1.0, 1.0, 1.0)"), encoding="utf-8")
    shader_path.with_suffix(".shader.meta").write_text(
        '{"uuid": "shader-lifetime-program"}\n', encoding="utf-8"
    )

    result = ShaderImportPlugin().preload(str(shader_path))
    assert result is not None
    rm.register_file(result)
    external = rm.get_shader("Lifetime")
    assert external is not None and external.is_valid

    removed = rm.unregister_runtime_asset_by_uuid("shader", external.uuid)
    assert removed is not None
    del removed
    gc.collect()
    assert external.is_valid
    assert tgfx.TcShaderProgram.find("shader-lifetime-program").is_valid

    del external
    gc.collect()
    assert not tgfx.TcShaderProgram.find("shader-lifetime-program").is_valid
