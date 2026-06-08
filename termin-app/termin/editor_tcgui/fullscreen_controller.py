"""Fullscreen panel visibility state for EditorWindowTcgui."""

from __future__ import annotations

from typing import Callable


class FullscreenController:
    def __init__(
        self,
        *,
        get_panels: Callable[[], list[object | None]],
        update_fullscreen_action: Callable[[], None],
    ) -> None:
        self._get_panels = get_panels
        self._update_fullscreen_action = update_fullscreen_action
        self._is_fullscreen = False
        self._pre_fullscreen_state: dict[int, bool] | None = None

    @property
    def is_fullscreen(self) -> bool:
        return self._is_fullscreen

    def toggle(self) -> None:
        panels = self._get_panels()
        if self._is_fullscreen:
            if self._pre_fullscreen_state is not None:
                for widget in panels:
                    if widget is not None and id(widget) in self._pre_fullscreen_state:
                        widget.visible = self._pre_fullscreen_state[id(widget)]
            self._is_fullscreen = False
            self._pre_fullscreen_state = None
        else:
            self._pre_fullscreen_state = {}
            for widget in panels:
                if widget is not None:
                    self._pre_fullscreen_state[id(widget)] = widget.visible
                    widget.visible = False
            self._is_fullscreen = True
        self._update_fullscreen_action()
