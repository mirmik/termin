"""Explicit native-window API.

Importing :mod:`termin.display` remains safe for offscreen consumers. Programs
that own OS windows opt into the platform module through this namespace.
"""

from termin_nanobind.runtime import preload_sdk_libs

preload_sdk_libs("termin_window")
preload_sdk_libs("termin_display_window")

from termin.display._platform_native import (  # noqa: E402
    BackendWindow,
    BackendWindowSystem,
    PresentationMode,
    SDLBackendWindow,
    SystemCursorShape,
    WindowHandle,
    WindowManager,
    WindowedGraphicsSession,
    get_clipboard_text,
    poll_sdl_events,
    quit_sdl,
    set_clipboard_text,
    set_system_cursor,
    start_text_input,
    stop_text_input,
    wait_sdl_events_timeout,
)
from termin.display.window_manager import (  # noqa: E402
    BackendWindowEntry,
    BackendWindowManager,
)

__all__ = [
    "BackendWindow",
    "BackendWindowEntry",
    "BackendWindowManager",
    "BackendWindowSystem",
    "PresentationMode",
    "SDLBackendWindow",
    "SystemCursorShape",
    "WindowHandle",
    "WindowManager",
    "WindowedGraphicsSession",
    "get_clipboard_text",
    "poll_sdl_events",
    "quit_sdl",
    "set_clipboard_text",
    "set_system_cursor",
    "start_text_input",
    "stop_text_input",
    "wait_sdl_events_timeout",
]
