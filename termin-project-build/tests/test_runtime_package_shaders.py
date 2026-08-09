from types import SimpleNamespace

import pytest
from termin.geombase import SrgbColor

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
            {
                "name": "u_tint",
                "property_type": "SrgbColor",
                "expected_encoding": None,
                "default": SrgbColor(0.25, 0.5, 0.75, 1.0),
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
    assert spec["properties"][3]["property_type"] == "SrgbColor"
    assert spec["properties"][3]["default"] == [0.25, 0.5, 0.75, 1.0]


def test_shader_program_spec_rejects_legacy_color_kind() -> None:
    program = SimpleNamespace(
        is_valid=True,
        uuid="legacy-program",
        name="Legacy",
        source_path="Assets/Legacy.shader",
        language="slang",
        features=0,
        properties=[
            {
                "name": "u_color",
                "property_type": "Color",
                "default": [1.0, 1.0, 1.0, 1.0],
                "range_min": None,
                "range_max": None,
            }
        ],
        phases=[],
    )

    with pytest.raises(ValueError, match="SrgbColor.*LinearColor"):
        shader_program_to_spec(program)
