"""Window manager — abstract multi-window support for tcgui."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tcgui.widgets.ui import UI


@dataclass
class WindowEntry:
    """A single window with its native handle, GL context, and UI."""
    handle: Any
    gl_context: Any
    ui: UI
    is_main: bool = False


class WindowManager:
    """Backend-agnostic multi-window manager.

    Subclass and implement the ``_*`` methods for a specific
    windowing backend (SDL, GLFW, etc.).
    """

    def __init__(self, share_group_key: int = 0):
        self._windows: list[WindowEntry] = []
        # Kept as a compatibility parameter while callers are cleaned up.
        _ = share_group_key
        # Process-wide Tgfx2Context — set by register_main(). Every
        # secondary window built via create_window() hands the same
        # object to its UI so all UIRenderers draw through one
        # IRenderDevice.
        self._graphics = None

    @property
    def windows(self) -> list[WindowEntry]:
        return self._windows

    def register_main(self, handle: Any, gl_context: Any, ui: UI) -> None:
        """Register the main (already-created) window."""
        entry = WindowEntry(handle, gl_context, ui, is_main=True)
        self._make_current(entry)
        self._windows.append(entry)
        # Pick up the Tgfx2Context the main UI was built with so
        # create_window() can reuse it for secondary windows — single
        # IRenderDevice invariant for the whole process.
        self._graphics = ui._renderer.graphics
        ui.create_window = self.create_window

    def create_window(self, title: str, width: int, height: int) -> UI | None:
        """Create a new window. Used as ``UI.create_window`` callback."""
        if self._graphics is None:
            raise RuntimeError(
                "WindowManager.create_window called before register_main: "
                "no graphics context to share with the new window.")
        handle, gl_context = self._create_native_window(title, width, height)
        window_ui = UI(graphics=self._graphics)
        entry = WindowEntry(handle, gl_context, window_ui)
        self._make_current(entry)
        self._windows.append(entry)

        def _destroy():
            if entry in self._windows:
                self._windows.remove(entry)
                self._make_current(entry)
                self._destroy_native_window(entry)

        window_ui.close_window = _destroy
        window_ui.on_empty = _destroy
        window_ui.create_window = self.create_window
        return window_ui

    # Default window background. UIRenderer clears its offscreen
    # target to this before drawing widgets, so transparent regions
    # show it after the final composite into the default framebuffer.
    WINDOW_BG: tuple[float, float, float, float] = (0.08, 0.08, 0.10, 1.0)

    def render_all(self) -> None:
        """Render all windows."""
        for entry in list(self._windows):
            self._make_current(entry)
            vw, vh = self._get_drawable_size(entry)
            entry.ui.render(vw, vh, background_color=self.WINDOW_BG)
            entry.ui.process_deferred()
            self._swap(entry)

    def get_ui_for_event(self, window_id: int) -> UI | None:
        """Find UI by native window ID."""
        for entry in self._windows:
            if self._get_window_id(entry) == window_id:
                return entry.ui
        return None

    def handle_window_close(self, window_id: int) -> bool:
        """Handle a window close event.

        Returns True if the closed window is main (application should exit).
        """
        for entry in self._windows:
            if self._get_window_id(entry) == window_id:
                if entry.is_main:
                    return True
                if entry.ui.close_window is not None:
                    entry.ui.close_window()
                return False
        return False

    # ------------------------------------------------------------------
    # Abstract — backend implements these
    # ------------------------------------------------------------------

    def _create_native_window(self, title: str, width: int,
                              height: int) -> tuple[Any, Any]:
        raise NotImplementedError

    def _destroy_native_window(self, entry: WindowEntry) -> None:
        raise NotImplementedError

    def _make_current(self, entry: WindowEntry) -> None:
        raise NotImplementedError

    def _get_drawable_size(self, entry: WindowEntry) -> tuple[int, int]:
        raise NotImplementedError

    def _swap(self, entry: WindowEntry) -> None:
        raise NotImplementedError

    def _get_window_id(self, entry: WindowEntry) -> int:
        raise NotImplementedError
