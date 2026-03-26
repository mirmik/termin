from termin.scene import PythonComponent
from termin.input._input_native import install_input_vtable


class InputComponent(PythonComponent):
    """Component capable of handling input events."""

    is_input_handler: bool = True

    def __init__(self, enabled: bool = True, active_in_editor: bool = False):
        super().__init__(enabled=enabled)
        self.active_in_editor = active_in_editor
        install_input_vtable(self._tc.c_ptr_int())

    def on_mouse_button(self, event):
        pass

    def on_mouse_move(self, event):
        pass

    def on_scroll(self, event):
        pass

    def on_key(self, event):
        pass


__all__ = ["InputComponent"]
