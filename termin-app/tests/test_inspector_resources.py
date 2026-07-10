from dataclasses import dataclass

import pytest

from termin.editor_core.inspector_resources import InspectorResourceCatalog


@dataclass
class _Accessors:
    allow_none: bool = True
    create_item: object = None

    def list_items(self):
        return [("first", "uuid-1"), ("second", "uuid-2")]


class _Resources:
    def __init__(self):
        self.accessors = _Accessors(create_item=lambda: ("created", "uuid-3"))

    def get_handle_accessors(self, kind):
        return self.accessors if kind == "tc_texture" else None


def test_inspector_resource_catalog_lists_resolves_and_creates_values():
    catalog = InspectorResourceCatalog(_Resources())
    choices = catalog.choices("tc_texture")

    assert [item.label for item in choices.items] == ["(None)", "first", "second"]
    assert choices.can_create
    assert choices.index_for_value(None) == 0
    assert choices.index_for_value({"uuid": "uuid-2", "name": "stale"}) == 2
    assert choices.index_for_value({"uuid": None, "name": "first"}) == 1
    assert choices.items[1].value == {"uuid": "uuid-1", "name": "first"}
    assert catalog.create("tc_texture").value == {"uuid": "uuid-3", "name": "created"}


def test_inspector_resource_catalog_rejects_unknown_create_kind():
    catalog = InspectorResourceCatalog(_Resources())
    assert catalog.choices("missing") is None
    with pytest.raises(ValueError, match="unknown"):
        catalog.create("missing")
