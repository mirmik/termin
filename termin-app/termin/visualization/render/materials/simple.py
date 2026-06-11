from __future__ import annotations

from termin.materials import TcMaterial

COLOR_SHADER_TEXT = """@program ColorShader
@language slang

@phase opaque
@priority 0
@glDepthTest true
@glDepthMask true
@glCull true

@property Color u_color = Color(1.0, 1.0, 1.0, 1.0)

@stage vertex
struct VertexInput
{
    float3 position : POSITION;
    float3 normal : NORMAL;
};

struct VertexOutput
{
    float4 position : SV_Position;
    float3 normal_world : NORMAL;
};

[shader("vertex")]
VertexOutput main(VertexInput input)
{
    VertexOutput output;
    output.normal_world = mul((float3x3)u_model, input.normal);
    float4 world = mul(u_model, float4(input.position, 1.0));
    output.position = mul(u_projection, mul(u_view, world));
    return output;
}
@endstage

@stage fragment
struct FragmentInput
{
    float3 normal_world : NORMAL;
};

struct FragmentOutput
{
    float4 color : SV_Target0;
};

[shader("fragment")]
FragmentOutput main(FragmentInput input)
{
    FragmentOutput output;
    float3 n = normalize(input.normal_world);
    float ndotl = max(dot(n, float3(0.2, 0.6, 0.5)), 0.0);
    float3 color = material.u_color.rgb * (0.25 + 0.75 * ndotl);
    output.color = float4(color, material.u_color.a);
    return output;
}
@endstage

@endphase
"""


def create_color_material(
    color: tuple[float, float, float, float],
    name: str = "ColorMaterial",
) -> TcMaterial:
    """Create a simple colored material with basic lighting."""
    from termin.materials import create_material_from_parsed, parse_shader_text

    mat = create_material_from_parsed(
        parse_shader_text(COLOR_SHADER_TEXT),
        name=name,
    )

    phase = mat.default_phase()
    if phase is not None:
        phase.set_color(color[0], color[1], color[2], color[3])

    return mat


class ColorMaterial(TcMaterial):
    """Simple colored material with basic lighting. Returns TcMaterial."""

    def __new__(cls, color: tuple[float, float, float, float]) -> TcMaterial:
        return create_color_material(color=color)


UNLIT_SHADER_TEXT = """@program UnlitShader
@language slang

@phase opaque
@priority 0
@glDepthTest true
@glDepthMask true
@glCull true

@property Color u_color = Color(1.0, 1.0, 1.0, 1.0)

@stage vertex
struct VertexInput
{
    float3 position : POSITION;
};

struct VertexOutput
{
    float4 position : SV_Position;
};

[shader("vertex")]
VertexOutput main(VertexInput input)
{
    VertexOutput output;
    float4 world = mul(u_model, float4(input.position, 1.0));
    output.position = mul(u_projection, mul(u_view, world));
    return output;
}
@endstage

@stage fragment
struct FragmentOutput
{
    float4 color : SV_Target0;
};

[shader("fragment")]
FragmentOutput main()
{
    FragmentOutput output;
    output.color = material.u_color;
    return output;
}
@endstage

@endphase
"""


def create_unlit_material(
    color: tuple[float, float, float, float],
    name: str = "UnlitMaterial",
) -> TcMaterial:
    """Create an unlit material (no lighting, just solid color)."""
    from termin.materials import create_material_from_parsed, parse_shader_text

    mat = create_material_from_parsed(
        parse_shader_text(UNLIT_SHADER_TEXT),
        name=name,
    )

    phase = mat.default_phase()
    if phase is not None:
        phase.set_color(color[0], color[1], color[2], color[3])

    return mat


class UnlitMaterial(TcMaterial):
    """Unlit material (no lighting). Returns TcMaterial."""

    def __new__(cls, color: tuple[float, float, float, float], **kwargs) -> TcMaterial:
        return create_unlit_material(color=color)
