from termin.input import INPUT_SOURCE_EDITOR, INPUT_SOURCE_RUNTIME, InputComponent, MouseButtonEvent
from termin.input._input_native import accepts_input_source, is_input_handler
from termin.ui_components import UIComponent


def test_ui_component_is_exported_from_canonical_package() -> None:
    assert UIComponent.__name__ == "UIComponent"


def test_ui_component_uses_high_input_priority() -> None:
    ui = UIComponent()
    normal = InputComponent()

    assert is_input_handler(ui._tc.c_ptr_int())
    assert is_input_handler(normal._tc.c_ptr_int())
    assert ui.input_priority > normal.input_priority
    assert ui.input_priority == ui.priority


def test_input_component_defaults_to_runtime_source_only() -> None:
    component = InputComponent()
    c_ptr = component._tc.c_ptr_int()

    assert component.input_source_mask == INPUT_SOURCE_RUNTIME
    assert accepts_input_source(c_ptr, INPUT_SOURCE_RUNTIME)
    assert not accepts_input_source(c_ptr, INPUT_SOURCE_EDITOR)


def test_ui_component_defaults_to_runtime_source_only() -> None:
    ui = UIComponent()
    c_ptr = ui._tc.c_ptr_int()

    assert ui.input_source_mask == INPUT_SOURCE_RUNTIME
    assert accepts_input_source(c_ptr, INPUT_SOURCE_RUNTIME)
    assert not accepts_input_source(c_ptr, INPUT_SOURCE_EDITOR)


def test_ui_priority_updates_input_priority() -> None:
    ui = UIComponent(priority=7)

    assert ui.priority == 7
    assert ui.input_priority == 7
    ui.priority = 42
    assert ui.input_priority == 42


def test_mouse_button_event_exposes_handled_flag() -> None:
    event = MouseButtonEvent()

    assert event.handled is False
    assert event.source == INPUT_SOURCE_RUNTIME
    event.handled = True
    event.source = INPUT_SOURCE_EDITOR
    assert event.handled is True
    assert event.source == INPUT_SOURCE_EDITOR
    assert "source=" in repr(event)
    assert "handled=True" in repr(event)
