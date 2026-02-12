"""
DisplayInputRouter + ViewportInputManager — two-level input handling.

DisplayInputRouter — routes events from display surface to viewport's input manager.
ViewportInputManager — per-viewport scene dispatch (C implementation).
"""

from termin._native.render import DisplayInputRouter
from termin._native.render import (
    _display_input_router_new,
    _display_input_router_free,
    _display_input_router_base,
    _viewport_input_manager_new,
    _viewport_input_manager_free,
)


class BasicDisplayInputManager:
    """
    Basic input manager: DisplayInputRouter + ViewportInputManager per viewport.

    Routes input events from display to viewports, then each viewport
    dispatches to scene InputComponents via vtable.
    """

    _router_ptr: int = 0
    _viewport_managers: list = []

    def __init__(self, display_ptr: int):
        """
        Create router + viewport managers for display.

        Args:
            display_ptr: Pointer to tc_display (from Display.tc_display_ptr)
        """
        self._router_ptr = _display_input_router_new(display_ptr)
        if self._router_ptr == 0:
            raise RuntimeError("Failed to create DisplayInputRouter")
        self._viewport_managers = []

    def __del__(self):
        self._free_viewport_managers()
        if self._router_ptr:
            _display_input_router_free(self._router_ptr)
            self._router_ptr = 0

    def _free_viewport_managers(self):
        for ptr in self._viewport_managers:
            _viewport_input_manager_free(ptr)
        self._viewport_managers = []

    def add_viewport(self, vp_index: int, vp_generation: int):
        """Create and attach viewport input manager for a viewport."""
        ptr = _viewport_input_manager_new(vp_index, vp_generation)
        if ptr:
            self._viewport_managers.append(ptr)

    @property
    def tc_input_manager_ptr(self) -> int:
        """Get tc_input_manager pointer for attaching to surface."""
        return _display_input_router_base(self._router_ptr)


__all__ = ["DisplayInputRouter", "BasicDisplayInputManager"]
