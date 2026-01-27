"""
Display — Python wrapper for tc_display (render target with viewports).

Display combines:
- tc_render_surface — where we render (window or offscreen)
- Viewports — list of viewports with cameras and scenes

Display does NOT handle:
- Input (handled by DisplayInputManager)
- Window creation (handled by Visualization or Editor)
"""

from __future__ import annotations

import uuid as uuid_module
from typing import TYPE_CHECKING

from termin._native.render import (
    _display_new,
    _display_free,
    _display_get_name,
    _display_set_name,
    _display_get_uuid,
    _display_set_uuid,
    _display_get_editor_only,
    _display_set_editor_only,
    _display_get_surface,
    _display_add_viewport,
    _display_remove_viewport,
    _display_get_viewport_count,
    _display_get_viewport_at_index,
    _display_viewport_at,
    _display_viewport_at_screen,
    _display_get_size,
    _display_update_all_pixel_rects,
    _display_make_current,
    _display_swap_buffers,
)

if TYPE_CHECKING:
    from termin.visualization.core.camera import CameraComponent
    from termin.visualization.core.scene import Scene
    from termin.visualization.core.viewport import Viewport
    from termin.visualization.render.surface import RenderSurface
    from termin.visualization.render.framegraph import RenderPipeline
    from termin.visualization.ui.canvas import Canvas


