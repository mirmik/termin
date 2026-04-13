"""
Display — Python wrapper for C++ TcDisplay.

Adds:
- surface property (stores Python RenderSurface to prevent GC)
- Resize callback setup
- connect_input() for input routing
"""

from __future__ import annotations

import uuid as uuid_module
from typing import TYPE_CHECKING

from termin.display._display_native import (
    Display as CppDisplay,
    DisplayInputRouter,
    _render_surface_set_on_resize,
)

if TYPE_CHECKING:
    pass


class Display(CppDisplay):
    """Display wraps C++ TcDisplay, adds surface property and input routing."""

    def __init__(
        self,
        surface,
        name: str = "Display",
        editor_only: bool = False,
        uuid: str | None = None,
    ):
        self._surface = surface
        self._input_router = None

        tc_surface_obj = surface.tc_surface()
        tc_surface_ptr = tc_surface_obj.ptr if tc_surface_obj else 0

        if uuid is None:
            uuid = str(uuid_module.uuid4())

        super().__init__(tc_surface_ptr, name, editor_only, uuid)

        _render_surface_set_on_resize(tc_surface_ptr, self._on_resize)

    def _on_resize(self, width: int, height: int) -> None:
        self.update_all_pixel_rects()

    @property
    def surface(self):
        return self._surface

    def connect_input(self) -> None:
        """Create and attach DisplayInputRouter for input dispatch."""
        self._input_router = DisplayInputRouter(self.tc_display_ptr)

    def viewport_rect_to_pixels(self, viewport) -> tuple[int, int, int, int]:
        width, height = self.get_size()
        vx, vy, vw, vh = viewport.rect
        px = int(vx * width)
        py = int(vy * height)
        pw = int(vw * width)
        ph = int(vh * height)
        return (px, py, pw, ph)
