from termin.materials import TcMaterial


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
