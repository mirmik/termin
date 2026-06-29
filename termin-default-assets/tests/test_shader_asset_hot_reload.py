from pathlib import Path


def _shader_source(color_expr: str) -> str:
    return f"""@program HotReload
@language slang

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
    assert rm.shaders["HotReload"] is rm.get_shader_asset("HotReload").program
