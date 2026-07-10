"""Toolkit-neutral inspect-field discovery, layout and edit orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

from tcbase import log
from termin.inspect import InspectField


FieldCollector = Callable[[Any], dict[str, InspectField]]
MetadataCollector = Callable[[Any], dict[str, Any]]
FieldChangeHandler = Callable[
    [
        InspectField,
        tuple[Any, ...],
        tuple[Any, ...],
        Any,
        bool,
    ],
    None,
]


@dataclass(frozen=True)
class InspectorFieldRow:
    kind: str
    key: str = ""
    label: str = ""
    field: InspectField | None = None
    metadata: dict[str, Any] | None = None
    value: Any = None
    mixed: bool = False
    visible: bool = True


@dataclass(frozen=True)
class InspectorFieldsSnapshot:
    target_count: int
    rows: tuple[InspectorFieldRow, ...]

    def field_row(self, key: str) -> InspectorFieldRow | None:
        for row in self.rows:
            if row.kind == "field" and row.key == key:
                return row
        return None


def values_equal(left: Any, right: Any) -> bool:
    """Compare inspector values without requiring hashability or scalar equality."""
    try:
        if isinstance(left, (tuple, list)) or isinstance(right, (tuple, list)):
            left_items = list(left) if left is not None else []
            right_items = list(right) if right is not None else []
            if len(left_items) != len(right_items):
                return False
            return all(values_equal(a, b) for a, b in zip(left_items, right_items, strict=True))
        result = left == right
        if isinstance(result, bool):
            return result
        return bool(result)
    except Exception as error:
        log.debug(f"[InspectorFields] value comparison failed: {error}")
        return False


def collect_inspect_fields(target: Any) -> dict[str, InspectField]:
    """Collect inspectable Python or native fields through the public registry API."""
    from termin.inspect import InspectRegistry, TypeBackend
    from termin.scene import TcComponentRef

    registry = InspectRegistry.instance()
    result: dict[str, InspectField] = {}
    if isinstance(target, TcComponentRef):
        type_name = target.type_name
        for info in registry.all_fields(type_name):
            if not info.is_inspectable:
                continue

            def getter(component, path=info.path):
                return component.get_field(path)

            def setter(component, value, path=info.path):
                entity = component.entity
                if entity is not None and entity.valid():
                    component.set_field(path, value, entity.scene)
                else:
                    component.set_field(path, value)

            def action(component, path=info.path):
                component.action_field(path)

            result[info.path] = InspectField(
                path=info.path,
                label=info.label,
                kind=info.kind,
                min=info.min,
                max=info.max,
                step=info.step,
                choices=[(choice.value, choice.label) for choice in info.choices] or None,
                action=action if info.action is not None else None,
                metadata={},
                getter=getter,
                setter=setter,
            )
        return result

    target_class = target.__class__
    type_name = target_class.__name__
    if registry.has_type(type_name) and registry.get_type_backend(type_name) == TypeBackend.Python:
        for base in reversed(target_class.__mro__):
            fields = base.__dict__.get("inspect_fields")
            if not isinstance(fields, dict):
                continue
            for key, field in fields.items():
                if isinstance(field, InspectField) and field.is_inspectable:
                    result[str(key)] = field
        return result

    for info in registry.all_fields(type_name):
        if not info.is_inspectable:
            continue

        def getter(obj, path=info.path):
            return registry.get(obj, path)

        def setter(obj, value, path=info.path):
            registry.set(obj, path, value)

        result[info.path] = InspectField(
            path=info.path,
            label=info.label,
            kind=info.kind,
            min=info.min,
            max=info.max,
            step=info.step,
            choices=[(choice.value, choice.label) for choice in info.choices] or None,
            action=info.action if info.action is not None else None,
            metadata={},
            getter=getter,
            setter=setter,
        )
    return result


def collect_inspector_metadata(target: Any) -> dict[str, Any]:
    from termin.inspect import InspectRegistry
    from termin.scene import TcComponentRef

    type_name = target.type_name if isinstance(target, TcComponentRef) else target.__class__.__name__
    metadata = InspectRegistry.instance().get_type_metadata(type_name)
    inspector = metadata.get("inspector", {}) if isinstance(metadata, dict) else {}
    return inspector if isinstance(inspector, dict) else {}


class InspectorFieldsController:
    """Build immutable field snapshots and apply edits to one or many targets."""

    def __init__(
        self,
        *,
        field_collector: FieldCollector = collect_inspect_fields,
        metadata_collector: MetadataCollector = collect_inspector_metadata,
        change_handler: FieldChangeHandler | None = None,
    ) -> None:
        self._field_collector = field_collector
        self._metadata_collector = metadata_collector
        self._change_handler = change_handler
        self._targets: tuple[Any, ...] = ()
        self._fields: dict[str, InspectField] = {}
        self._metadata: dict[str, Any] = {}
        self._snapshot = InspectorFieldsSnapshot(0, ())

    @property
    def targets(self) -> tuple[Any, ...]:
        return self._targets

    @property
    def snapshot(self) -> InspectorFieldsSnapshot:
        return self._snapshot

    def set_targets(self, targets: Iterable[Any]) -> InspectorFieldsSnapshot:
        self._targets = tuple(target for target in targets if target is not None)
        self._fields = {}
        self._metadata = {}
        if not self._targets:
            self._snapshot = InspectorFieldsSnapshot(0, ())
            return self._snapshot

        try:
            first_fields = self._field_collector(self._targets[0])
            shared_keys = list(first_fields)
            for target in self._targets[1:]:
                candidate = self._field_collector(target)
                shared_keys = [
                    key for key in shared_keys if key in candidate and candidate[key].kind == first_fields[key].kind
                ]
            self._fields = {key: first_fields[key] for key in shared_keys}
            self._metadata = self._metadata_collector(self._targets[0])
            self._snapshot = self._build_snapshot()
        except (ImportError, RuntimeError, ValueError, TypeError) as error:
            log.error(f"[InspectorFields] failed to build field snapshot: {error}")
            self._snapshot = InspectorFieldsSnapshot(len(self._targets), ())
        return self._snapshot

    def refresh(self) -> InspectorFieldsSnapshot:
        self._snapshot = self._build_snapshot() if self._targets else InspectorFieldsSnapshot(0, ())
        return self._snapshot

    def apply_value(self, key: str, value: Any, *, merge: bool = False) -> InspectorFieldsSnapshot:
        field = self._fields.get(key)
        if field is None:
            log.error(f"[InspectorFields] cannot edit unknown field '{key}'")
            raise KeyError(key)
        if field.read_only:
            log.error(f"[InspectorFields] cannot edit read-only field '{key}'")
            raise ValueError(f"field '{key}' is read-only")
        old_values = tuple(field.get_value(target) for target in self._targets)
        if self._change_handler is not None:
            self._change_handler(field, self._targets, old_values, value, merge)
        else:
            for target in self._targets:
                field.set_value(target, value)
        return self.refresh()

    def invoke_action(self, key: str) -> InspectorFieldsSnapshot:
        field = self._fields.get(key)
        if field is None:
            log.error(f"[InspectorFields] cannot invoke unknown field action '{key}'")
            raise KeyError(key)
        if field.action is None:
            log.error(f"[InspectorFields] field '{key}' has no action")
            raise ValueError(f"field '{key}' has no action")
        for target in self._targets:
            field.action(target)
        return self.refresh()

    def _build_snapshot(self) -> InspectorFieldsSnapshot:
        field_metadata = self._metadata.get("fields", {})
        if not isinstance(field_metadata, dict):
            field_metadata = {}
        normalized_metadata = {str(key): value for key, value in field_metadata.items() if isinstance(value, dict)}
        rows: list[InspectorFieldRow] = []
        rendered: set[str] = set()
        layout = self._metadata.get("layout", [])
        if isinstance(layout, list):
            for item in layout:
                if not isinstance(item, dict):
                    continue
                kind = item.get("kind", "field")
                if kind in ("section", "separator"):
                    rows.append(InspectorFieldRow(kind=str(kind), label=str(item.get("label", ""))))
                    continue
                if kind != "field":
                    log.error(f"[InspectorFields] unknown layout item kind '{kind}'")
                    continue
                key = item.get("path")
                if not isinstance(key, str) or key not in self._fields:
                    log.error(f"[InspectorFields] layout references unknown field '{key}'")
                    continue
                metadata = dict(normalized_metadata.get(key, {}))
                metadata.update({name: value for name, value in item.items() if name not in ("kind", "path")})
                rows.append(self._field_row(key, self._fields[key], metadata))
                rendered.add(key)
        for key, field in self._fields.items():
            if key not in rendered:
                rows.append(self._field_row(key, field, normalized_metadata.get(key, {})))
        return InspectorFieldsSnapshot(len(self._targets), tuple(rows))

    def _field_row(
        self,
        key: str,
        field: InspectField,
        metadata: dict[str, Any],
    ) -> InspectorFieldRow:
        values = tuple(field.get_value(target) for target in self._targets)
        mixed = any(not values_equal(values[0], value) for value in values[1:])
        visible = self._field_visible(key, metadata)
        return InspectorFieldRow(
            kind="field",
            key=key,
            label=field.label or key,
            field=field,
            metadata=dict(metadata),
            value=None if mixed else values[0],
            mixed=mixed,
            visible=visible,
        )

    def _field_visible(self, key: str, metadata: dict[str, Any]) -> bool:
        visible_if = metadata.get("visible_if")
        if visible_if is None:
            return True
        if not isinstance(visible_if, str):
            log.error(f"[InspectorFields] visible_if for '{key}' must be a string")
            return True
        controlling = self._fields.get(visible_if)
        if controlling is None:
            log.error(f"[InspectorFields] visible_if references unknown field '{visible_if}'")
            return True
        return any(bool(controlling.get_value(target)) for target in self._targets)


__all__ = [
    "InspectorFieldRow",
    "InspectorFieldsController",
    "InspectorFieldsSnapshot",
    "collect_inspect_fields",
    "collect_inspector_metadata",
    "values_equal",
]
