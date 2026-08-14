"""
Display-level input routing helpers.

The display owns its stable router. BasicDisplayInputManager only owns the
per-viewport managers used for simple runtime/player scene dispatch.
"""

from __future__ import annotations

from termin.display._display_native import (
    _display_get_input_manager,
    _viewport_get_input_manager,
    _viewport_input_manager_free,
    _viewport_input_manager_new,
)


class BasicDisplayInputManager:
    """
    Basic input manager: display endpoint + ViewportInputManager per viewport.

    Routes input events from display to viewports, then each viewport dispatches
    to scene InputComponents through the native input-manager vtable.
    """

    def __init__(self, display_handle: tuple[int, int]):
        self._display_handle: tuple[int, int] | None = display_handle
        self._viewport_managers: dict[tuple[int, int], int] = {}
        if _display_get_input_manager(*display_handle) == 0:
            raise RuntimeError("Display input endpoint is unavailable")

    def __del__(self):
        self.close()

    def close(self) -> None:
        """Release all native input objects owned by this manager."""

        self._free_viewport_managers()
        self._display_handle = None

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
        if self._display_handle is None:
            raise RuntimeError("BasicDisplayInputManager is closed")
        endpoint = _display_get_input_manager(*self._display_handle)
        if endpoint == 0:
            raise RuntimeError("Display input endpoint is unavailable")
        return endpoint


__all__ = ["BasicDisplayInputManager"]
