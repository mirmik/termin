from termin.materials import TcMaterial
import pytest
from termin.graphics import ShaderLanguage


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


def test_add_phase_from_sources_requires_explicit_language() -> None:
    material = TcMaterial.create("ExplicitShaderLanguageMaterial", "")
    with pytest.raises(ValueError, match="requires an explicit shader language"):
        material.add_phase_from_sources(VERTEX, FRAGMENT)


def test_raw_glsl_phase_does_not_infer_engine_resource_layout() -> None:
    import termin.graphics  # noqa: F401  # Registers TcShader before TcMaterialPhase.shader casts it.

    material = TcMaterial.create("RawGlslEngineLayoutMaterial", "")
    phase = material.add_phase_from_sources(
        """
#version 450
layout(location=0) in vec3 in_position;
uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;
void main() {
    gl_Position = u_projection * u_view * u_model * vec4(in_position, 1.0);
}
""",
        FRAGMENT,
        "",
        "RawGlslEngineLayoutShader",
        "opaque",
        0,
        language=ShaderLanguage.GLSL.value,
    )
    assert phase is not None

    shader = phase.shader
    assert shader.resource_binding_count == 0
    assert shader.find_resource_binding("per_frame") is None
    assert shader.find_resource_binding("draw_data") is None


def test_material_copy_survives_registry_growth() -> None:
    source = TcMaterial.create("PoolGrowthSource", "")
    assert source.is_valid
    phase = source.add_phase_from_sources(
        VERTEX,
        FRAGMENT,
        "",
        "PoolGrowthShader",
        "opaque",
        0,
        language=ShaderLanguage.GLSL.value,
    )
    assert phase is not None

    copies = []
    for index in range(160):
        copied = source.copy("")
        assert copied.is_valid
        assert copied.phase_count == 1
        assert copied.get_phase(0).phase_mark == "opaque"
        copied.name = f"PoolGrowthCopy_{index}"
        copies.append(copied)


def test_replace_content_preserves_identity_and_shader_lifetime() -> None:
    destination = TcMaterial.create("LiveMaterial", "")
    identity = destination.uuid
    source = TcMaterial.create("AuthoredMaterial", "")
    source.source_path = "/authored/material.material"
    source.set_shader_program_dependency("authored-program", 4)
    phase = source.add_phase_from_sources(
        VERTEX, FRAGMENT, "", "ReplacementShader", "opaque", 0,
        language=ShaderLanguage.GLSL.value,
    )
    shader_uuid = phase.shader.uuid
    phase.declare_texture("u_input")
    source.set_texture_source("u_input", "render_target", "Panel", "color")
    destination_version = destination.version

    assert destination.replace_content(source)
    assert destination.uuid == identity
    assert destination.name == "AuthoredMaterial"
    assert destination.source_path == source.source_path
    assert destination.shader_program_uuid == "authored-program"
    assert destination.shader_program_version == 4
    assert destination.version > destination_version
    assert destination.phase_count == 1
    assert destination.texture_sources == source.texture_sources

    # The replacement owns its shader reference after the staged owner dies.
    del phase
    del source
    assert destination.get_phase(0).shader.is_valid
    assert destination.get_phase(0).shader.uuid == shader_uuid
    destination.get_phase(0).set_uniform_float("u_probe", 2.0)
    assert destination.uniforms["u_probe"] == pytest.approx(2.0)
    assert destination.replace_content(destination)
    assert not destination.replace_content(TcMaterial())
    assert destination.phase_count == 1
