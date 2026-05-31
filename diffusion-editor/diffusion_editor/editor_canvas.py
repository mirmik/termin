"""EditorCanvas — extends tcgui Canvas with brush/mask painting and rect modes."""

from __future__ import annotations

import logging

import numpy as np

from tcbase import Key, MouseButton, Mods
from tcgui.widgets.canvas import Canvas
from tcgui.widgets.events import KeyEvent

from .layer_stack import LayerStack
from .layer import Layer
from .tool import LamaTool, InstructTool
from .brush import Brush, BrushToolMode
from .canvas_geometry import (
    canvas_to_layer_point,
    clip_canvas_rect,
    clip_layer_local_rect,
    union_rect,
    visible_layer_rect,
)
from .canvas_composite import CanvasCompositeBridge
from .canvas_edit_session import CanvasEditSession
from .canvas_overlay import CanvasOverlayBridge
from .canvas_paint_stroke import PaintStrokeBuffer
from .canvas_rect_drag import CanvasRectDrag
from .canvas_smudge import SmudgeStrokeBuffer
from .canvas_tools import create_canvas_tools
from .soft_mask_stroke import SoftMaskBrush, apply_dab, apply_line

logger = logging.getLogger(__name__)


class EditorCanvas(Canvas):
    """Zoomable image canvas with brush painting, mask painting, and rect tools."""

    def __init__(self, layer_stack: LayerStack, *,
                 gpu_compositing: bool = True,
                 ctx=None):
        super().__init__()
        self.background_color = (0.08, 0.08, 0.10, 1.0)
        self._layer_stack = layer_stack
        self._composite_bridge = CanvasCompositeBridge(
            layer_stack,
            gpu_compositing=gpu_compositing,
            graphics=ctx,
            set_image=self.set_image,
        )

        self.brush = Brush()
        self._brush_tool_mode = BrushToolMode.PAINT
        self._stroke_tools = create_canvas_tools()
        self._active_stroke_tool = self._stroke_tools[self._brush_tool_mode]
        self._brush_eraser = False
        self._mask_brush_size = 50
        self._mask_brush_hardness = 0.4
        self._mask_brush_flow = 1.0
        self._mask_eraser = False
        self._overlay_bridge = CanvasOverlayBridge(
            layer_stack,
            set_overlay=self.set_overlay,
        )

        # Selection painting mode
        self._selection_mode = False
        self._sel_brush_size = 50
        self._sel_brush_hardness = 0.4
        self._sel_brush_flow = 1.0
        self._selection_eraser = False

        # Selection rectangle mode
        self._selection_rect_drag = CanvasRectDrag(
            include_end_pixel=True,
            min_size=1,
        )

        # Rectangle modes
        self._patch_rect_drag = CanvasRectDrag(
            include_end_pixel=False,
            min_size=2,
        )
        self._show_patch_rect = True

        # Stroke buffer (MAX blending during one stroke)
        self._paint_stroke = PaintStrokeBuffer()

        self._edit_session = CanvasEditSession()
        self._mask_erase_stroke: np.ndarray | None = None
        self._mask_erase_dirty: tuple[int, int, int, int] | None = None
        self._smudge_stroke = SmudgeStrokeBuffer()

        # Callbacks
        self.on_mouse_moved: callable = None
        self.on_color_picked: callable = None
        self.on_patch_rect_drawn: callable = None
        self.on_selection_rect_drawn: callable = None
        self.on_edit_begin: callable = None  # (label: str, layer: Layer, target: str)
        self.on_edit_end: callable = None  # (layer: Layer, target: str, dirty_rect)

        # Wire layer stack
        layer_stack.on_changed = self._on_stack_changed

        # Wire canvas callbacks for painting
        self.on_canvas_mouse_down = self._handle_mouse_down
        self.on_canvas_mouse_move = self._handle_mouse_move
        self.on_canvas_mouse_up = self._handle_mouse_up
        self.on_render_overlay = self._render_overlay

    # ------------------------------------------------------------------
    # Layer stack integration
    # ------------------------------------------------------------------

    @property
    def _composite(self) -> np.ndarray | None:
        return self._composite_bridge.composite

    @_composite.setter
    def _composite(self, composite: np.ndarray | None) -> None:
        self._composite_bridge.composite = composite

    @property
    def _gpu_compositing(self) -> bool:
        return self._composite_bridge.gpu_compositing

    @_gpu_compositing.setter
    def _gpu_compositing(self, enabled: bool) -> None:
        self._composite_bridge.gpu_compositing = enabled

    @property
    def _gpu_compositor(self):
        return self._composite_bridge.gpu_compositor

    @_gpu_compositor.setter
    def _gpu_compositor(self, compositor) -> None:
        self._composite_bridge.gpu_compositor = compositor

    @property
    def _composite_stale(self) -> bool:
        return self._composite_bridge.composite_stale

    @_composite_stale.setter
    def _composite_stale(self, stale: bool) -> None:
        self._composite_bridge.composite_stale = stale

    @property
    def _show_mask(self) -> bool:
        return self._overlay_bridge.show_mask

    def _on_stack_changed(self):
        self._composite_bridge.rebuild()
        self._update_composite()

    def _update_composite(self):
        composite = self._composite_bridge.update_composite()
        if composite is None and self._composite_bridge.using_gpu:
            # Keep Canvas.image_size in sync for fit/zoom math in GPU path.
            w, h = self._layer_stack.width, self._layer_stack.height
            if w > 0 and h > 0:
                if self._image_data is None or self._image_data.shape[:2] != (h, w):
                    self._image_data = np.empty((h, w, 4), dtype=np.uint8)
            else:
                self._image_data = None
        self._overlay_bridge.clear()
        self._update_overlay()

    def _update_overlay(self):
        self._overlay_bridge.rebuild()

    def _update_stroke_region(self, layer, dirty):
        """Apply current paint stroke preview into the layer dirty region."""
        if dirty is None or layer is None:
            return
        dirty = self._paint_stroke.apply_region(layer.image, dirty)
        if dirty is None:
            return
        self._refresh_modified_layer_rect(layer, dirty)

    def _update_mask_overlay_region(self, layer, dirty):
        """Update mask overlay after mask painting."""
        self._overlay_bridge.update_mask_region(layer, dirty)

    def _update_mask_overlay_region_preview(self, layer, dirty, preview_mask):
        """Update overlay alpha from a provided mask preview region."""
        self._overlay_bridge.update_mask_region_preview(layer, dirty, preview_mask)

    def _preview_mask_erase_region(self, layer, dirty):
        """Preview erase on composite without modifying layer.image."""
        if dirty is None or self._mask_erase_stroke is None:
            return
        local_rect, canvas_rect = self._clip_layer_local_rect(layer, dirty)
        if local_rect is None:
            return
        x0, y0, x1, y1 = local_rect
        erase = self._mask_erase_stroke[y0:y1, x0:x1]
        self._composite_bridge.preview_erased_layer_rect(
            layer,
            local_rect,
            canvas_rect,
            erase,
        )

    def _erase_layer_rect(self, layer, rect, erase):
        """Erase layer.image alpha by erase mask within rect, update composite.

        erase can be float32 [0..1] or uint8 [0..255].
        """
        if rect is None or erase is None:
            return
        local_rect, canvas_rect = self._clip_layer_local_rect(layer, rect)
        if local_rect is None:
            return
        x0, y0, x1, y1 = local_rect
        if erase.dtype == np.uint8:
            erase = erase.astype(np.float32) / 255.0
        la = layer.image[y0:y1, x0:x1, 3].astype(np.float32)
        layer.image[y0:y1, x0:x1, 3] = np.clip(
            la * (1.0 - erase), 0, 255).astype(np.uint8)

        self._composite_bridge.refresh_modified_layer_rect(
            layer,
            local_rect,
            canvas_rect,
        )

    def get_composite(self) -> np.ndarray | None:
        return self._composite_bridge.get_composite()

    def get_composite_below(self, layer: Layer) -> np.ndarray | None:
        return self._composite_bridge.get_composite_below(layer)

    def view_center_image(self) -> tuple[int, int]:
        cx = self.x + self.width / 2
        cy = self.y + self.height / 2
        ix, iy = self.widget_to_image(cx, cy)
        return int(ix), int(iy)

    # ------------------------------------------------------------------
    # Setters
    # ------------------------------------------------------------------

    def set_mask_brush(self, size: int, hardness: float, flow: float = 1.0):
        self._mask_brush_size = size
        self._mask_brush_hardness = hardness
        self._mask_brush_flow = max(0.0, min(flow, 1.0))
        if self._brush_tool_mode not in (BrushToolMode.MASK, BrushToolMode.MASK_ERASER):
            self.set_brush_tool(BrushToolMode.MASK)

    def set_mask_eraser(self, eraser: bool):
        self._mask_eraser = eraser
        self.set_brush_tool(
            BrushToolMode.MASK_ERASER if eraser else BrushToolMode.MASK)

    def set_brush_eraser(self, eraser: bool):
        self.set_brush_tool(BrushToolMode.ERASER if eraser else BrushToolMode.PAINT)

    def set_brush_tool(self, mode: BrushToolMode | str):
        self._brush_tool_mode = BrushToolMode(mode)
        self._brush_eraser = self._brush_tool_mode == BrushToolMode.ERASER
        self._mask_eraser = self._brush_tool_mode == BrushToolMode.MASK_ERASER
        self._active_stroke_tool = self._stroke_tools[self._brush_tool_mode]

    @property
    def brush_tool_mode(self) -> BrushToolMode:
        return self._brush_tool_mode

    def set_selection_mode(self, on: bool):
        self._selection_mode = on
        self.cursor = "cross" if on else ""

    def set_selection_brush(self, size: int, hardness: float, flow: float = 1.0):
        self._sel_brush_size = size
        self._sel_brush_hardness = hardness
        self._sel_brush_flow = max(0.0, min(flow, 1.0))

    def set_selection_eraser(self, eraser: bool):
        self._selection_eraser = eraser

    def set_selection_rect_mode(self, on: bool):
        self._selection_rect_drag.set_enabled(on)
        self.cursor = "cross" if on else ""

    def set_show_mask(self, show: bool):
        self._overlay_bridge.show_mask = show
        self._overlay_bridge.clear()
        self._update_overlay()

    def set_show_selection(self, show: bool):
        self._overlay_bridge.show_selection = show
        self._update_overlay()

    def set_patch_rect_mode(self, on: bool):
        self._patch_rect_drag.set_enabled(on)
        self.cursor = "cross" if on else ""

    def set_show_patch_rect(self, show: bool):
        self._show_patch_rect = show

    # ------------------------------------------------------------------
    # Mask painting
    # ------------------------------------------------------------------

    def _mask_brush(self) -> SoftMaskBrush:
        return SoftMaskBrush(
            size=self._mask_brush_size,
            hardness=self._mask_brush_hardness,
            flow=self._mask_brush_flow,
        )

    def _selection_brush(self) -> SoftMaskBrush:
        return SoftMaskBrush(
            size=self._sel_brush_size,
            hardness=self._sel_brush_hardness,
            flow=self._sel_brush_flow,
        )

    def _dab_mask(self, mask: np.ndarray, cx: int, cy: int, *, erase: bool | None = None):
        """Returns (dirty_rect, stamp) or (None, None).

        mask is float32 [0..1], same for returned stamp.
        """
        if erase is None:
            erase = self._mask_eraser
        return apply_dab(mask, cx, cy, self._mask_brush(), erase=erase)

    def _stroke_mask_line(self, mask: np.ndarray,
                          x0: int, y0: int, x1: int, y1: int,
                          *, erase: bool | None = None):
        """Draw smooth mask stroke segment. Returns (dirty_rect, stamp) or (None, None).

        mask is float32 [0..1], same for returned stamp.
        """
        if erase is None:
            erase = self._mask_eraser
        return apply_line(mask, x0, y0, x1, y1, self._mask_brush(), erase=erase)

    @staticmethod
    def _union_rect(a, b):
        return union_rect(a, b)

    def _canvas_to_layer_point(self, layer, x: int, y: int) -> tuple[int, int]:
        return canvas_to_layer_point(layer, x, y)

    def _clip_canvas_rect(self, rect):
        return clip_canvas_rect(
            rect,
            self._layer_stack.width,
            self._layer_stack.height,
        )

    def _visible_layer_rect(self, layer):
        return visible_layer_rect(
            layer,
            self._layer_stack.width,
            self._layer_stack.height,
        )

    def _can_edit_layer(self, layer) -> bool:
        return (
            layer is not None
            and self._layer_stack.is_layer_visible_for_composition(layer)
        )

    def _clip_layer_local_rect(self, layer, rect):
        return clip_layer_local_rect(
            layer,
            rect,
            self._layer_stack.width,
            self._layer_stack.height,
        )

    # ------------------------------------------------------------------
    # Selection painting
    # ------------------------------------------------------------------

    def _dab_selection(self, cx: int, cy: int):
        """Paint a selection dab at image coordinates. Returns (dirty_rect, stamp)."""
        d = self._sel_brush_size
        if d < 1:
            return None, None
        sel = self._layer_stack.selection.data
        if sel.size == 0:
            return None, None
        return apply_dab(
            sel,
            cx,
            cy,
            self._selection_brush(),
            erase=self._selection_eraser,
        )

    def _stroke_selection_line(self, x0: int, y0: int, x1: int, y1: int):
        """Paint a selection stroke segment. Returns (dirty_rect, stamp) or (None, None)."""
        sel = self._layer_stack.selection.data
        if sel.size == 0:
            return None, None
        d = self._sel_brush_size
        if d < 1:
            return None, None
        return apply_line(
            sel,
            x0,
            y0,
            x1,
            y1,
            self._selection_brush(),
            erase=self._selection_eraser,
        )

    # ------------------------------------------------------------------
    # Mask erase (preview)
    # ------------------------------------------------------------------

    def _begin_mask_erase(self, layer):
        if layer is None:
            return
        h, w = layer.height, layer.width
        if h == 0 or w == 0:
            return
        self._mask_erase_stroke = np.zeros((h, w), dtype=np.float32)
        self._mask_erase_dirty = None

    # ------------------------------------------------------------------
    # Stroke buffer for brush painting
    # ------------------------------------------------------------------

    def _begin_stroke(self, layer=None):
        if layer is None:
            layer = self._layer_stack.active_layer
        if layer is None:
            return
        if self._brush_eraser:
            self._paint_stroke.clear()
            return
        self._paint_stroke.begin(layer.image, tuple(self.brush.color))

    def _end_stroke(self):
        layer = self._layer_stack.active_layer
        dirty = self._paint_stroke.live_dirty_rect
        if layer is not None and dirty is not None:
            self._layer_stack.mark_layer_dirty(
                layer, layer.local_rect_to_canvas(dirty))
        self._paint_stroke.clear()
        self._overlay_bridge.clear()
        self._update_overlay()

    # ------------------------------------------------------------------
    # Eraser
    # ------------------------------------------------------------------

    def _composite_rect_below(self, target_layer, dy0, dy1, dx0, dx1):
        return self._composite_bridge.composite_rect_below(
            target_layer, dy0, dy1, dx0, dx1)

    def _erase_dab(self, layer, cx: int, cy: int):
        stamp = self.brush._alpha_stamp
        sh, sw = stamp.shape[:2]
        ih, iw = layer.image.shape[:2]

        x0 = cx - sw // 2
        y0 = cy - sh // 2
        sx0, sy0 = max(0, -x0), max(0, -y0)
        sx1, sy1 = min(sw, iw - x0), min(sh, ih - y0)
        dx0, dy0b = max(0, x0), max(0, y0)
        dx1, dy1 = dx0 + (sx1 - sx0), dy0b + (sy1 - sy0)
        if dx0 >= dx1 or dy0b >= dy1:
            return None

        erase = (stamp[sy0:sy1, sx0:sx1]
                 * (self.brush.color[3] / 255.0)
                 * self.brush.flow)
        la = layer.image[dy0b:dy1, dx0:dx1, 3].astype(np.float32)
        layer.image[dy0b:dy1, dx0:dx1, 3] = np.clip(
            la * (1.0 - erase), 0, 255).astype(np.uint8)

        dirty = (dx0, dy0b, dx1, dy1)
        self._refresh_modified_layer_rect(layer, dirty)
        return dirty

    def _erase_stroke_line(self, layer, x0: int, y0: int, x1: int, y1: int):
        ih, iw = layer.image.shape[:2]
        radius = self.brush.size / 2.0
        stamp = self.brush._alpha_stamp

        bx0 = max(0, int(min(x0, x1) - radius))
        by0 = max(0, int(min(y0, y1) - radius))
        bx1 = min(iw, int(max(x0, x1) + radius) + 1)
        by1 = min(ih, int(max(y0, y1) + radius) + 1)
        if bx0 >= bx1 or by0 >= by1:
            return None

        sdx = float(x1 - x0)
        sdy = float(y1 - y0)
        seg_len_sq = sdx * sdx + sdy * sdy

        if seg_len_sq < 0.5:
            return self._erase_dab(layer, x0, y0)

        yy, xx = np.mgrid[by0:by1, bx0:bx1]
        xx = xx.astype(np.float32)
        yy = yy.astype(np.float32)

        t = ((xx - x0) * sdx + (yy - y0) * sdy) / seg_len_sq
        np.clip(t, 0.0, 1.0, out=t)
        cx = x0 + t * sdx
        cy = y0 + t * sdy
        dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)

        if self.brush.hardness >= 1.0:
            erase = (dist <= radius).astype(np.float32)
        else:
            inner = radius * self.brush.hardness
            erase = np.clip(
                (radius - dist) / max(radius - inner, 0.001), 0.0, 1.0)

        erase *= (self.brush.color[3] / 255.0) * self.brush.flow
        la = layer.image[by0:by1, bx0:bx1, 3].astype(np.float32)
        layer.image[by0:by1, bx0:bx1, 3] = np.clip(
            la * (1.0 - erase), 0, 255).astype(np.uint8)

        dirty = (bx0, by0, bx1, by1)
        self._refresh_modified_layer_rect(layer, dirty)
        return dirty

    # ------------------------------------------------------------------
    # Smudge
    # ------------------------------------------------------------------

    def _begin_smudge(self, layer, x: int, y: int):
        self._smudge_stroke.begin(layer.image, self.brush, x, y)

    def _end_smudge(self):
        self._smudge_stroke.clear()

    def _refresh_modified_layer_rect(self, layer, rect):
        local_rect, canvas_rect = self._clip_layer_local_rect(layer, rect)
        if local_rect is None:
            return
        self._composite_bridge.refresh_modified_layer_rect(
            layer,
            local_rect,
            canvas_rect,
        )

    def _refresh_layer_transform(self, layer, dirty_canvas_rect):
        self._composite_bridge.refresh_layer_transform(layer, dirty_canvas_rect)

    def _smudge_dab(self, layer, cx: int, cy: int):
        dirty = self._smudge_stroke.dab(layer.image, self.brush, cx, cy)
        self._refresh_modified_layer_rect(layer, dirty)
        return dirty

    def _smudge_stroke_line(self, layer, x0: int, y0: int, x1: int, y1: int):
        dirty = self._smudge_stroke.line(
            layer.image,
            self.brush,
            x0,
            y0,
            x1,
            y1,
        )
        self._refresh_modified_layer_rect(layer, dirty)
        return dirty

    # ------------------------------------------------------------------
    # Mouse handlers (called from Canvas callbacks)
    # ------------------------------------------------------------------

    def _handle_mouse_down(self, ix: float, iy: float, button, mods: int = 0):
        from tcbase import Mods
        ix, iy = int(ix), int(iy)

        # Ctrl+LMB or RMB — eyedropper
        if button == MouseButton.RIGHT or (
                button == MouseButton.LEFT and (mods & Mods.CTRL.value)):
            self._pick_color(ix, iy)
            return

        if button == MouseButton.LEFT:
            layer = self._layer_stack.active_layer
            if layer is None:
                return

            # Selection rect mode
            if self._selection_rect_drag.begin(ix, iy):
                return

            # Selection painting
            if self._selection_mode:
                self._edit_session.begin(
                    label="Selection Stroke",
                    target="selection",
                    layer=None,
                    pos=(ix, iy),
                )
                if self.on_edit_begin:
                    self.on_edit_begin("Selection Stroke", None, "selection")
                dirty, _stamp = self._dab_selection(ix, iy)
                self._edit_session.add_dirty(dirty)
                self._update_overlay()
                return

            if not self._can_edit_layer(layer):
                return

            # Patch rect mode
            if self._patch_rect_drag.begin(ix, iy):
                return

            # Painting
            tool = self._active_stroke_tool
            self._edit_session.begin(
                label=tool.label,
                target=tool.target,
                layer=layer,
                pos=(ix, iy),
            )
            if self.on_edit_begin:
                self.on_edit_begin(tool.label, layer, tool.target)
            dirty = tool.begin(self, layer, ix, iy)
            self._edit_session.add_dirty(dirty)

    def _handle_mouse_move(self, ix: float, iy: float):
        ixi, iyi = int(ix), int(iy)

        if self._selection_rect_drag.move(ixi, iyi):
            return

        if self._patch_rect_drag.move(ixi, iyi):
            return

        if self._edit_session.active:
            if self._edit_session.target == "selection":
                if self._edit_session.last_pos:
                    lx, ly = self._edit_session.last_pos
                    dirty, _stamp = self._stroke_selection_line(lx, ly, ixi, iyi)
                else:
                    dirty, _stamp = self._dab_selection(ixi, iyi)
                self._edit_session.add_dirty(dirty)
                self._update_overlay()
                self._edit_session.move_to((ixi, iyi))
                return
            layer = self._layer_stack.active_layer
            if layer is None:
                return
            dirty = self._active_stroke_tool.move(
                self, layer, self._edit_session.last_pos, ixi, iyi)
            self._edit_session.add_dirty(dirty)
            self._edit_session.move_to((ixi, iyi))

        if self.on_mouse_moved:
            self.on_mouse_moved(ixi, iyi)

    def _handle_mouse_up(self, ix: float, iy: float):
        ixi, iyi = int(ix), int(iy)

        if self._selection_rect_drag.dragging:
            result = self._selection_rect_drag.finish(ixi, iyi)
            self.cursor = ""
            if result is not None and self.on_selection_rect_drawn:
                self.on_selection_rect_drawn(*result.rect)
            return

        if self._patch_rect_drag.dragging:
            result = self._patch_rect_drag.finish(ixi, iyi)
            self.cursor = ""
            if result is not None and self.on_patch_rect_drawn:
                self.on_patch_rect_drawn(*result.rect)
            return

        if self._edit_session.active:
            if self._edit_session.target == "selection":
                self._update_overlay()
                if self.on_edit_end:
                    self.on_edit_end(None, "selection", self._edit_session.dirty_rect)
            else:
                layer = self._layer_stack.active_layer
                self._active_stroke_tool.end(self, layer)
                self._overlay_bridge.clear()
                self._update_overlay()
                if self.on_edit_end:
                    self.on_edit_end(
                        self._edit_session.layer,
                        self._edit_session.target,
                        self._edit_session.dirty_rect,
                    )
            self._edit_session.clear()

    def _pick_color(self, ix: int, iy: int):
        if self._layer_stack.width == 0 or self._layer_stack.height == 0:
            return
        composite = self._layer_stack.composite()
        h, w = composite.shape[:2]
        if 0 <= ix < w and 0 <= iy < h:
            r, g, b, a = composite[iy, ix]
            if self.on_color_picked:
                self.on_color_picked(int(r), int(g), int(b), int(a))

    # ------------------------------------------------------------------
    # Rendering (GPU compositing path)
    # ------------------------------------------------------------------

    def render(self, renderer):
        # Borrow the compositor's display tex directly. Since
        # EditorWindow threads the process-global tgfx2 context into
        # both the compositor and the renderer, the handle is valid on
        # both sides — no GL-id wrap, no raw-GL detour that only worked
        # on OpenGL. On Vulkan the raw-GL path returned 0 and left the
        # canvas black; this shared-device path draws a real image on
        # both backends.
        borrowed_display_tex = None
        if self._composite_bridge.using_gpu:
            # During mask erase preview, _preview_mask_erase_region
            # modifies self._composite on CPU and calls set_image() —
            # let base Canvas handle that upload instead of overriding
            # with the GPU display tex.
            in_mask_erase_preview = self._mask_erase_stroke is not None

            if not in_mask_erase_preview:
                tex = self._composite_bridge.display_tex
                w, h = self._composite_bridge.display_size()
                if tex is not None and w > 0 and h > 0:
                    if self._image_texture is not None and self._image_tex_size is not None:
                        renderer.destroy_texture(self._image_texture)
                    self._image_texture = tex
                    self._image_tex_size = None  # non-owning borrow
                    self._image_dirty = False
                    if self._image_data is None or self._image_data.shape[:2] != (h, w):
                        self._image_data = np.empty((h, w, 4), dtype=np.uint8)
                    borrowed_display_tex = tex
            else:
                if self._image_texture is not None and self._image_tex_size is None:
                    self._image_texture = None
        try:
            super().render(renderer)
        finally:
            # Null out the borrowed reference so Canvas.dispose / texture
            # updates don't try to destroy a texture owned by the compositor.
            if borrowed_display_tex is not None and self._image_texture is borrowed_display_tex:
                self._image_texture = None

    # ------------------------------------------------------------------
    # Keyboard
    # ------------------------------------------------------------------

    def on_key_down(self, event: KeyEvent) -> bool:
        if event.key == Key.RBRACKET:
            self.brush.set_size(self.brush.size + 5)
            return True
        elif event.key == Key.LBRACKET:
            self.brush.set_size(self.brush.size - 5)
            return True
        return super().on_key_down(event)

    # ------------------------------------------------------------------
    # Render overlay (rectangles via renderer)
    # ------------------------------------------------------------------

    def _render_overlay(self, canvas, renderer):
        layer = self._layer_stack.active_layer

        # Active layer bounds. Drawn in canvas coordinates, so local-sized
        # layers and moved layers remain visually discoverable.
        if layer is not None and layer.width > 0 and layer.height > 0:
            ix0, iy0, ix1, iy1 = layer.bounds
            wx0, wy0 = canvas.image_to_widget(ix0, iy0)
            wx1, wy1 = canvas.image_to_widget(ix1, iy1)
            w = wx1 - wx0
            h = wy1 - wy0
            if w != 0 and h != 0:
                renderer.draw_rect_outline(wx0, wy0, w, h,
                                           (0.0, 0.0, 0.0, 0.85), 3.0)
                renderer.draw_rect_outline(wx0, wy0, w, h,
                                           (1.0, 1.0, 1.0, 0.95), 1.0)

        # Selection rectangle (cyan)
        rect = self._selection_rect_drag.preview_rect()
        if rect is not None:
            if rect:
                ix0, iy0, ix1, iy1 = rect
                wx0, wy0 = canvas.image_to_widget(ix0, iy0)
                wx1, wy1 = canvas.image_to_widget(ix1, iy1)
                renderer.draw_rect(wx0, wy0, wx1 - wx0, wy1 - wy0,
                                   (0.0, 0.8, 1.0, 0.12))
                renderer.draw_rect_outline(wx0, wy0, wx1 - wx0, wy1 - wy0,
                                           (0.0, 0.8, 1.0, 0.7), 2.0)

        # Patch rectangle (green outline)
        if self._show_patch_rect and layer is not None:
            rect = self._patch_rect_drag.preview_rect()
            if rect is None and layer.patch_rect:
                rect = layer.local_rect_to_canvas(layer.patch_rect)
            if rect:
                ix0, iy0, ix1, iy1 = rect
                wx0, wy0 = canvas.image_to_widget(ix0, iy0)
                wx1, wy1 = canvas.image_to_widget(ix1, iy1)
                renderer.draw_rect_outline(wx0, wy0, wx1 - wx0, wy1 - wy0,
                                           (0.2, 0.78, 0.31, 0.8), 2.0)

    def dispose(self):
        """Release GPU resources held by the canvas compositor."""
        self._composite_bridge.dispose()
