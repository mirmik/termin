from __future__ import annotations

import pytest

from termin.editor_native.dialog_service import NativeDialogService
from termin.gui_native import Document, KeyCode, KeyEvent, KeyEventType, Rect


def _key(key: KeyCode) -> KeyEvent:
    event = KeyEvent()
    event.type = KeyEventType.Down
    event.key = key
    return event


def test_native_dialog_service_delivers_input_and_releases_dialog() -> None:
    document = Document()
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


def test_native_dialog_service_maps_choice_cancel_to_none() -> None:
    document = Document()
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


def test_native_dialog_service_delivers_color_and_releases_dialog() -> None:
    document = Document()
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


def test_native_dialog_service_layer_mask_roundtrip_and_lifetime() -> None:
    document = Document()
    service = NativeDialogService(
        document,
        viewport=lambda: Rect(0.0, 0.0, 640.0, 480.0),
        request_render=lambda: None,
    )
    values: list[int | None] = []

    service.show_layer_mask(0b101, tuple(f"Layer {index}" for index in range(64)), values.append)
    assert service.active_count == 1
    assert document.live_widget_count > 100
    assert document.dispatch_key_event(_key(KeyCode.Enter))
    assert values == [0b101]
    assert service.active_count == 0
    assert document.live_widget_count == 0
