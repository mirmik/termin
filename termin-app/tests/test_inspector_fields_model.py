from dataclasses import dataclass

import pytest

from termin.editor_core.inspector_fields_model import InspectorFieldsController
from termin.inspect import InspectField


@dataclass
class _Target:
    enabled: bool
    gain: float
    mode: str
    action_count: int = 0


def _fields(_target):
    def set_enabled(target, value):
        target.enabled = bool(value)

    def set_gain(target, value):
        target.gain = float(value)

    def set_mode(target, value):
        target.mode = str(value)

    def reset(target):
        target.action_count += 1

    return {
        "enabled": InspectField(
            path="enabled",
            label="Enabled",
            kind="bool",
            getter=lambda target: target.enabled,
            setter=set_enabled,
        ),
        "gain": InspectField(
            path="gain",
            label="Gain",
            kind="float",
            min=0.0,
            max=2.0,
            getter=lambda target: target.gain,
            setter=set_gain,
        ),
        "mode": InspectField(
            path="mode",
            label="Mode",
            kind="enum",
            choices=[("a", "Mode A"), ("b", "Mode B")],
            getter=lambda target: target.mode,
            setter=set_mode,
        ),
        "reset": InspectField(
            path="reset",
            label="Reset",
            kind="button",
            getter=lambda _target: None,
            action=reset,
        ),
    }


def _metadata(_target):
    return {
        "layout": [
            {"kind": "section", "label": "General"},
            {"kind": "field", "path": "enabled"},
            {"kind": "field", "path": "gain", "visible_if": "enabled"},
            {"kind": "separator"},
        ],
        "fields": {"mode": {"tooltip": "Select mode"}},
    }


def test_inspector_fields_snapshot_layout_mixed_values_and_visibility():
    first = _Target(enabled=False, gain=0.25, mode="a")
    second = _Target(enabled=True, gain=0.75, mode="a")
    controller = InspectorFieldsController(
        field_collector=_fields,
        metadata_collector=_metadata,
    )

    snapshot = controller.set_targets([first, second])

    assert snapshot.target_count == 2
    assert [row.kind for row in snapshot.rows] == [
        "section",
        "field",
        "field",
        "separator",
        "field",
        "field",
    ]
    assert snapshot.field_row("enabled").mixed
    assert snapshot.field_row("gain").mixed
    assert snapshot.field_row("gain").visible
    assert snapshot.field_row("mode").value == "a"
    assert snapshot.field_row("mode").metadata == {"tooltip": "Select mode"}

    second.enabled = False
    assert not controller.refresh().field_row("gain").visible


def test_inspector_fields_apply_action_and_change_handler_contract():
    first = _Target(enabled=True, gain=0.25, mode="a")
    second = _Target(enabled=True, gain=0.75, mode="b")
    changes = []

    def apply_change(field, targets, old_values, value, merge):
        changes.append((field.path, old_values, value, merge))
        for target in targets:
            field.set_value(target, value)

    controller = InspectorFieldsController(
        field_collector=_fields,
        metadata_collector=_metadata,
        change_handler=apply_change,
    )
    controller.set_targets([first, second])

    snapshot = controller.apply_value("gain", 1.5, merge=True)
    assert changes == [("gain", (0.25, 0.75), 1.5, True)]
    assert first.gain == pytest.approx(1.5)
    assert second.gain == pytest.approx(1.5)
    assert not snapshot.field_row("gain").mixed

    controller.invoke_action("reset")
    assert first.action_count == 1
    assert second.action_count == 1


def test_inspector_fields_reject_unknown_and_read_only_edits():
    target = _Target(enabled=True, gain=0.25, mode="a")
    fields = _fields(target)
    fields["mode"].read_only = True
    controller = InspectorFieldsController(
        field_collector=lambda _target: fields,
        metadata_collector=lambda _target: {},
    )
    controller.set_targets([target])

    with pytest.raises(KeyError):
        controller.apply_value("missing", 1)
    with pytest.raises(ValueError, match="read-only"):
        controller.apply_value("mode", "b")
