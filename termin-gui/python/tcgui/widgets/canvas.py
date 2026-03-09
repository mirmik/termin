"""Canvas — zoomable, pannable image display widget with interaction hooks."""

from __future__ import annotations

from typing import Callable

import numpy as np

from tcbase import MouseButton
from tcgui.widgets.widget import Widget
from tcgui.widgets.events import MouseEvent, MouseWheelEvent
from tcgui.widgets.theme import current_theme as _t


class Canvas(Widget):
    """Zoomable, pannable image viewer with interaction callbacks.

    Displays a numpy RGBA image with built-in pan (middle mouse) and
    zoom (scroll wheel). Application-specific logic (painting, selection,
    tools) is implemented through callbacks.

    Usage::

        canvas = Canvas()
        canvas.set_image(rgba_array)   # (H, W, 4) uint8
        canvas.fit_in_view()

        canvas.on_canvas_mouse_down = lambda ix, iy, btn: ...
        canvas.on_render_overlay = lambda c, renderer: ...
    """

    def __init__(self):
        super().__init__()
        self.focusable = True

        # --- Image data ---
        self._image_data: np.ndarray | None = None
        self._image_texture = None  # GPUTextureHandle
        self._image_dirty: bool = False

        # --- Overlay data (optional second layer, e.g. stroke preview) ---
        self._overlay_data: np.ndarray | None = None
        self._overlay_texture = None
        self._overlay_dirty: bool = False
        self._overlay_dirty_rect: tuple[int, int, int, int] | None = None  # (x, y, w, h)

        # --- Viewport transform ---
        self._zoom: float = 1.0
        self._offset_x: float = 0.0
        self._offset_y: float = 0.0
        self.min_zoom: float = 0.01
        self.max_zoom: float = 100.0
        self.zoom_factor: float = 1.15

        # --- Pan state ---
        self._panning: bool = False
        self._pan_start_x: float = 0.0
        self._pan_start_y: float = 0.0
        self._pan_start_offset_x: float = 0.0
        self._pan_start_offset_y: float = 0.0

        # --- Style ---
        self.background_color: tuple = _t.bg_primary

        # --- Callbacks ---
        self.on_canvas_mouse_down: Callable | None = None
        self.on_canvas_mouse_move: Callable | None = None
        self.on_canvas_mouse_up: Callable | None = None
        self.on_zoom_changed: Callable | None = None
        self.on_render_overlay: Callable | None = None

    # ------------------------------------------------------------------
    # Image management
    # ------------------------------------------------------------------

    def set_image(self, data: np.ndarray | None) -> None:
        """Set or clear the displayed image.

        *data*: ``(H, W, 4)`` uint8 RGBA numpy array, or ``None`` to clear.
        """
        if data is not None:
            data = np.ascontiguousarray(data)
        self._image_data = data
        self._image_dirty = True

    def set_overlay(self, data: np.ndarray | None) -> None:
        """Set or clear the overlay image (drawn on top of the main image).

        *data*: ``(H, W, 4)`` uint8 RGBA numpy array, or ``None`` to clear.
        """
        if data is not None:
            data = np.ascontiguousarray(data)
        self._overlay_data = data
        self._overlay_dirty = True
        self._overlay_dirty_rect = None  # full upload

    def set_overlay_ref(self, data: np.ndarray | None) -> None:
        """Set overlay by reference (no copy). Caller must keep buffer alive.

        Use mark_overlay_dirty() for subsequent partial updates.
        """
        self._overlay_data = data
        self._overlay_dirty = True
        self._overlay_dirty_rect = None  # full upload on first set

    def mark_overlay_dirty(self, x0: int, y0: int, x1: int, y1: int) -> None:
        """Mark a region of the overlay as needing GPU re-upload.

        Coordinates are in image pixels: (x0, y0) top-left, (x1, y1) bottom-right.
        """
        if self._overlay_data is None:
            return
        h, w = self._overlay_data.shape[:2]
        x0 = max(0, x0)
        y0 = max(0, y0)
        x1 = min(w, x1)
        y1 = min(h, y1)
        if x1 <= x0 or y1 <= y0:
            return
        rw, rh = x1 - x0, y1 - y0
        new_rect = (x0, y0, rw, rh)

        if self._overlay_dirty and self._overlay_dirty_rect is None:
            return  # already marked for full upload

        if self._overlay_dirty and self._overlay_dirty_rect is not None:
            # union with existing
            ox, oy, ow, oh = self._overlay_dirty_rect
            ux = min(ox, x0)
            uy = min(oy, y0)
            uw = max(ox + ow, x0 + rw) - ux
            uh = max(oy + oh, y0 + rh) - uy
            self._overlay_dirty_rect = (ux, uy, uw, uh)
        else:
            self._overlay_dirty_rect = new_rect
        self._overlay_dirty = True

    @property
    def image_size(self) -> tuple[int, int] | None:
        """Return ``(width, height)`` of the current image, or ``None``."""
        if self._image_data is None:
            return None
        h, w = self._image_data.shape[:2]
        return (w, h)

    # ------------------------------------------------------------------
    # Viewport
    # ------------------------------------------------------------------

    @property
    def zoom(self) -> float:
        return self._zoom

    def set_zoom(self, value: float,
                 anchor_wx: float | None = None,
                 anchor_wy: float | None = None) -> None:
        """Set zoom level, optionally anchoring to a widget-space point."""
        if anchor_wx is not None and anchor_wy is not None:
            old_ix, old_iy = self.widget_to_image(anchor_wx, anchor_wy)
            self._zoom = max(self.min_zoom, min(value, self.max_zoom))
            self._offset_x = (anchor_wx - self.x) - old_ix * self._zoom
            self._offset_y = (anchor_wy - self.y) - old_iy * self._zoom
        else:
            cx = self.x + self.width / 2
            cy = self.y + self.height / 2
            old_ix, old_iy = self.widget_to_image(cx, cy)
            self._zoom = max(self.min_zoom, min(value, self.max_zoom))
            self._offset_x = self.width / 2 - old_ix * self._zoom
            self._offset_y = self.height / 2 - old_iy * self._zoom

        if self.on_zoom_changed:
            self.on_zoom_changed(self._zoom)

    def fit_in_view(self) -> None:
        """Auto-zoom and center image to fit in canvas bounds."""
        size = self.image_size
        if size is None:
            return
        img_w, img_h = size
        if img_w == 0 or img_h == 0:
            return
        if self.width <= 0 or self.height <= 0:
            return

        scale_x = self.width / img_w
        scale_y = self.height / img_h
        self._zoom = min(scale_x, scale_y) * 0.95
        self._offset_x = (self.width - img_w * self._zoom) / 2
        self._offset_y = (self.height - img_h * self._zoom) / 2

        if self.on_zoom_changed:
            self.on_zoom_changed(self._zoom)

    def center_on(self, ix: float, iy: float) -> None:
        """Center the viewport on image coordinate ``(ix, iy)``."""
        self._offset_x = self.width / 2 - ix * self._zoom
        self._offset_y = self.height / 2 - iy * self._zoom

    # ------------------------------------------------------------------
    # Coordinate transforms
    # ------------------------------------------------------------------

    def widget_to_image(self, wx: float, wy: float) -> tuple[float, float]:
        """Convert widget-space coordinates to image-space coordinates."""
        ix = (wx - self.x - self._offset_x) / self._zoom
        iy = (wy - self.y - self._offset_y) / self._zoom
        return (ix, iy)

    def image_to_widget(self, ix: float, iy: float) -> tuple[float, float]:
        """Convert image-space coordinates to widget-space coordinates."""
        wx = self.x + self._offset_x + ix * self._zoom
        wy = self.y + self._offset_y + iy * self._zoom
        return (wx, wy)

    # ------------------------------------------------------------------
    # Texture management
    # ------------------------------------------------------------------

    def _sync_textures(self, renderer) -> None:
        graphics = renderer._graphics

        if self._image_dirty:
            self._image_dirty = False
            if self._image_data is None:
                if self._image_texture is not None:
                    self._image_texture.delete()
                    self._image_texture = None
            else:
                h, w = self._image_data.shape[:2]
                if (self._image_texture is not None
                        and self._image_texture.get_width() == w
                        and self._image_texture.get_height() == h):
                    graphics.update_texture(
                        self._image_texture, self._image_data, w, h, 4)
                else:
                    if self._image_texture is not None:
                        self._image_texture.delete()
                    self._image_texture = graphics.create_texture(
                        self._image_data, w, h, channels=4,
                        mipmap=False, clamp=True)

        if self._overlay_dirty:
            self._overlay_dirty = False
            dirty_rect = self._overlay_dirty_rect
            self._overlay_dirty_rect = None
            if self._overlay_data is None:
                if self._overlay_texture is not None:
                    self._overlay_texture.delete()
                    self._overlay_texture = None
            else:
                h, w = self._overlay_data.shape[:2]
                if (self._overlay_texture is not None
                        and self._overlay_texture.get_width() == w
                        and self._overlay_texture.get_height() == h):
                    if (dirty_rect is not None
                            and hasattr(graphics, 'update_texture_region')):
                        rx, ry, rw, rh = dirty_rect
                        graphics.update_texture_region(
                            self._overlay_texture, self._overlay_data,
                            rx, ry, rw, rh, 4)
                    else:
                        graphics.update_texture(
                            self._overlay_texture, self._overlay_data, w, h, 4)
                else:
                    if self._overlay_texture is not None:
                        self._overlay_texture.delete()
                    self._overlay_texture = graphics.create_texture(
                        self._overlay_data, w, h, channels=4,
                        mipmap=False, clamp=True)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self, renderer: 'UIRenderer'):
        # Background
        renderer.draw_rect(self.x, self.y, self.width, self.height,
                           self.background_color)

        # Clip to canvas bounds
        renderer.begin_clip(self.x, self.y, self.width, self.height)

        # Upload / update GPU textures
        self._sync_textures(renderer)

        # Compute screen-space image bounds
        size = self.image_size
        if size is not None and self._image_texture is not None:
            img_w, img_h = size
            sx = self.x + self._offset_x
            sy = self.y + self._offset_y
            sw = img_w * self._zoom
            sh = img_h * self._zoom

            renderer.draw_image(sx, sy, sw, sh, self._image_texture)

            # Overlay
            if self._overlay_texture is not None:
                renderer.draw_image(sx, sy, sw, sh, self._overlay_texture)

        # Application overlay callback
        if self.on_render_overlay:
            self.on_render_overlay(self, renderer)

        renderer.end_clip()

    # ------------------------------------------------------------------
    # Mouse events
    # ------------------------------------------------------------------

    def on_mouse_down(self, event: MouseEvent) -> bool:
        # Middle button: pan
        if event.button == MouseButton.MIDDLE:
            self._panning = True
            self._pan_start_x = event.x
            self._pan_start_y = event.y
            self._pan_start_offset_x = self._offset_x
            self._pan_start_offset_y = self._offset_y
            return True

        # Forward to application
        if self.on_canvas_mouse_down:
            ix, iy = self.widget_to_image(event.x, event.y)
            self.on_canvas_mouse_down(ix, iy, event.button, event.mods)
            return True

        return False

    def on_mouse_move(self, event: MouseEvent):
        if self._panning:
            dx = event.x - self._pan_start_x
            dy = event.y - self._pan_start_y
            self._offset_x = self._pan_start_offset_x + dx
            self._offset_y = self._pan_start_offset_y + dy
            return

        if self.on_canvas_mouse_move:
            ix, iy = self.widget_to_image(event.x, event.y)
            self.on_canvas_mouse_move(ix, iy)

    def on_mouse_up(self, event: MouseEvent):
        if self._panning:
            self._panning = False
            return

        if self.on_canvas_mouse_up:
            ix, iy = self.widget_to_image(event.x, event.y)
            self.on_canvas_mouse_up(ix, iy)

    def on_mouse_wheel(self, event: MouseWheelEvent) -> bool:
        if self.image_size is None:
            return False

        # Zoom anchored to cursor position
        old_ix, old_iy = self.widget_to_image(event.x, event.y)
        factor = self.zoom_factor if event.dy > 0 else 1.0 / self.zoom_factor
        self._zoom = max(self.min_zoom, min(self._zoom * factor, self.max_zoom))

        # Adjust offset to keep same image point under cursor
        self._offset_x = (event.x - self.x) - old_ix * self._zoom
        self._offset_y = (event.y - self.y) - old_iy * self._zoom

        if self.on_zoom_changed:
            self.on_zoom_changed(self._zoom)

        return True
