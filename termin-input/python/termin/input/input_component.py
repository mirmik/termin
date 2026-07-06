from termin.scene import PythonComponent, ComponentRegistry
from tcbase import log
from termin.input._input_native import (
    install_input_vtable,
    install_overlay_input_vtable,
    input_capability_id,
    overlay_input_capability_id,
)


class InputComponent(PythonComponent):
    """Component capable of handling input events."""

    is_input_handler: bool = True
    input_category: str = "normal"

    def __init__(self, enabled: bool = True, active_in_editor: bool = False):
        super().__init__(enabled=enabled)
        self.active_in_editor = active_in_editor
        if self.input_category == "overlay":
            install_overlay_input_vtable(self._tc.c_ptr_int())
        elif self.input_category == "normal":
            install_input_vtable(self._tc.c_ptr_int())
        else:
            message = (
                f"[InputComponent] unsupported input_category={self.input_category!r} "
                f"on {type(self).__name__}"
            )
            log.error(message)
            raise ValueError(message)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.input_category == "overlay":
            ComponentRegistry.set_capability(cls.__name__, overlay_input_capability_id(), True)
        elif cls.input_category == "normal":
            ComponentRegistry.set_capability(cls.__name__, input_capability_id(), True)
        else:
            message = (
                f"[InputComponent] unsupported input_category={cls.input_category!r} "
                f"on {cls.__name__}"
            )
            log.error(message)
            raise ValueError(message)

    def on_mouse_button(self, event):
        pass

    def on_mouse_move(self, event):
        pass

    def on_scroll(self, event):
        pass

    def on_key(self, event):
        pass


__all__ = ["InputComponent"]
