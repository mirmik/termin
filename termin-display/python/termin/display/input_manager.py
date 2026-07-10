"""
Display-level input routing helpers.

DisplayInputRouter routes display surface events to viewport input managers.
BasicDisplayInputManager owns a router plus per-viewport managers for simple
runtime/player input dispatch.
"""

from __future__ import annotations

from termin.display._display_native import (
    DisplayInputRouter,
    _display_input_router_base,
    _display_input_router_free,
    _display_input_router_new,
    _viewport_get_input_manager,
    _viewport_input_manager_free,
    _viewport_input_manager_new,
)


class BasicDisplayInputManager:
    """
    Basic input manager: DisplayInputRouter + ViewportInputManager per viewport.

    Routes input events from display to viewports, then each viewport dispatches
    to scene InputComponents through the native input-manager vtable.
    """

    def __init__(self, display_ptr: int):
        self._router_ptr = 0
        self._viewport_managers: dict[tuple[int, int], int] = {}

        self._router_ptr = _display_input_router_new(display_ptr)
        if self._router_ptr == 0:
            raise RuntimeError("Failed to create DisplayInputRouter")

    def __del__(self):
        self.close()

    def close(self) -> None:
        """Release all native input objects owned by this manager."""

        self._free_viewport_managers()
        if self._router_ptr:
            _display_input_router_free(self._router_ptr)
            self._router_ptr = 0

    def _free_viewport_managers(self) -> None:
        for ptr in self._viewport_managers.values():
            _viewport_input_manager_free(ptr)
        self._viewport_managers.clear()

    def add_viewport(self, vp_index: int, vp_generation: int) -> bool:
        """Create and attach a viewport input manager for a viewport."""
        key = (vp_index, vp_generation)
        if key in self._viewport_managers:
            return True
        existing = _viewport_get_input_manager(vp_index, vp_generation)
        if existing:
            return True

        ptr = _viewport_input_manager_new(vp_index, vp_generation)
        if ptr:
            self._viewport_managers[key] = ptr
            return True
        return False

    def remove_viewport(self, vp_index: int, vp_generation: int) -> bool:
        """Release a per-viewport manager previously created by this owner."""

        ptr = self._viewport_managers.pop((vp_index, vp_generation), None)
        if ptr is None:
            return False
        _viewport_input_manager_free(ptr)
        return True

    @property
    def tc_input_manager_ptr(self) -> int:
        """Return the tc_input_manager pointer for attaching to a surface."""
        if not self._router_ptr:
            raise RuntimeError("BasicDisplayInputManager is closed")
        return _display_input_router_base(self._router_ptr)


__all__ = ["DisplayInputRouter", "BasicDisplayInputManager"]
