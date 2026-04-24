"""
Display — Python wrapper for C++ TcDisplay.

Minimal wrapper that adds:
- surface property (stores Python RenderSurface to prevent GC)
- Resize callback setup
"""

from __future__ import annotations

import uuid as uuid_module
from typing import TYPE_CHECKING

from termin._native.render import Display as CppDisplay

if TYPE_CHECKING:
    from termin.visualization.render.surface import RenderSurface


class Display(CppDisplay):
    """
    Display — what and where to render.

    Inherits from C++ TcDisplay, adds surface property.
    """

    def __init__(
        self,
        surface: "RenderSurface",
        name: str = "Display",
        editor_only: bool = False,
        uuid: str | None = None,
    ):
        """
        Create Display with specified surface.

        Args:
            surface: Render surface (WindowRenderSurface or OffscreenRenderSurface).
            name: Display name.
            editor_only: If True, display is created and rendered only in editor.
            uuid: UUID (generated if not specified).
        """
        # Store Python surface reference to prevent GC
        self._surface = surface
        self._input_manager = None

        # Get tc_render_surface pointer from surface
        tc_surface_obj = surface.tc_surface()
        tc_surface_ptr = tc_surface_obj.ptr if tc_surface_obj else 0

        # Generate UUID if not provided
        if uuid is None:
            uuid = str(uuid_module.uuid4())

        # Initialize C++ base class
        super().__init__(tc_surface_ptr, name, editor_only, uuid)

        # Set up resize callback to update viewport pixel_rects
        from termin._native.render import _render_surface_set_on_resize
        _render_surface_set_on_resize(tc_surface_ptr, self._on_resize)

    def _on_resize(self, width: int, height: int) -> None:
        """Called when surface resizes - update viewport pixel_rects."""
        self.update_all_pixel_rects()

    @property
    def surface(self) -> "RenderSurface":
        """Render surface."""
        return self._surface

    def connect_input(self) -> None:
        """Create and attach DisplayInputRouter.

        Routes events from the surface to each viewport's input manager,
        which dispatches to scene InputComponents (e.g. OrbitCameraController).
        """
        from termin.visualization.platform.input_manager import DisplayInputRouter
        self._input_router = DisplayInputRouter(self.tc_display_ptr)

    def viewport_rect_to_pixels(self, viewport) -> tuple[int, int, int, int]:
        """
        Convert normalized viewport rect to pixels.

        Args:
            viewport: Viewport to convert.

        Returns:
            (px, py, pw, ph) — position and size in pixels.
        """
        width, height = self.get_size()
        vx, vy, vw, vh = viewport.rect
        px = int(vx * width)
        py = int(vy * height)
        pw = int(vw * width)
        ph = int(vh * height)
        return (px, py, pw, ph)
