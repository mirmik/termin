"""
DisplayInputManager — input handling for Display.

SimpleDisplayInputManager — C++ handler with raycast/click support.
BasicDisplayInputManager — C handler for cross-language use (no raycast).

Both route mouse/keyboard events to scene via InputComponents.
"""

from termin._native.render import SimpleDisplayInputManager
from termin._native.render import (
    _simple_input_manager_new,
    _simple_input_manager_free,
    _simple_input_manager_get_input_manager,
)


class BasicDisplayInputManager:
    """
    Basic input manager implemented in C (tc_simple_input_manager).

    Routes input events to scene InputComponents via vtable.
    No raycast/click handling - just dispatches raw events.

    Use this for cross-language scenarios (C#, Rust) or when
    raycast is not needed.
    """

    _ptr: int = 0

    def __init__(self, display_ptr: int):
        """
        Create basic input manager for display.

        Args:
            display_ptr: Pointer to tc_display (from Display.tc_display_ptr)
        """
        self._ptr = _simple_input_manager_new(display_ptr)
        if self._ptr == 0:
            raise RuntimeError("Failed to create BasicDisplayInputManager")

    def __del__(self):
        if self._ptr:
            _simple_input_manager_free(self._ptr)
            self._ptr = 0

    @property
    def tc_input_manager_ptr(self) -> int:
        """Get tc_input_manager pointer for attaching to surface."""
        return _simple_input_manager_get_input_manager(self._ptr)


__all__ = ["SimpleDisplayInputManager", "BasicDisplayInputManager"]