class Display:
    """
    Display — what and where to render.

    Wraps tc_display from core_c. Contains:
    - surface: RenderSurface (window or offscreen FBO)
    - viewports: list of Viewports

    For rendering use RenderEngine externally:
        engine.render_views(display.surface, views)
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
        # Initialize pointer to 0 before any operations that could fail
        self._tc_display_ptr: int = 0

        # Store Python surface reference to prevent GC
        self._surface = surface

        # Get tc_render_surface pointer from surface
        # SDLWindowRenderSurface has tc_surface() method returning tc_render_surface*
        tc_surface_obj = surface.tc_surface()
        tc_surface_ptr = tc_surface_obj.ptr if tc_surface_obj else 0

        # Create tc_display
        self._tc_display_ptr = _display_new(tc_surface_ptr, name)

        # Set UUID (generate if not provided)
        if uuid is None:
            uuid = str(uuid_module.uuid4())
        _display_set_uuid(self._tc_display_ptr, uuid)

        # Set editor_only flag
        _display_set_editor_only(self._tc_display_ptr, editor_only)

        # Set up resize callback to update viewport pixel_rects
        from termin._native.render import _render_surface_set_on_resize
        _render_surface_set_on_resize(tc_surface_ptr, self._on_resize)

    def _on_resize(self, width: int, height: int) -> None:
        """Called when surface resizes - update viewport pixel_rects."""
        self.update_all_pixel_rects()

    def __del__(self):
        if self._tc_display_ptr:
            _display_free(self._tc_display_ptr)
            self._tc_display_ptr = 0

    @property
    def tc_display_ptr(self) -> int:
        """Raw pointer to tc_display (for C interop)."""
        return self._tc_display_ptr

    @property
    def name(self) -> str:
        """Display name."""
        return _display_get_name(self._tc_display_ptr)

    @name.setter
    def name(self, value: str) -> None:
        _display_set_name(self._tc_display_ptr, value)

    @property
    def uuid(self) -> str:
        """Unique identifier (for serialization)."""
        return _display_get_uuid(self._tc_display_ptr)

    @property
    def runtime_id(self) -> int:
        """64-bit hash of UUID (for fast runtime lookup)."""
        return hash(self.uuid) & 0xFFFFFFFFFFFFFFFF

    @property
    def editor_only(self) -> bool:
        """If True, display is created and rendered only in editor."""
        return _display_get_editor_only(self._tc_display_ptr)

    @editor_only.setter
    def editor_only(self, value: bool) -> None:
        _display_set_editor_only(self._tc_display_ptr, value)

    @property
    def surface(self) -> "RenderSurface":
        """Render surface."""
        return self._surface

    @property
    def viewports(self) -> list["Viewport"]:
        """List of viewports (read-only, iterates C linked list)."""
        from termin.viewport import Viewport

        count = _display_get_viewport_count(self._tc_display_ptr)
        result = []
        for i in range(count):
            vp_ptr = _display_get_viewport_at_index(self._tc_display_ptr, i)
            if vp_ptr:
                result.append(Viewport._from_ptr(vp_ptr))
        return result

    def get_size(self) -> tuple[int, int]:
        """Return display size in pixels."""
        return _display_get_size(self._tc_display_ptr)

    def add_viewport(self, viewport: "Viewport") -> "Viewport":
        """
        Add viewport to display.

        Args:
            viewport: Viewport to add.

        Returns:
            Added viewport.
        """
        vp_ptr = viewport._tc_viewport_ptr()
        _display_add_viewport(self._tc_display_ptr, vp_ptr)
        self._update_viewport_pixel_rect(viewport)
        return viewport

    def remove_viewport(self, viewport: "Viewport") -> None:
        """
        Remove viewport from display.

        Args:
            viewport: Viewport to remove.
        """
        vp_ptr = viewport._tc_viewport_ptr()
        _display_remove_viewport(self._tc_display_ptr, vp_ptr)
        # Remove viewport from camera's list
        if viewport.camera is not None:
            viewport.camera.remove_viewport(viewport)

    def _update_viewport_pixel_rect(self, viewport: "Viewport") -> None:
        """Recalculate pixel_rect for one viewport."""
        width, height = self.get_size()
        vx, vy, vw, vh = viewport.rect
        px = int(vx * width)
        py = int(vy * height)
        pw = max(1, int(vw * width))
        ph = max(1, int(vh * height))
        viewport.pixel_rect = (px, py, pw, ph)

    def update_all_pixel_rects(self) -> None:
        """Recalculate pixel_rect for all viewports. Call on surface resize."""
        _display_update_all_pixel_rects(self._tc_display_ptr)

    def create_viewport(
        self,
        scene: "Scene",
        camera: "CameraComponent",
        rect: tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0),
        pipeline: "RenderPipeline | None" = None,
        name: str = "main",
    ) -> "Viewport":
        """
        Create and add new viewport.

        Args:
            scene: Scene to render.
            camera: Camera for rendering.
            rect: Normalized rectangle (x, y, w, h) in [0..1].
            pipeline: Render pipeline (None = default pipeline).
            name: Viewport name for identification in pipeline.

        Returns:
            Created Viewport.
        """
        from termin.visualization.core.viewport import Viewport, make_default_pipeline

        if pipeline is None:
            pipeline = make_default_pipeline()

        viewport = Viewport(
            name=name,
            scene=scene,
            camera=camera,
            rect=rect,
            pipeline=pipeline,
        )
        camera.add_viewport(viewport)
        self.add_viewport(viewport)
        return viewport

    def viewport_at(self, x: float, y: float) -> "Viewport | None":
        """
        Find viewport at specified coordinates.

        Returns viewport with highest depth when overlapping.

        Args:
            x, y: Normalized coordinates [0..1], origin top-left.

        Returns:
            Viewport under cursor or None.
        """
        # Transform y: screen coordinates (top-down) -> OpenGL (bottom-up)
        ny = 1.0 - y

        vp_ptr = _display_viewport_at(self._tc_display_ptr, x, ny)
        if vp_ptr == 0:
            return None

        from termin.viewport import Viewport
        return Viewport._from_ptr(vp_ptr)

    def viewport_at_pixels(self, px: float, py: float) -> "Viewport | None":
        """
        Find viewport at specified pixel coordinates.

        Args:
            px, py: Pixel coordinates, origin top-left.

        Returns:
            Viewport under cursor or None.
        """
        vp_ptr = _display_viewport_at_screen(self._tc_display_ptr, px, py)
        if vp_ptr == 0:
            return None

        from termin.viewport import Viewport
        return Viewport._from_ptr(vp_ptr)

    def viewport_rect_to_pixels(self, viewport: "Viewport") -> tuple[int, int, int, int]:
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

    def make_current(self) -> None:
        """Make render context current."""
        _display_make_current(self._tc_display_ptr)

    def present(self) -> None:
        """Present rendered result (swap buffers)."""
        _display_swap_buffers(self._tc_display_ptr)
