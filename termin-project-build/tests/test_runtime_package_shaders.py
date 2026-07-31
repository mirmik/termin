from types import SimpleNamespace

from termin.project_build.runtime_package.shaders import shader_program_to_spec


def test_shader_program_spec_preserves_expected_texture_encoding() -> None:
    shader = SimpleNamespace(is_valid=True, uuid="phase-shader")
    state = {
        "polygon_mode": 0,
        "cull": True,
        "depth_test": True,
        "depth_write": True,
        "blend": False,
        "blend_src": 1,
        "blend_dst": 0,
        "depth_func": 0,
    }
    program = SimpleNamespace(
        is_valid=True,
        uuid="program",
        name="Program",
        source_path="Assets/Program.shader",
        language="slang",
        features=0,
        properties=[
            {
                "name": "u_albedo",
                "property_type": "Texture",
                "expected_encoding": "srgb",
                "default": "white",
                "range_min": None,
                "range_max": None,
            },
            {
                "name": "u_normal",
                "property_type": "Texture",
                "expected_encoding": "linear",
                "default": "normal",
                "range_min": None,
                "range_max": None,
            },
            {
                "name": "u_input",
                "property_type": "Texture",
                "expected_encoding": None,
                "default": "white",
                "range_min": None,
                "range_max": None,
            },
        ],
        phases=[
            {
                "phase_mark": "opaque",
                "priority": 0,
                "shader": shader,
                "state": state,
            }
        ],
    )

    spec = shader_program_to_spec(program)

    assert spec["properties"][0]["expected_encoding"] == "srgb"
    assert spec["properties"][1]["expected_encoding"] == "linear"
    assert "expected_encoding" not in spec["properties"][2]
