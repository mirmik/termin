"""Brush-like canvas tools used by EditorCanvas."""

from __future__ import annotations

from .brush import BrushToolMode
from .canvas_image_erase import erase_alpha_region, erase_dab, erase_line


class CanvasStrokeTool:
    mode: BrushToolMode
    label: str
    target: str

    def begin(self, canvas, layer, x: int, y: int):
        raise NotImplementedError

    def move(self, canvas, layer, last_pos: tuple[int, int] | None, x: int, y: int):
        raise NotImplementedError

    def end(self, canvas, layer):
        pass


class PaintTool(CanvasStrokeTool):
    mode = BrushToolMode.PAINT
    label = "Paint Stroke"
    target = "image"

    def begin(self, canvas, layer, x: int, y: int):
        x, y = canvas._canvas_to_layer_point(layer, x, y)
        canvas._paint_stroke.begin(layer.image, tuple(canvas.brush.color))
        stroke_mask = canvas._paint_stroke.mask
        if stroke_mask is None:
            return None
        dirty = canvas.brush.dab_to_mask(stroke_mask, x, y)
        self._apply_region(canvas, layer, dirty)
        return dirty

    def move(self, canvas, layer, last_pos, x: int, y: int):
        stroke_mask = canvas._paint_stroke.mask
        if stroke_mask is None:
            return None
        x, y = canvas._canvas_to_layer_point(layer, x, y)
        if last_pos:
            lx, ly = canvas._canvas_to_layer_point(layer, *last_pos)
            dirty = canvas.brush.stroke_to_mask(stroke_mask, lx, ly, x, y)
        else:
            dirty = canvas.brush.dab_to_mask(stroke_mask, x, y)
        self._apply_region(canvas, layer, dirty)
        return dirty

    def end(self, canvas, layer):
        dirty = canvas._paint_stroke.live_dirty_rect
        if layer is not None and dirty is not None:
            canvas._layer_stack.mark_layer_dirty(
                layer,
                layer.local_rect_to_canvas(dirty),
            )
        canvas._paint_stroke.clear()
        canvas._overlay_bridge.clear()
        canvas._update_overlay()

    def _apply_region(self, canvas, layer, dirty):
        if dirty is None or layer is None:
            return
        dirty = canvas._paint_stroke.apply_region(layer.image, dirty)
        if dirty is None:
            return
        canvas._refresh_modified_layer_rect(layer, dirty)


class EraserTool(CanvasStrokeTool):
    mode = BrushToolMode.ERASER
    label = "Erase Stroke"
    target = "image"

    def begin(self, canvas, layer, x: int, y: int):
        canvas._paint_stroke.clear()
        x, y = canvas._canvas_to_layer_point(layer, x, y)
        dirty = erase_dab(layer.image, canvas.brush, x, y)
        canvas._refresh_modified_layer_rect(layer, dirty)
        return dirty

    def move(self, canvas, layer, last_pos, x: int, y: int):
        x, y = canvas._canvas_to_layer_point(layer, x, y)
        if last_pos:
            lx, ly = canvas._canvas_to_layer_point(layer, *last_pos)
            dirty = erase_line(layer.image, canvas.brush, lx, ly, x, y)
        else:
            dirty = erase_dab(layer.image, canvas.brush, x, y)
        canvas._refresh_modified_layer_rect(layer, dirty)
        return dirty

    def end(self, canvas, layer):
        if layer is not None:
            canvas._layer_stack.mark_layer_dirty(layer)


class SmudgeTool(CanvasStrokeTool):
    mode = BrushToolMode.SMUDGE
    label = "Smudge Stroke"
    target = "image"

    def __init__(self):
        self._dirty_rect = None

    def begin(self, canvas, layer, x: int, y: int):
        self._dirty_rect = None
        x, y = canvas._canvas_to_layer_point(layer, x, y)
        canvas._smudge_stroke.begin(layer.image, canvas.brush, x, y)
        return None

    def move(self, canvas, layer, last_pos, x: int, y: int):
        if not last_pos:
            return None
        lx, ly = canvas._canvas_to_layer_point(layer, *last_pos)
        x, y = canvas._canvas_to_layer_point(layer, x, y)
        dirty = canvas._smudge_stroke.line(
            layer.image,
            canvas.brush,
            lx,
            ly,
            x,
            y,
        )
        canvas._refresh_modified_layer_rect(layer, dirty)
        self._dirty_rect = canvas._union_rect(self._dirty_rect, dirty)
        return dirty

    def end(self, canvas, layer):
        if layer is not None and self._dirty_rect is not None:
            canvas._layer_stack.mark_layer_dirty(
                layer, layer.local_rect_to_canvas(self._dirty_rect))
        self._dirty_rect = None
        canvas._smudge_stroke.clear()


