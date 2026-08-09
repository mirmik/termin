from dataclasses import dataclass
from uuid import uuid4

import pytest

from termin.editor_core.material_inspector_model import (
    MaterialInspectorController,
    MaterialTextureValue,
    material_vector,
)
from termin.geombase import LinearColor, SrgbColor, Vec4


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

    def __init__(self, uuid: str = "brick-uuid") -> None:
        self.uuid = uuid


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
            "tint": SrgbColor(0.5, 0.25, 0.75, 0.75),
        }
        self.textures = {"albedo": _Texture()}
        self.texture_sources = {}
        self.texture_assignments = []

    def set_texture(self, name, texture) -> int:
        self.texture_sources.pop(name, None)
        self.texture_assignments.append((name, texture))
        return len(self.phases)

    def set_texture_source(self, name, kind, source_name, channel) -> None:
        self.texture_sources[name] = {
            "kind": kind,
            "target": source_name,
            "channel": channel,
        }


class _Program:
    phases = [object()]
    properties = [
        {"name": "enabled", "label": "Enabled", "property_type": "Bool", "default": False, "range_min": None, "range_max": None},
        {"name": "roughness", "label": "Roughness", "property_type": "Float", "default": 0.5, "range_min": 0.0, "range_max": 1.0},
        {"name": "count", "label": "Count", "property_type": "Int", "default": 1, "range_min": 0.0, "range_max": 8.0},
        {"name": "direction", "label": "Direction", "property_type": "Vec3", "default": (0.0, 0.0, 1.0), "range_min": None, "range_max": None},
        {"name": "tint", "label": "Tint", "property_type": "SrgbColor", "default": (1.0, 1.0, 1.0, 1.0), "range_min": None, "range_max": None},
        {"name": "albedo", "label": "Albedo", "property_type": "Texture", "default": "white", "expected_encoding": "srgb", "range_min": None, "range_max": None},
    ]


class _Resources:
    def __init__(self) -> None:
        self.texture = _Texture()

    def list_shader_names(self):
        return ["lit", "unlit"]

    def get_shader(self, name):
        return _Program() if name == "lit" else None

    def get_texture_asset_by_uuid(self, uuid):
        if uuid != "brick-uuid":
            return None
        return type("Asset", (), {"name": "brick", "uuid": "brick-uuid"})()

    def get_handle_by_uuid(self, kind, uuid):
        return self.texture if kind == "texture" and uuid == "brick-uuid" else None

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
    assert isinstance(snapshot.properties[4].value, SrgbColor)
    assert tuple(snapshot.properties[4].value) == pytest.approx((0.5, 0.25, 0.75, 0.75))
    assert snapshot.properties[5].texture == MaterialTextureValue(
        "file", "brick-uuid", "white", "srgb"
    )

    controller.set_property("roughness", 0.75)
    controller.set_property("count", 4.9)
    controller.set_property("direction", (4.0, 5.0, 6.0))
    controller.set_property("tint", SrgbColor(0.1, 0.2, 0.3, 1.0))

    for phase in material.phases:
        assert phase.params["roughness"] == pytest.approx(0.75)
        assert phase.params["count"] == 4
        assert tuple(phase.params["direction"]) == pytest.approx((4.0, 5.0, 6.0))
        assert isinstance(phase.params["tint"], SrgbColor)
        assert tuple(phase.params["tint"]) == pytest.approx((0.1, 0.2, 0.3, 1.0))
    assert len(changes) == 4


def test_material_inspector_resolves_native_inspect_projection():
    from termin.materials import TcMaterial

    material = TcMaterial.create("InspectProjection", str(uuid4()))
    controller = MaterialInspectorController(_Resources())

    snapshot = controller.set_target(material.serialize())

    assert controller.material.is_valid
    assert controller.material.uuid == material.uuid
    assert snapshot.has_material
    assert snapshot.name == "InspectProjection"


def test_material_inspector_file_texture_and_name_edits():
    material = _Material()
    resources = _Resources()
    controller = MaterialInspectorController(resources)
    controller.set_target(material)

    controller.set_name(" Renamed ")
    controller.set_texture("albedo", "file", "brick-uuid")

    assert material.name == "Renamed"
    assert material.texture_assignments == [("albedo", resources.texture)]


def test_material_inspector_edits_unconstrained_texture_property():
    material = _Material()
    resources = _Resources()
    program = _Program()
    program.properties = [
        {
            **property_data,
            "expected_encoding": None,
        }
        if property_data["name"] == "albedo"
        else property_data
        for property_data in _Program.properties
    ]
    resources.get_shader = lambda name: program if name == "lit" else None
    controller = MaterialInspectorController(resources)
    controller.set_target(material)

    controller.set_texture("albedo", "file", "brick-uuid")

    assert material.texture_assignments == [("albedo", resources.texture)]


def test_material_inspector_retains_render_target_source_symbolically():
    material = _Material()
    target_texture = _Texture()
    controller = MaterialInspectorController(
        _Resources(),
        render_target_texture=lambda name, channel: target_texture
        if (name, channel) == ("Panel", "color")
        else None,
    )
    controller.set_target(material)

    snapshot = controller.set_texture("albedo", "rt_color", "Panel")

    assert material.texture_sources["albedo"] == {
        "kind": "render_target",
        "target": "Panel",
        "channel": "color",
    }
    assert snapshot.properties[-1].texture == MaterialTextureValue(
        "rt_color", "Panel", "white", "srgb"
    )


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


def test_material_inspector_keeps_linear_color_hdr_and_vec4_distinct():
    material = _Material()
    material.uniforms["radiance"] = LinearColor(4.0, 0.5, -2.0, 0.75)
    material.uniforms["raw"] = Vec4(0.1, 0.2, 0.3, 0.4)
    program = _Program()
    program.properties = [
        {
            "name": "radiance",
            "label": "Radiance",
            "property_type": "LinearColor",
            "default": LinearColor(0.0, 0.0, 0.0, 1.0),
            "range_min": None,
            "range_max": None,
        },
        {
            "name": "raw",
            "label": "Raw",
            "property_type": "Vec4",
            "default": Vec4(0.0, 0.0, 0.0, 1.0),
            "range_min": None,
            "range_max": None,
        },
    ]
    resources = _Resources()
    resources.get_shader = lambda name: program if name == "lit" else None
    controller = MaterialInspectorController(resources)
    snapshot = controller.set_target(material)

    assert isinstance(snapshot.properties[0].value, LinearColor)
    assert tuple(snapshot.properties[0].value) == pytest.approx((4.0, 0.5, -2.0, 0.75))
    assert isinstance(snapshot.properties[1].value, Vec4)
    with pytest.raises(ValueError, match="expects LinearColor"):
        controller.set_property("radiance", SrgbColor(1.0, 0.0, 0.0, 1.0))
    with pytest.raises(ValueError, match="expects Vec4"):
        controller.set_property("raw", SrgbColor(1.0, 0.0, 0.0, 1.0))

    material.uniforms["radiance"] = SrgbColor(1.0, 0.0, 0.0, 1.0)
    with pytest.raises(ValueError, match="expects LinearColor"):
        controller.set_target(material)
