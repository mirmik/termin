"""Viewport interaction callback registry for EditorWindowTcgui."""

from __future__ import annotations

from typing import Callable

from tcbase import log


ViewportPointerHandler = Callable[[str, float, float, float, float, int, int, int], bool]
ViewportKeyHandler = Callable[[object], bool]
ViewportOverlayDrawer = Callable[[], None]


class ViewportInteractionHub:
    def __init__(
        self,
        *,
        request_viewport_update: Callable[[], None],
        on_tool_activity_changed: Callable[[], None],
    ) -> None:
        self._request_viewport_update = request_viewport_update
        self._on_tool_activity_changed = on_tool_activity_changed

        self._click_interceptor: Callable | None = None
        self._click_interceptors: list[Callable] = []
        self._pointer_handlers: list[ViewportPointerHandler] = []
        self._key_handlers: list[ViewportKeyHandler] = []
        self._overlay_drawers: list[ViewportOverlayDrawer] = []
        self._active_tool_count = 0

    @property
    def active_tool_count(self) -> int:
        return self._active_tool_count

    def set_click_interceptor(self, callback: Callable | None) -> None:
        self._click_interceptor = callback

    def add_click_interceptor(self, callback: Callable) -> None:
        if callback not in self._click_interceptors:
            self._click_interceptors.append(callback)

    def remove_click_interceptor(self, callback: Callable) -> None:
        self._click_interceptors = [
            existing for existing in self._click_interceptors
            if existing != callback
        ]

    def add_pointer_handler(self, callback: ViewportPointerHandler) -> None:
        if callback not in self._pointer_handlers:
            self._pointer_handlers.append(callback)

    def remove_pointer_handler(self, callback: ViewportPointerHandler) -> None:
        self._pointer_handlers = [
            existing for existing in self._pointer_handlers
            if existing != callback
        ]

    def add_key_handler(self, callback: ViewportKeyHandler) -> None:
        if callback not in self._key_handlers:
            self._key_handlers.append(callback)

    def remove_key_handler(self, callback: ViewportKeyHandler) -> None:
        self._key_handlers = [
            existing for existing in self._key_handlers
            if existing != callback
        ]

    def add_overlay_drawer(self, callback: ViewportOverlayDrawer) -> None:
        if callback not in self._overlay_drawers:
            self._overlay_drawers.append(callback)
            self._request_viewport_update()

    def remove_overlay_drawer(self, callback: ViewportOverlayDrawer) -> None:
        before = len(self._overlay_drawers)
        self._overlay_drawers = [
            existing for existing in self._overlay_drawers
            if existing != callback
        ]
        if len(self._overlay_drawers) != before:
            self._request_viewport_update()

    def begin_tool(self) -> None:
        self._active_tool_count += 1
        if self._active_tool_count == 1:
            self._on_tool_activity_changed()

    def end_tool(self) -> None:
        if self._active_tool_count <= 0:
            log.error("[EditorWindowTcgui] viewport tool release without matching begin")
            self._active_tool_count = 0
            return
        self._active_tool_count -= 1
        if self._active_tool_count == 0:
            self._on_tool_activity_changed()

    def dispatch_click(self, *args) -> bool:
        if self._click_interceptor is not None:
            try:
                if bool(self._click_interceptor(*args)):
                    return True
            except Exception as e:
                log.error(f"[EditorWindowTcgui] viewport click interceptor failed: {e}")
                return False
        for callback in self._click_interceptors:
            try:
                if bool(callback(*args)):
                    return True
            except Exception as e:
                log.error(f"[EditorWindowTcgui] viewport click interceptor failed: {e}")
                return False
        return False

    def dispatch_pointer(
        self,
        phase: str,
        x: float,
        y: float,
        dx: float,
        dy: float,
        button: int,
        action: int,
        mods: int,
    ) -> bool:
        handlers = list(self._pointer_handlers)
        handlers.reverse()
        for callback in handlers:
            try:
                if bool(callback(phase, x, y, dx, dy, button, action, mods)):
                    return True
            except Exception as e:
                log.error(f"[EditorWindowTcgui] viewport pointer handler failed: {e}")
                return False
        return False

    def dispatch_key(self, event) -> bool:
        handlers = list(self._key_handlers)
        handlers.reverse()
        for callback in handlers:
            try:
                if bool(callback(event)):
                    return True
            except Exception as e:
                log.error(f"[EditorWindowTcgui] viewport key handler failed: {e}")
                return True
        return False

    def draw_overlays(self) -> bool:
        has_overlay_drawers = False
        for drawer in self._overlay_drawers:
            has_overlay_drawers = True
            try:
                drawer()
            except Exception as e:
                log.error(f"[EditorWindowTcgui] viewport overlay drawer failed: {e}")
        return has_overlay_drawers
