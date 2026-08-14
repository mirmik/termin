from types import SimpleNamespace

from termin.geombase import LinearColor, SrgbColor, Vec4
from termin.project_build.runtime_package.materials import material_uniforms_to_json


def test_material_uniform_json_preserves_color_values_without_redundant_kind_tags() -> None:
    material = SimpleNamespace(
        uniforms={
            "u_authored": SrgbColor(0.25, 0.5, 0.75, 1.0),
            "u_radiance": LinearColor(2.0, 1.5, 0.5, 0.75),
            "u_numeric": Vec4(0.1, 0.2, 0.3, 0.4),
        }
    )

    encoded = material_uniforms_to_json(material)

    assert encoded == {
        "u_authored": [0.25, 0.5, 0.75, 1.0],
        "u_radiance": [2.0, 1.5, 0.5, 0.75],
        "u_numeric": [0.1, 0.2, 0.3, 0.4],
    }
    assert all(isinstance(value, list) for value in encoded.values())
