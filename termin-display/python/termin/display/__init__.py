from termin_nanobind.runtime import preload_sdk_libs

preload_sdk_libs("termin_display")

from termin.display._platform_native import BackendWindow
from termin.display.window_manager import (
    BackendWindowEntry,
    BackendWindowManager,
)

from termin.display._display_native import Display
from termin.display._display_native import DisplayInputRouter
from termin.display._display_native import FBOSurface
from termin.display._display_native import _display_get_surface_ptr
from termin.display._display_native import _display_input_router_base
from termin.display._display_native import _display_input_router_free
from termin.display._display_native import _display_input_router_new
from termin.display._display_native import _input_manager_create_vtable
from termin.display._display_native import _input_manager_free
from termin.display._display_native import _input_manager_new
from termin.display._display_native import _input_manager_on_char
from termin.display._display_native import _input_manager_on_key
from termin.display._display_native import _input_manager_on_mouse_button
from termin.display._display_native import _input_manager_on_mouse_move
from termin.display._display_native import _input_manager_on_scroll
from termin.display._display_native import _render_surface_free_external
from termin.display._display_native import _render_surface_get_input_manager
from termin.display._display_native import _render_surface_get_ptr
from termin.display._display_native import _render_surface_new_from_python
from termin.display._display_native import _render_surface_notify_resize
from termin.display._display_native import _render_surface_set_input_manager
from termin.display._display_native import _render_surface_set_on_resize
from termin.display._display_native import _viewport_get_input_manager
from termin.display._display_native import _viewport_input_manager_free
from termin.display._display_native import _viewport_input_manager_new

__all__ = [
    "BackendWindow",
    "BackendWindowEntry",
    "BackendWindowManager",
    "Display",
    "DisplayInputRouter",
    "FBOSurface",
    "_display_get_surface_ptr",
    "_display_input_router_base",
    "_display_input_router_free",
    "_display_input_router_new",
    "_input_manager_create_vtable",
    "_input_manager_free",
    "_input_manager_new",
    "_input_manager_on_char",
    "_input_manager_on_key",
    "_input_manager_on_mouse_button",
    "_input_manager_on_mouse_move",
    "_input_manager_on_scroll",
    "_render_surface_free_external",
    "_render_surface_get_input_manager",
    "_render_surface_get_ptr",
    "_render_surface_new_from_python",
    "_render_surface_notify_resize",
    "_render_surface_set_input_manager",
    "_render_surface_set_on_resize",
    "_viewport_get_input_manager",
    "_viewport_input_manager_free",
    "_viewport_input_manager_new",
]
