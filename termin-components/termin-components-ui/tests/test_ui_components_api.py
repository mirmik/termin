from termin.input import InputComponent, MouseButtonEvent
from termin.input._input_native import is_input_handler, is_overlay_input_handler
from termin.ui_components import UIComponent


def test_ui_component_is_exported_from_canonical_package() -> None:
    assert UIComponent.__name__ == "UIComponent"


def test_ui_component_uses_overlay_input_category() -> None:
    ui = UIComponent()
    normal = InputComponent()

    assert UIComponent.input_category == "overlay"
    assert not is_input_handler(ui._tc.c_ptr_int())
    assert is_overlay_input_handler(ui._tc.c_ptr_int())
    assert is_input_handler(normal._tc.c_ptr_int())
    assert not is_overlay_input_handler(normal._tc.c_ptr_int())


def test_mouse_button_event_exposes_handled_flag() -> None:
    event = MouseButtonEvent()

    assert event.handled is False
    event.handled = True
    assert event.handled is True
    assert "handled=True" in repr(event)
