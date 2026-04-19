"""tcgui-aware adapter around termin.display.BackendWindowManager.

The generic window-bag + device sharing lives in termin-display — this
module only binds tcgui ``UI`` instances to each window and drives
render_compose / present per frame. Secondary windows created through
``UI.create_window`` get their own ``UI`` built on the primary's
``Tgfx2Context`` so every renderer shares one IRenderDevice.
"""

from __future__ import annotations

from tcgui.widgets.ui import UI
from termin.display import (
    BackendWindow,
    BackendWindowEntry,
    BackendWindowManager as _BaseManager,
)


class BackendWindowManager(_BaseManager):
    """Multi-window manager specialized for tcgui UIs.

    Stores the ``UI`` of each window in ``entry.host_data`` so the
    render loop can look it up per frame.
    """

    # Default window background. UIRenderer clears its offscreen target
    # to this before drawing widgets; transparent regions show it after
    # the final composite is presented.
    WINDOW_BG: tuple[float, float, float, float] = (0.08, 0.08, 0.10, 1.0)

    def __init__(self) -> None:
        super().__init__()
        # Primary's Tgfx2Context, cached in register_main so every
        # secondary UI spins up with the same `graphics=` — one
        # IRenderDevice per process invariant.
        self._graphics = None

    def register_main(self, window: BackendWindow, ui: UI) -> BackendWindowEntry:  # type: ignore[override]
        entry = super().register_main(window, host_data=ui)
        self._graphics = ui._renderer.graphics
        ui.create_window = self._ui_create_window
        return entry

    def _ui_create_window(self, title: str, width: int, height: int) -> UI | None:
        """Bound to ``UI.create_window`` on every managed UI so widgets
        can pop secondary windows via ``parent_ui.create_window(...)``."""
        if self._graphics is None:
            raise RuntimeError(
                "BackendWindowManager: create_window called before "
                "register_main.")
        window_ui = UI(graphics=self._graphics)

        def _on_destroy(entry: BackendWindowEntry) -> None:
            # No UI teardown needed — UI has no native resources
            # beyond the shared Tgfx2Context. The BackendWindow dtor
            # runs after this, and that releases the OS handles.
            pass

        entry = super().create_window(
            title, width, height,
            host_data=window_ui, on_destroy=_on_destroy)

        # Let widgets inside this UI pop their own windows and close
        # themselves. close_window is the graceful path (button / esc);
        # on_empty fires when the UI root becomes empty.
        def _close():
            self.destroy_window(entry)

        window_ui.close_window = _close
        window_ui.on_empty = _close
        window_ui.create_window = self._ui_create_window
        return window_ui

    # ------------------------------------------------------------------
    # Per-frame render loop
    # ------------------------------------------------------------------

    def render_all(self) -> None:
        """Render every registered window's UI and present its composite."""
        for entry in list(self.entries):
            ui: UI = entry.host_data
            vw, vh = entry.window.framebuffer_size()
            if vw <= 0 or vh <= 0:
                continue
            tex = ui.render_compose(vw, vh, background_color=self.WINDOW_BG)
            ui.process_deferred()
            if tex is None:
                # Empty UI — skip present so the swapchain keeps the
                # previous frame on screen instead of showing garbage.
                continue
            entry.window.present(tex)

    def poll_events(self) -> bool:
        """Drain events on every window. Returns False if the main
        window was closed (application should exit)."""
        alive = True
        for entry in self.entries:
            entry.window.poll_events()
            if entry.is_main and entry.window.should_close():
                alive = False
        return alive

    def close_main(self) -> None:
        main = self.main_entry()
        if main is not None:
            main.window.set_should_close(True)
