"""Multi-window management on top of BackendWindow.

Generic window-bag + event routing helpers. Knows nothing about UI
frameworks — hosts attach their own UI / renderer state to each
window through ``BackendWindowEntry.host_data`` and drive render via
``entries()``.

Secondary windows share the primary's ``IRenderDevice`` — see the
secondary-window ctor in ``BackendWindow``. There is one device per
process regardless of how many OS windows the host opens.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from termin.display._platform_native import BackendWindow


@dataclass
class BackendWindowEntry:
    """A registered window. ``host_data`` is free-form — the host
    stashes its UI / renderer / input state here."""
    window: BackendWindow
    is_main: bool = False
    host_data: Any = None
    # Called by the manager when the entry is being torn down (either
    # via destroy_window() or handle_window_close() on a secondary).
    # Hosts use this to release UI state, unregister input handlers,
    # etc. The manager invokes it *before* removing the entry and
    # dropping the BackendWindow reference.
    on_destroy: Callable[["BackendWindowEntry"], None] | None = None


class BackendWindowManager:
    """Generic multi-window manager around BackendWindow.

    Hosts subclass or compose this to plug in their UI / rendering
    story. The manager itself has no opinions about UI — it only
    owns the list of ``BackendWindowEntry`` and knows how to find
    an entry by SDL windowID.
    """

    def __init__(self) -> None:
        self._entries: list[BackendWindowEntry] = []

    # ------------------------------------------------------------------
    # Registration / lifecycle
    # ------------------------------------------------------------------

    def register_main(self, window: BackendWindow, *,
                      host_data: Any = None,
                      on_destroy: Callable[[BackendWindowEntry], None] | None = None
                      ) -> BackendWindowEntry:
        """Register the primary window. Must be called before
        create_window()."""
        entry = BackendWindowEntry(
            window=window, is_main=True,
            host_data=host_data, on_destroy=on_destroy)
        self._entries.append(entry)
        return entry

    def create_window(self, title: str, width: int, height: int, *,
                      host_data: Any = None,
                      on_destroy: Callable[[BackendWindowEntry], None] | None = None
                      ) -> BackendWindowEntry:
        """Open a secondary OS window backed by the primary's
        IRenderDevice. Returns the new entry — host fills in
        ``host_data`` (typically a UI + renderer bound to the shared
        graphics context)."""
        main = self.main_entry()
        if main is None:
            raise RuntimeError(
                "BackendWindowManager.create_window called before "
                "register_main: no primary window to share device with.")
        secondary = BackendWindow(title, width, height, main.window)
        entry = BackendWindowEntry(
            window=secondary, is_main=False,
            host_data=host_data, on_destroy=on_destroy)
        self._entries.append(entry)
        return entry

    def destroy_window(self, entry: BackendWindowEntry) -> None:
        """Tear down and remove a registered secondary window.
        No-op for the primary (application lifecycle owns it)."""
        if entry.is_main:
            return
        if entry not in self._entries:
            return
        if entry.on_destroy is not None:
            entry.on_destroy(entry)
        self._entries.remove(entry)
        # BackendWindow dtor (run when the last Python reference drops)
        # tears down the OS window, GL context / Vulkan surface +
        # swapchain. The shared device stays alive in the primary.

    def destroy_all(self) -> None:
        """Tear down all windows, secondary first, then primary.
        The primary's on_destroy still fires so hosts can release
        their state before the process exits."""
        for entry in list(self._entries):
            if not entry.is_main and entry.on_destroy is not None:
                entry.on_destroy(entry)
        for entry in list(self._entries):
            if entry.is_main and entry.on_destroy is not None:
                entry.on_destroy(entry)
        self._entries.clear()

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def entries(self) -> list[BackendWindowEntry]:
        return self._entries

    def main_entry(self) -> BackendWindowEntry | None:
        for e in self._entries:
            if e.is_main:
                return e
        return None

    def get_entry_for_window_id(self, window_id: int) -> BackendWindowEntry | None:
        for e in self._entries:
            if e.window.window_id() == window_id:
                return e
        return None

    def is_main_window_id(self, window_id: int) -> bool:
        e = self.get_entry_for_window_id(window_id)
        return e is not None and e.is_main

    def handle_window_close(self, window_id: int) -> bool:
        """Handle SDL_WINDOWEVENT_CLOSE for a given windowID.

        Returns True if the closed window is the main one — the
        application should exit. Secondary windows are torn down
        in-place (their on_destroy fires, the entry is removed).
        """
        entry = self.get_entry_for_window_id(window_id)
        if entry is None:
            return False
        if entry.is_main:
            return True
        self.destroy_window(entry)
        return False
