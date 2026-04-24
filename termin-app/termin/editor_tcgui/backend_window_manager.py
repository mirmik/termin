"""BackendWindow-based window manager for the tcgui editor.

Replaces ``SDLWindowManager`` for the main window. Builds on
``termin.display.BackendWindow``, which speaks both OpenGL and Vulkan
from the same Python API — so the editor can host either backend
without any changes above this file.

Secondary windows are deferred to M5 (single-device, multi-surface
support). Code below assumes a single main BackendWindow.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tcgui.widgets.ui import UI
from termin.display._platform_native import BackendWindow


@dataclass
class BackendWindowEntry:
    """A BackendWindow paired with its UI and metadata."""
    window: BackendWindow
    ui: UI
    is_main: bool = False


class BackendWindowManager:
    """Multi-window manager on top of BackendWindow.

    Unlike ``SDLWindowManager``, there is no per-window GL context
    nor a per-window tc_gpu_context — BackendWindow owns the single
    process-global IRenderDevice and every UI renders through the
    same borrowed Tgfx2Context.
    """

    # Default window background. UIRenderer clears its offscreen target
    # to this before drawing widgets; transparent regions show it after
    # the final composite is presented.
    WINDOW_BG: tuple[float, float, float, float] = (0.08, 0.08, 0.10, 1.0)

    def __init__(self) -> None:
        self._windows: list[BackendWindowEntry] = []

    @property
    def windows(self) -> list[BackendWindowEntry]:
        return self._windows

    def register_main(self, window: BackendWindow, ui: UI) -> None:
        entry = BackendWindowEntry(window=window, ui=ui, is_main=True)
        self._windows.append(entry)
        # Multi-window support lives in M5; disable the callback so
        # widgets that try to pop secondary windows fail loudly rather
        # than silently — easier to notice when the feature returns.
        ui.create_window = None

    def render_all(self) -> None:
        """Render every registered window and present its composite."""
        for entry in list(self._windows):
            vw, vh = entry.window.framebuffer_size()
            if vw <= 0 or vh <= 0:
                continue
            tex = entry.ui.render_compose(vw, vh, background_color=self.WINDOW_BG)
            entry.ui.process_deferred()
            if tex is None:
                # Empty UI (no root, no overlays) — nothing to show.
                # Skipping present() keeps the previous frame on screen
                # rather than flashing whatever garbage the swapchain
                # image happens to contain.
                continue
            entry.window.present(tex)

    def poll_events(self) -> bool:
        """Drain events on every window. Returns False if the main
        window was closed (application should exit)."""
        alive = True
        for entry in self._windows:
            entry.window.poll_events()
            if entry.is_main and entry.window.should_close():
                alive = False
        return alive

    def close_main(self) -> None:
        for entry in self._windows:
            if entry.is_main:
                entry.window.set_should_close(True)

    def destroy_all(self) -> None:
        # BackendWindow's dtor tears down GL context / Vulkan device /
        # SDL window in the correct order. Python drops the wrapper on
        # list clear.
        self._windows.clear()
