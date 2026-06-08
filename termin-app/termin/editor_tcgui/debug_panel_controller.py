"""Profiler / modules debug panel state for EditorWindowTcgui."""

from __future__ import annotations

from typing import Callable


class DebugPanelController:
    def __init__(
        self,
        *,
        get_ui: Callable[[], object | None],
        update_profiler_action: Callable[[], None],
        update_modules_action: Callable[[], None],
    ) -> None:
        self._get_ui = get_ui
        self._update_profiler_action = update_profiler_action
        self._update_modules_action = update_modules_action

        self._debug_panel = None
        self._debug_splitter = None
        self._profiler_panel = None
        self._modules_panel = None
        self._profiler_visible = False
        self._modules_visible = False
        self._last_profiler_update = 0.0
        self._last_modules_update = 0.0

    @property
    def profiler_visible(self) -> bool:
        return self._profiler_visible

    @property
    def modules_visible(self) -> bool:
        return self._modules_visible

    def set_widgets(
        self,
        *,
        debug_panel,
        debug_splitter,
        profiler_panel,
        modules_panel,
    ) -> None:
        self._debug_panel = debug_panel
        self._debug_splitter = debug_splitter
        self._profiler_panel = profiler_panel
        self._modules_panel = modules_panel
        self.update_visibility()

    def toggle_profiler(self) -> None:
        self._profiler_visible = not self._profiler_visible
        self.update_visibility()
        self._update_profiler_action()

    def toggle_modules(self) -> None:
        self._modules_visible = not self._modules_visible
        self.update_visibility()
        self._update_modules_action()

    def update_visibility(self) -> None:
        visible = self._profiler_visible or self._modules_visible
        if self._debug_panel is not None:
            self._debug_panel.visible = visible
        if self._debug_splitter is not None:
            self._debug_splitter.visible = visible

        if visible and self._debug_panel is not None:
            if self._profiler_visible and not self._modules_visible:
                self._debug_panel.selected_index = 0
            elif self._modules_visible and not self._profiler_visible:
                self._debug_panel.selected_index = 1

        ui = self._get_ui()
        if ui is not None:
            ui.request_layout()

    def poll(self, now: float) -> None:
        if self._profiler_visible and self._profiler_panel is not None:
            if now - self._last_profiler_update > 0.1:
                self._profiler_panel.update_display()
                self._last_profiler_update = now
        if self._modules_visible and self._modules_panel is not None:
            if now - self._last_modules_update > 1.0:
                self._modules_panel.update_display()
                self._last_modules_update = now
