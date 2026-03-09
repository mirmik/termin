"""SDL2-based window backend using C++ SDLWindowRenderSurface."""

from __future__ import annotations

from typing import Any, Callable, Optional, Tuple

from termin._native.platform import (
    SDLWindowBackend as _SDLWindowBackend,
    SDLWindowRenderSurface,
)
from termin.graphics import OpenGLGraphicsBackend

from tgfx.window import BackendWindow, WindowBackend


class _TcSurfaceWrapper:
    """Wrapper with .ptr for Display interop."""

    def __init__(self, ptr: int):
        self.ptr = ptr


class SDLWindowHandle(BackendWindow):
    """SDL2 window wrapper using C++ SDLWindowRenderSurface.

    Events are dispatched at the C++ level through the surface's
    input_manager — no Python callback wiring needed for input.
    """

    def __init__(
        self,
        _render_surface: SDLWindowRenderSurface,
        graphics: Optional[OpenGLGraphicsBackend] = None,
    ):
        self._render_surface = _render_surface
        self._user_pointer: Any = None

        if graphics is not None:
            self._render_surface.set_graphics(graphics)

    def close(self) -> None:
        self._render_surface.set_should_close(True)

    def should_close(self) -> bool:
        return self._render_surface.should_close()

    def make_current(self) -> None:
        self._render_surface.make_current()

    def swap_buffers(self) -> None:
        self._render_surface.swap_buffers()

    def framebuffer_size(self) -> Tuple[int, int]:
        return self._render_surface.get_size()

    def window_size(self) -> Tuple[int, int]:
        return self._render_surface.window_size()

    def get_cursor_pos(self) -> Tuple[float, float]:
        return self._render_surface.get_cursor_pos()

    def set_should_close(self, flag: bool) -> None:
        self._render_surface.set_should_close(flag)

    def set_user_pointer(self, ptr: Any) -> None:
        self._user_pointer = ptr

    def set_graphics(self, graphics: OpenGLGraphicsBackend) -> None:
        self._render_surface.set_graphics(graphics)

    def set_framebuffer_size_callback(self, callback: Callable) -> None:
        pass  # Resize handled by tc_render_surface_notify_resize in C++

    def set_cursor_pos_callback(self, callback: Callable) -> None:
        pass  # Events dispatched through input_manager

    def set_scroll_callback(self, callback: Callable) -> None:
        pass  # Events dispatched through input_manager

    def set_mouse_button_callback(self, callback: Callable) -> None:
        pass  # Events dispatched through input_manager

    def set_key_callback(self, callback: Callable) -> None:
        pass  # Events dispatched through input_manager

    def request_update(self) -> None:
        self._render_surface.request_update()

    def get_window_framebuffer(self) -> Any:
        return self._render_surface.get_window_framebuffer()

    def get_framebuffer(self):
        return self.get_window_framebuffer()

    def get_framebuffer_id(self) -> int:
        return 0

    def tc_surface(self) -> _TcSurfaceWrapper:
        return _TcSurfaceWrapper(self._render_surface.tc_surface_ptr())

    def get_window_id(self) -> int:
        return self._render_surface.window_id()


class SDLWindowBackend(WindowBackend):
    """SDL2 window backend using C++ implementation."""

    def __init__(self, graphics: Optional[OpenGLGraphicsBackend] = None):
        self._backend = _SDLWindowBackend()
        self._graphics = graphics
        self._windows: dict[int, SDLWindowHandle] = {}

    def set_graphics(self, graphics: OpenGLGraphicsBackend) -> None:
        self._graphics = graphics

    def create_window(
        self,
        width: int,
        height: int,
        title: str,
        share: Optional[BackendWindow] = None,
    ) -> SDLWindowHandle:
        share_surface = None
        if share is not None and isinstance(share, SDLWindowHandle):
            share_surface = share._render_surface
        surface = SDLWindowRenderSurface(
            width, height, title, self._backend, share_surface,
        )
        handle = SDLWindowHandle(surface, graphics=self._graphics)
        self._windows[handle.get_window_id()] = handle
        return handle

    def poll_events(self) -> None:
        self._backend.poll_events()

        closed_ids = [
            wid for wid, win in self._windows.items() if win.should_close()
        ]
        for wid in closed_ids:
            del self._windows[wid]

    def terminate(self) -> None:
        for win in list(self._windows.values()):
            win.close()
        self._windows.clear()
        self._backend.terminate()
