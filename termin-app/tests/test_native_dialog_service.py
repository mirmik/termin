from __future__ import annotations
from termin.gui_native import tc_ui_document_create, tc_ui_document_destroy

import pytest

from tcbase import MouseButton
from termin.editor_native.dialog_service import NativeDialogService
from termin.editor_native.metrics import EDITOR_UI_METRICS
from termin.gui_native import (
    KeyCode,
    KeyEvent,
    KeyEventType,
    PointerEvent,
    PointerEventType,
    Rect,
)


def _key(key: KeyCode) -> KeyEvent:
    event = KeyEvent()
    event.type = KeyEventType.Down
    event.key = key
    return event


def test_native_dialog_service_delivers_input_and_releases_dialog() -> None:
    document = tc_ui_document_create()
    renders: list[bool] = []
    service = NativeDialogService(
        document,
        viewport=lambda: Rect(0.0, 0.0, 640.0, 480.0),
        request_render=lambda: renders.append(True),
    )
    values: list[str | None] = []

    service.show_input("Rename", "Name", "entity", values.append)
    assert service.active_count == 1
    assert document.dispatch_key_event(_key(KeyCode.Enter))
    assert values == ["entity"]
    assert service.active_count == 0
    assert document.live_widget_count == 0
    assert len(renders) == 2
    tc_ui_document_destroy(document)


def test_native_dialog_service_maps_choice_cancel_to_none() -> None:
    document = tc_ui_document_create()
    service = NativeDialogService(
        document,
        viewport=lambda: Rect(0.0, 0.0, 640.0, 480.0),
        request_render=lambda: None,
    )
    values: list[str | None] = []

    service.show_choice(
        "Delete",
        "Delete children?",
        ["Delete", "Cancel"],
        values.append,
        default="Delete",
        cancel="Cancel",
    )
    assert document.dispatch_key_event(_key(KeyCode.Escape))
    assert values == [None]
    assert service.active_count == 0
    assert document.live_widget_count == 0
    tc_ui_document_destroy(document)


def test_native_dialog_service_delivers_color_and_releases_dialog() -> None:
    document = tc_ui_document_create()
    service = NativeDialogService(
        document,
        viewport=lambda: Rect(0.0, 0.0, 640.0, 480.0),
        request_render=lambda: None,
    )
    values: list[tuple[float, float, float, float] | None] = []

    service.show_color((0.1, 0.2, 0.3, 0.4), values.append)
    assert service.active_count == 1
    assert document.dispatch_key_event(_key(KeyCode.Enter))
    assert values == [pytest.approx((0.1, 0.2, 0.3, 0.4))]
    assert service.active_count == 0
    assert document.live_widget_count == 0
    tc_ui_document_destroy(document)


def test_native_dialog_service_registers_and_releases_color_picker() -> None:
    document = tc_ui_document_create()
    registered = []
    released = []
    service = NativeDialogService(
        document,
        viewport=lambda: Rect(0.0, 0.0, 640.0, 480.0),
        request_render=lambda: None,
        register_color_picker=registered.append,
        unregister_color_picker=released.append,
    )

    service.show_color((0.1, 0.2, 0.3, 0.4), lambda _value: None)
    assert len(registered) == 1
    assert registered[0].handle.valid
    assert document.dispatch_key_event(_key(KeyCode.Enter))
    assert released == registered
    assert document.live_widget_count == 0
    tc_ui_document_destroy(document)


def test_native_dialog_service_delivers_color_from_default_button_click() -> None:
    document = tc_ui_document_create()
    service = NativeDialogService(
        document,
        viewport=lambda: Rect(0.0, 0.0, 640.0, 480.0),
        request_render=lambda: None,
    )
    values: list[tuple[float, float, float, float] | None] = []

    service.show_color((0.1, 0.2, 0.3, 0.4), values.append)
    dialog = next(iter(service._active.values()))
    default_button = dialog.widget.children[-2]
    bounds = default_button.bounds
    event = PointerEvent()
    event.button = MouseButton.LEFT.value
    event.x = bounds.x + bounds.width * 0.5
    event.y = bounds.y + bounds.height * 0.5
    event.type = PointerEventType.Down
    assert document.dispatch_pointer_event(event)
    event.type = PointerEventType.Up
    assert document.dispatch_pointer_event(event)

    assert values == [pytest.approx((0.1, 0.2, 0.3, 0.4))]
    assert service.active_count == 0
    assert document.live_widget_count == 0
    tc_ui_document_destroy(document)


def test_native_dialog_service_layer_mask_roundtrip_and_lifetime() -> None:
    document = tc_ui_document_create()
    service = NativeDialogService(
        document,
        viewport=lambda: Rect(0.0, 0.0, 640.0, 480.0),
        request_render=lambda: None,
    )
    values: list[int | None] = []

    service.show_layer_mask(0b101, tuple(f"Layer {index}" for index in range(64)), values.append)
    assert service.active_count == 1
    dialog = next(iter(service._active.values()))
    content = dialog.widget.children[0]
    assert content.children[0].bounds.height == EDITOR_UI_METRICS.field_row
    layer_list = content.children[1].children[0]
    assert layer_list.children[0].bounds.height == EDITOR_UI_METRICS.compact_row
    assert document.live_widget_count > 100
    assert document.dispatch_key_event(_key(KeyCode.Enter))
    assert values == [0b101]
    assert service.active_count == 0
    assert document.live_widget_count == 0
    tc_ui_document_destroy(document)


def test_native_dialog_service_save_file_delivers_path_and_releases_dialog(tmp_path) -> None:
    document = tc_ui_document_create()
    service = NativeDialogService(
        document,
        viewport=lambda: Rect(0.0, 0.0, 800.0, 600.0),
        request_render=lambda: None,
    )
    values: list[str | None] = []

    service.show_save_file(
        "Save Pipeline",
        str(tmp_path),
        "Pipeline | *.pipeline",
        values.append,
        default_name="main.pipeline",
    )
    assert service.active_count == 1
    assert document.dispatch_key_event(_key(KeyCode.Enter))
    assert values == [str(tmp_path / "main.pipeline")]
    assert service.active_count == 0
    assert document.live_widget_count == 0
    tc_ui_document_destroy(document)
