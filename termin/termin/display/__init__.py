from termin import _dll_setup  # noqa: F401

_dll_setup.extend_package_path(__path__, "display")

from termin.display._display_native import Display  # noqa: E402
from termin.display._display_native import DisplayInputRouter  # noqa: E402
from termin.display._display_native import _display_get_surface_ptr  # noqa: E402
from termin.display._display_native import _display_input_router_base  # noqa: E402
from termin.display._display_native import _display_input_router_free  # noqa: E402
from termin.display._display_native import _display_input_router_new  # noqa: E402
from termin.display._display_native import _input_manager_create_vtable  # noqa: E402
from termin.display._display_native import _input_manager_free  # noqa: E402
from termin.display._display_native import _input_manager_new  # noqa: E402
from termin.display._display_native import _input_manager_on_char  # noqa: E402
from termin.display._display_native import _input_manager_on_key  # noqa: E402
from termin.display._display_native import _input_manager_on_mouse_button  # noqa: E402
from termin.display._display_native import _input_manager_on_mouse_move  # noqa: E402
from termin.display._display_native import _input_manager_on_scroll  # noqa: E402
from termin.display._display_native import _render_surface_free_external  # noqa: E402
from termin.display._display_native import _render_surface_get_input_manager  # noqa: E402
from termin.display._display_native import _render_surface_get_ptr  # noqa: E402
from termin.display._display_native import _render_surface_new_from_python  # noqa: E402
from termin.display._display_native import _render_surface_notify_resize  # noqa: E402
from termin.display._display_native import _render_surface_set_input_manager  # noqa: E402
from termin.display._display_native import _render_surface_set_on_resize  # noqa: E402
from termin.display._display_native import _viewport_get_input_manager  # noqa: E402
from termin.display._display_native import _viewport_input_manager_free  # noqa: E402
from termin.display._display_native import _viewport_input_manager_new  # noqa: E402

__all__ = [
    "Display",
    "DisplayInputRouter",
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
