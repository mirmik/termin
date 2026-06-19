# termin.input - input handling
from termin_nanobind.runtime import preload_sdk_libs

preload_sdk_libs("termin_input")

from termin.input._input_native import (
    XrHand,
    XrInput,
    XrRigInputState,
    xr_hand_from_string,
    xr_hand_to_string,
)
from termin.input.input_component import InputComponent

_DISPLAY_EVENT_EXPORTS = {
    "KeyEvent",
    "MouseButtonEvent",
    "MouseMoveEvent",
    "ScrollEvent",
}


def __getattr__(name: str):
    if name in _DISPLAY_EVENT_EXPORTS:
        from termin.display import _display_native

        value = _display_native.__dict__[name]
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "InputComponent",
    "KeyEvent",
    "MouseButtonEvent",
    "MouseMoveEvent",
    "ScrollEvent",
    "XrHand",
    "XrInput",
    "XrRigInputState",
    "xr_hand_from_string",
    "xr_hand_to_string",
]