class MaskPaintTool(CanvasStrokeTool):
    mode = BrushToolMode.MASK
    label = "Mask Stroke"
    target = "mask"

    def begin(self, canvas, layer, x: int, y: int):
        x, y = canvas._canvas_to_layer_point(layer, x, y)
        dirty, _stamp = canvas._mask_painter.dab(
            layer.mask.data,
            x,
            y,
            erase=False,
        )
        canvas._update_mask_overlay_region(layer, dirty)
        return dirty

    def move(self, canvas, layer, last_pos, x: int, y: int):
        x, y = canvas._canvas_to_layer_point(layer, x, y)
        if last_pos:
            lx, ly = canvas._canvas_to_layer_point(layer, *last_pos)
            dirty, _stamp = canvas._mask_painter.line(
                layer.mask.data,
                lx,
                ly,
                x,
                y,
                erase=False,
            )
        else:
            dirty, _stamp = canvas._mask_painter.dab(
                layer.mask.data,
                x,
                y,
                erase=False,
            )
        canvas._update_mask_overlay_region(layer, dirty)
        return dirty


class MaskEraserTool(CanvasStrokeTool):
    mode = BrushToolMode.MASK_ERASER
    label = "Mask Erase Stroke"
    target = "mask"

    def begin(self, canvas, layer, x: int, y: int):
        x, y = canvas._canvas_to_layer_point(layer, x, y)
        canvas._mask_erase_stroke.begin(layer.height, layer.width)
        erase_mask = canvas._mask_erase_stroke.mask
        if erase_mask is None:
            return None
        dirty, _stamp = canvas._mask_painter.dab(erase_mask, x, y, erase=False)
        self._preview(canvas, layer, dirty)
        return dirty

    def move(self, canvas, layer, last_pos, x: int, y: int):
        x, y = canvas._canvas_to_layer_point(layer, x, y)
        if canvas._mask_erase_stroke.mask is None:
            canvas._mask_erase_stroke.begin(layer.height, layer.width)
        erase_mask = canvas._mask_erase_stroke.mask
        if erase_mask is None:
            return None
        if last_pos:
            lx, ly = canvas._canvas_to_layer_point(layer, *last_pos)
            dirty, _stamp = canvas._mask_painter.line(
                erase_mask,
                lx,
                ly,
                x,
                y,
                erase=False,
            )
        else:
            dirty, _stamp = canvas._mask_painter.dab(
                erase_mask,
                x,
                y,
                erase=False,
            )
        self._preview(canvas, layer, dirty)
        return dirty

    def end(self, canvas, layer):
        dirty = canvas._mask_erase_stroke.dirty_rect
        if layer is not None and dirty is not None:
            canvas._mask_erase_stroke.apply_to_layer_mask(layer.mask.data)
            local_rect, canvas_rect = canvas._clip_layer_local_rect(layer, dirty)
            if local_rect is not None:
                erase = canvas._mask_erase_stroke.erase_region(local_rect)
                if erase is not None:
                    erase_alpha_region(layer.image, local_rect, erase)
                    canvas._composite_bridge.refresh_modified_layer_rect(
                        layer,
                        local_rect,
                        canvas_rect,
                    )
            canvas._update_mask_overlay_region(layer, dirty)
        canvas._mask_erase_stroke.clear()

    def _preview(self, canvas, layer, dirty):
        canvas._mask_erase_stroke.add_dirty(dirty)
        if dirty is None:
            return
        if canvas._show_mask:
            preview = canvas._mask_erase_stroke.preview_region(
                layer.mask.data,
                dirty,
            )
            canvas._update_mask_overlay_region_preview(layer, dirty, preview)
        canvas._preview_mask_erase_region(layer, dirty)


class MoveTool(CanvasStrokeTool):
    mode = BrushToolMode.MOVE
    label = "Move Layer"
    target = "transform"

    def begin(self, canvas, layer, x: int, y: int):
        if layer is None:
            return None
        self._start_x = x
        self._start_y = y
        self._layer_start_x = layer.x
        self._layer_start_y = layer.y
        return layer.bounds

    def move(self, canvas, layer, last_pos, x: int, y: int):
        if layer is None:
            return None
        dx = x - self._start_x
        dy = y - self._start_y
        old_bounds = layer.bounds
        layer.x = self._layer_start_x + dx
        layer.y = self._layer_start_y + dy
        dirty = canvas._union_rect(old_bounds, layer.bounds)
        canvas._refresh_layer_transform(layer, dirty)
        return dirty

    def end(self, canvas, layer):
        pass


def create_canvas_tools() -> dict[BrushToolMode, CanvasStrokeTool]:
    return {
        BrushToolMode.PAINT: PaintTool(),
        BrushToolMode.ERASER: EraserTool(),
        BrushToolMode.SMUDGE: SmudgeTool(),
        BrushToolMode.MASK: MaskPaintTool(),
        BrushToolMode.MASK_ERASER: MaskEraserTool(),
        BrushToolMode.MOVE: MoveTool(),
    }
