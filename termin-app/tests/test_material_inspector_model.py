from dataclasses import dataclass

import pytest

from termin.editor_core.material_inspector_model import (
    MaterialInspectorController,
    MaterialTextureValue,
    material_vector,
)


@dataclass
class _Property:
    name: str
    label: str
    property_type: str
    default: object
    range_min: float | None = None
    range_max: float | None = None


class _Phase:
    def __init__(self) -> None:
        self.params = {}

    def set_param(self, name, value) -> None:
        self.params[name] = value


class _Texture:
    is_valid = True


class _Material:
    def __init__(self) -> None:
        self.name = "Probe"
        self.uuid = "material-uuid"
        self.shader_name = "lit"
        self.phases = [_Phase(), _Phase()]
        self.uniforms = {
            "enabled": True,
            "roughness": 0.25,
            "count": 2,
            "direction": (1.0, 2.0, 3.0),
            "tint": (1.5, 0.5, -1.0, 0.75),
        }
        self.textures = {"albedo": _Texture()}
        self.texture_assignments = []

    def set_texture(self, name, texture) -> int:
        self.texture_assignments.append((name, texture))
        return len(self.phases)


class _Program:
    phases = [object()]
    material_properties = [
        _Property("enabled", "Enabled", "Bool", False),
        _Property("roughness", "Roughness", "Float", 0.5, 0.0, 1.0),
        _Property("count", "Count", "Int", 1, 0.0, 8.0),
        _Property("direction", "Direction", "Vec3", (0.0, 0.0, 1.0)),
        _Property("tint", "Tint", "Color", (1.0, 1.0, 1.0, 1.0)),
        _Property("albedo", "Albedo", "Texture", "white"),
    ]


class _Resources:
    def __init__(self) -> None:
        self.texture = _Texture()

    def list_shader_names(self):
        return ["lit", "unlit"]

    def get_shader(self, name):
        return _Program() if name == "lit" else None

    def find_texture_name(self, texture):
        return "brick" if texture is not None else None

    def get_texture_handle(self, name):
        return self.texture if name == "brick" else None

    def find_material_name(self, _material):
        return None


def test_material_inspector_snapshot_and_property_edits_share_one_controller():
    material = _Material()
    changes = []
    controller = MaterialInspectorController(_Resources(), changed=lambda: changes.append(True))

    snapshot = controller.set_target(material)

    assert snapshot.name == "Probe"
    assert snapshot.shader_choices == ("lit", "unlit")
    assert snapshot.phase_count == 2
    assert snapshot.properties[1].minimum == 0.0
    assert snapshot.properties[1].maximum == 1.0
    assert snapshot.properties[4].value == pytest.approx((1.0, 0.5, 0.0, 0.75))
    assert snapshot.properties[5].texture == MaterialTextureValue("file", "brick", "white")

    controller.set_property("roughness", 0.75)
    controller.set_property("count", 4.9)
    controller.set_property("direction", (4.0, 5.0, 6.0))
    controller.set_property("tint", (0.1, 0.2, 0.3))

    for phase in material.phases:
        assert phase.params["roughness"] == pytest.approx(0.75)
        assert phase.params["count"] == 4
        assert tuple(phase.params["direction"]) == pytest.approx((4.0, 5.0, 6.0))
        assert tuple(phase.params["tint"]) == pytest.approx((0.1, 0.2, 0.3, 1.0))
    assert len(changes) == 4


def test_material_inspector_file_texture_and_name_edits():
    material = _Material()
    resources = _Resources()
    controller = MaterialInspectorController(resources)
    controller.set_target(material)

    controller.set_name(" Renamed ")
    controller.set_texture("albedo", "file", "brick")

    assert material.name == "Renamed"
    assert material.texture_assignments == [("albedo", resources.texture)]


def test_material_vector_padding_and_validation():
    assert material_vector(None, 3) == (0.0, 0.0, 0.0)
    assert material_vector((0.25, 0.5, 0.75), 4, color=True) == (
        0.25,
        0.5,
        0.75,
        1.0,
    )
    with pytest.raises(ValueError, match="not iterable"):
        material_vector(object(), 3)
