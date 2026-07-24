from termin.gui_native import tc_ui_document_create, tc_ui_document_destroy
from dataclasses import dataclass

import numpy as np
import pytest

from termin.editor_core.inspector_fields_model import InspectorFieldsController
from termin.editor_core.inspector_resources import InspectorResourceCatalog
from termin.editor_core.material_inspector_model import MaterialInspectorController
from termin.editor_native import build_native_inspector_fields, build_native_material_inspector
from termin.editor_native.material_inspector import NativeMaterialInspector
from termin.inspect import InspectField


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

    def __init__(self) -> None:
        self._image_data = np.array([[[32, 64, 128, 255]]], dtype=np.uint8)


class _Material:
    def __init__(self) -> None:
        self.name = "Inline"
        self.uuid = "inline-uuid"
        self.shader_name = "lit"
        self.phases = [_Phase()]
        self.uniforms = {
            "enabled": True,
            "roughness": 0.25,
            "direction": (1.0, 2.0, 3.0),
            "tint": (1.0, 0.5, 0.25, 1.0),
        }
        self.textures = {"albedo": _Texture()}
        self.assigned_texture = None

    def set_texture(self, name, texture) -> int:
        self.assigned_texture = (name, texture)
        return 1


class _Program:
    phases = [object()]
    properties = [
        {"name": "enabled", "label": "Enabled", "property_type": "Bool", "default": False, "range_min": None, "range_max": None},
        {"name": "roughness", "label": "Roughness", "property_type": "Float", "default": 0.5, "range_min": 0.0, "range_max": 1.0},
        {"name": "direction", "label": "Direction", "property_type": "Vec3", "default": (0.0, 0.0, 1.0), "range_min": None, "range_max": None},
        {"name": "tint", "label": "Tint", "property_type": "Color", "default": (1.0, 1.0, 1.0, 1.0), "range_min": None, "range_max": None},
        {"name": "albedo", "label": "Albedo", "property_type": "Texture", "default": "white", "range_min": None, "range_max": None},
    ]


class _Accessors:
    allow_none = True
    create_item = None

    def list_items(self):
        return [("brick", "texture-uuid")]


class _Resources:
    def __init__(self) -> None:
        self.texture = _Texture()

    def list_shader_names(self):
        return ["lit"]

    def get_shader(self, name):
        return _Program() if name == "lit" else None

    def find_texture_name(self, _texture):
        return "brick"

    def list_texture_names(self):
        return ["brick"]

    def get_texture_handle(self, name):
        return self.texture if name == "brick" else None

    def get_texture(self, name):
        return self.texture if name == "brick" else None

    def find_material_name(self, _material):
        return None

    def get_handle_accessors(self, kind):
        return _Accessors() if kind == "tc_texture" else None


def test_native_material_inspector_projects_and_edits_shared_snapshot():
    document = tc_ui_document_create()
    material = _Material()
    resources = _Resources()
    catalog = InspectorResourceCatalog(resources)
    inspector = build_native_material_inspector(
        document,
        MaterialInspectorController(resources),
        request_render=lambda: None,
        resource_catalog=catalog,
    )

    inspector.set_target(material)

    # Texture rows are taller than ordinary fields, so the enclosing inline
    # inspector must advertise their real extent to the parent scroll area.
    assert inspector.root.preferred_size.height == pytest.approx(292.0)

    assert inspector.controls["name"].text == "Inline"
    assert inspector.controls["shader"].selected_index == 0
    assert inspector.controls["roughness"].value == pytest.approx(0.25)
    inspector.controls["roughness"].value = 0.75
    assert material.phases[0].params["roughness"] == pytest.approx(0.75)

    texture_combo = inspector.controls["albedo"]
    assert texture_combo.selected_text == "brick"
    texture_combo.selected_index = 0
    assert material.assigned_texture is not None
    assert material.assigned_texture[0] == "albedo"
    inspector.controls.clear()
    assert document.destroy_widget_recursive(inspector.root.handle)
    tc_ui_document_destroy(document)


def test_native_material_inspector_registers_and_releases_texture_previews():
    document = tc_ui_document_create()
    material = _Material()
    resources = _Resources()
    registered = []
    released = []

    def register(image, pixels):
        registered.append((image, pixels))
        return lambda: released.append(image)

    inspector = build_native_material_inspector(
        document,
        MaterialInspectorController(resources),
        request_render=lambda: None,
        resource_catalog=InspectorResourceCatalog(resources),
        show_texture_preview=register,
    )
    inspector.set_target(material)
    assert len(registered) == 1
    assert registered[0][1].shape == (1, 1, 4)
    inspector.controls["albedo"].selected_index = 0
    assert released == [registered[0][0]]
    assert len(registered) == 2
    inspector._release_previews()
    assert released == [registered[0][0], registered[1][0]]
    inspector.controls.clear()
    assert document.destroy_widget_recursive(inspector.root.handle)
    tc_ui_document_destroy(document)


def test_inline_material_metadata_uses_native_material_projection():
    @dataclass
    class Target:
        material: object

    target = Target(_Material())
    resources = _Resources()
    controller = InspectorFieldsController(
        field_collector=lambda _target: {
            "material": InspectField(
                path="material",
                label="Material",
                kind="tc_material",
                getter=lambda item: item.material,
            )
        },
        metadata_collector=lambda _target: {"fields": {"material": {"widget": "inline_material"}}},
    )
    document = tc_ui_document_create()
    panel = build_native_inspector_fields(
        document,
        controller,
        request_render=lambda: None,
        resource_catalog=InspectorResourceCatalog(resources),
    )

    panel.set_targets([target])

    inline = panel.field_widgets["material"]
    assert isinstance(inline, NativeMaterialInspector)
    assert inline.controller.material is target.material
    assert inline.controls["roughness"].value == pytest.approx(0.25)
    inline.controls.clear()
    panel.field_widgets.clear()
    assert document.destroy_widget_recursive(panel.root.handle)
    tc_ui_document_destroy(document)
