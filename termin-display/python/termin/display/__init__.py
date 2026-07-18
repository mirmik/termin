import logging

from termin_nanobind.runtime import preload_sdk_libs

preload_sdk_libs("termin_display")

_logger = logging.getLogger(__name__)

try:
    from termin.display._platform_native import (
        BackendWindow,
        PresentationMode,
        SDLBackendWindow,
        get_clipboard_text,
        poll_sdl_events,
        quit_sdl,
        set_clipboard_text,
        start_text_input,
        stop_text_input,
        wait_sdl_events_timeout,
    )
except ImportError as e:
    _logger.debug("Platform native module not available (optional): %s", e)
    BackendWindow = None
    PresentationMode = None
    SDLBackendWindow = None
    get_clipboard_text = None
    poll_sdl_events = None
    quit_sdl = None
    set_clipboard_text = None
    start_text_input = None
    stop_text_input = None
    wait_sdl_events_timeout = None

try:
    from termin.display.window_manager import (
        BackendWindowEntry,
        BackendWindowManager,
    )
except ImportError as e:
    _logger.debug("Window manager not available (optional): %s", e)
    BackendWindowEntry = None
    BackendWindowManager = None

from termin.display._display_native import Display
from termin.display._display_native import DisplayInputRouter
from termin.display._display_native import FBOSurface
from termin.display._display_native import _display_get_surface_ptr as _display_get_surface_ptr
from termin.display._display_native import _display_input_router_base as _display_input_router_base
from termin.display._display_native import _display_input_router_free as _display_input_router_free
from termin.display._display_native import _display_input_router_new as _display_input_router_new
from termin.display._display_native import _input_manager_create_vtable as _input_manager_create_vtable
from termin.display._display_native import _input_manager_free as _input_manager_free
from termin.display._display_native import _input_manager_new as _input_manager_new
from termin.display._display_native import _input_manager_on_char as _input_manager_on_char
from termin.display._display_native import _input_manager_on_key as _input_manager_on_key
from termin.display._display_native import _input_manager_on_mouse_button as _input_manager_on_mouse_button
from termin.display._display_native import _input_manager_on_mouse_move as _input_manager_on_mouse_move
from termin.display._display_native import _input_manager_on_scroll as _input_manager_on_scroll
from termin.display._display_native import _render_surface_free_external as _render_surface_free_external
from termin.display._display_native import _render_surface_get_input_manager as _render_surface_get_input_manager
from termin.display._display_native import _render_surface_get_ptr as _render_surface_get_ptr
from termin.display._display_native import _render_surface_new_from_python as _render_surface_new_from_python
from termin.display._display_native import _render_surface_notify_resize as _render_surface_notify_resize
from termin.display._display_native import _render_surface_set_input_manager as _render_surface_set_input_manager
from termin.display._display_native import _render_surface_set_on_resize as _render_surface_set_on_resize
from termin.display._display_native import _viewport_get_input_manager as _viewport_get_input_manager
from termin.display._display_native import _viewport_input_manager_free as _viewport_input_manager_free
from termin.display._display_native import _viewport_input_manager_new as _viewport_input_manager_new
from termin.display.input_manager import BasicDisplayInputManager

__all__ = [
    "BackendWindow",
    "PresentationMode",
    "SDLBackendWindow",
    "get_clipboard_text",
    "poll_sdl_events",
    "quit_sdl",
    "set_clipboard_text",
    "start_text_input",
    "stop_text_input",
    "wait_sdl_events_timeout",
    "BackendWindowEntry",
    "BackendWindowManager",
    "Display",
    "DisplayInputRouter",
    "BasicDisplayInputManager",
    "FBOSurface",
]
