from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from termin.inspect import InspectField
from termin.prefab import property_path as property_path_module
from termin.prefab.property_path import PropertyPath, PropertyPathError
from termin.scene import Entity, PythonComponent


def _read_value(component: "_PrefabPathComponent") -> int:
    return component.value


def _write_value(component: "_PrefabPathComponent", value: Any) -> None:
    component.value = int(value)


class _PrefabPathComponent(PythonComponent):
    inspect_fields = {
        "value": InspectField(
            label="Value",
            kind="int",
            getter=_read_value,
            setter=_write_value,
        ),
    }

    def __init__(self, value: int = 0) -> None:
        super().__init__()
        self.value = value
        self.hidden = 41


@dataclass
class _Entity:
    components: list[Any] = field(default_factory=list)
    name: str = "Entity"


def test_component_path_uses_canonical_type_name_and_inspect_field() -> None:
    component = _PrefabPathComponent(value=3)
    entity = _Entity(components=[component])

    assert PropertyPath.get(entity, "components/_PrefabPathComponent/value") == 3
    assert PropertyPath.set(entity, "components/_PrefabPathComponent/value", 9)
    assert component.value == 9


def test_component_path_works_with_scene_entity_components() -> None:
    component = _PrefabPathComponent(value=3)
    entity = Entity(name="PrefabEntity")
    entity.add_component(component)

    try:
        assert PropertyPath.get(entity, "components/_PrefabPathComponent/value") == 3
        PropertyPath.set_or_raise(entity, "components/_PrefabPathComponent/value", 13)
    finally:
        entity.remove_component(component)

    assert component.value == 13


def test_component_path_still_allows_indexed_components() -> None:
    component = _PrefabPathComponent(value=3)
    entity = _Entity(components=[component])

    assert PropertyPath.get(entity, "components/0/value") == 3
    PropertyPath.set_or_raise(entity, "components/0/value", 11)

    assert component.value == 11


def test_component_path_rejects_existing_attr_outside_inspect_schema() -> None:
    component = _PrefabPathComponent(value=3)
    entity = _Entity(components=[component])

    with pytest.raises(PropertyPathError, match="no inspect field 'hidden'"):
        PropertyPath.set_or_raise(entity, "components/_PrefabPathComponent/hidden", 12)

    assert component.hidden == 41
    assert not PropertyPath.exists(entity, "components/_PrefabPathComponent/hidden")


def test_set_logs_failed_component_path(monkeypatch: pytest.MonkeyPatch) -> None:
    component = _PrefabPathComponent(value=3)
    entity = _Entity(components=[component])
    warnings: list[tuple[str, bool]] = []

    class _Log:
        def warning(self, message: str, exc_info: bool = False) -> None:
            warnings.append((message, exc_info))

    monkeypatch.setattr(property_path_module, "log", _Log())

    assert not PropertyPath.set(entity, "components/RenamedComponent/value", 7)
    assert component.value == 3
    assert warnings == [
        (
            "[PropertyPath] Failed to set 'components/RenamedComponent/value' "
            "on entity 'Entity'",
            True,
        )
    ]
