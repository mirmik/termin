"""Window manager — abstract multi-window support for tcgui."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tgfx import (
    GraphicsBackend,
    tc_gpu_context_new,
    tc_gpu_set_context,
    tc_gpu_context_set_name,
    tc_gpu_context_free,
    tc_gpu_share_group_get_or_create,
    tc_gpu_share_group_unref,
)
from tcgui.widgets.ui import UI


@dataclass
class WindowEntry:
    """A single window with its native handle, GL context, and UI."""
    handle: Any
    gl_context: Any
    ui: UI
    is_main: bool = False
    gpu_context: int = 0


class WindowManager:
    """Backend-agnostic multi-window manager.

    Subclass and implement the ``_*`` methods for a specific
    windowing backend (SDL, GLFW, etc.).
    """

    def __init__(self, graphics: GraphicsBackend, share_group_key: int = 0):
        self._graphics = graphics
        self._windows: list[WindowEntry] = []
        self._share_group_key = share_group_key

    @property
    def windows(self) -> list[WindowEntry]:
        return self._windows

    def _create_gpu_context(self, name: str) -> int:
        """Create a tc_gpu_context in the same share group."""
        group = tc_gpu_share_group_get_or_create(self._share_group_key)
        ctx = tc_gpu_context_new(0, group)
        tc_gpu_context_set_name(ctx, name)
        tc_gpu_share_group_unref(group)
        return ctx

    def _destroy_gpu_context(self, entry: WindowEntry) -> None:
        if entry.gpu_context:
            tc_gpu_context_free(entry.gpu_context)
            entry.gpu_context = 0

    def register_main(self, handle: Any, gl_context: Any, ui: UI) -> None:
        """Register the main (already-created) window."""
        entry = WindowEntry(handle, gl_context, ui, is_main=True)
        self._make_current(entry)
        entry.gpu_context = self._create_gpu_context("main_window")
        self._windows.append(entry)
        ui.create_window = self.create_window

    def create_window(self, title: str, width: int, height: int) -> UI | None:
        """Create a new window. Used as ``UI.create_window`` callback."""
        handle, gl_context = self._create_native_window(title, width, height)
        window_ui = UI()
        entry = WindowEntry(handle, gl_context, window_ui)
        self._make_current(entry)
        entry.gpu_context = self._create_gpu_context(f"window:{title[:20]}")
        self._windows.append(entry)

        def _destroy():
            if entry in self._windows:
                self._windows.remove(entry)
                self._make_current(entry)
                self._destroy_gpu_context(entry)
                self._destroy_native_window(entry)

        window_ui.close_window = _destroy
        window_ui.on_empty = _destroy
        window_ui.create_window = self.create_window
        return window_ui

    def render_all(self) -> None:
        """Render all windows."""
        for entry in list(self._windows):
            self._make_current(entry)
            tc_gpu_set_context(entry.gpu_context)
            vw, vh = self._get_drawable_size(entry)
            self._graphics.bind_framebuffer(None)
            self._graphics.set_viewport(0, 0, vw, vh)
            self._graphics.clear_color_depth(0.08, 0.08, 0.10, 1.0)
            entry.ui.render(vw, vh)
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
