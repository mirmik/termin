from termin.scene import PythonComponent, ComponentRegistry
from termin.input._input_native import (
    get_input_priority,
    install_input_vtable,
    input_capability_id,
    set_input_priority,
)


class InputComponent(PythonComponent):
    """Component capable of handling input events."""

    is_input_handler: bool = True
    default_input_priority: int = 0

    def __init__(self, enabled: bool = True, active_in_editor: bool = False):
        super().__init__(enabled=enabled)
        self.active_in_editor = active_in_editor
        install_input_vtable(self._tc.c_ptr_int())
        self.input_priority = type(self).default_input_priority

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        ComponentRegistry.set_capability(cls.__name__, input_capability_id(), True)

    @property
    def input_priority(self) -> int:
        return get_input_priority(self._tc.c_ptr_int())

    @input_priority.setter
    def input_priority(self, value: int):
        set_input_priority(self._tc.c_ptr_int(), int(value))

    def on_mouse_button(self, event):
        pass

    def on_mouse_move(self, event):
        pass

    def on_scroll(self, event):
        pass

    def on_key(self, event):
        pass


__all__ = ["InputComponent"]
