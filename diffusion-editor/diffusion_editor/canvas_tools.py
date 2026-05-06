"""Brush-like canvas tools used by EditorCanvas."""

from __future__ import annotations

import numpy as np

from .brush import BrushToolMode


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
        canvas._begin_stroke(layer)
        if canvas._stroke_mask is None:
            return None
        dirty = canvas.brush.dab_to_mask(canvas._stroke_mask, x, y)
        canvas._update_stroke_region(layer, dirty)
        return dirty

    def move(self, canvas, layer, last_pos, x: int, y: int):
        if canvas._stroke_mask is None:
            return None
        x, y = canvas._canvas_to_layer_point(layer, x, y)
        if last_pos:
            lx, ly = canvas._canvas_to_layer_point(layer, *last_pos)
            dirty = canvas.brush.stroke_to_mask(canvas._stroke_mask, lx, ly, x, y)
        else:
            dirty = canvas.brush.dab_to_mask(canvas._stroke_mask, x, y)
        canvas._update_stroke_region(layer, dirty)
        return dirty

    def end(self, canvas, layer):
        canvas._end_stroke()


class EraserTool(CanvasStrokeTool):
    mode = BrushToolMode.ERASER
    label = "Erase Stroke"
    target = "image"

    def begin(self, canvas, layer, x: int, y: int):
        canvas._begin_stroke(layer)
        x, y = canvas._canvas_to_layer_point(layer, x, y)
        dirty = canvas._erase_dab(layer, x, y)
        if not canvas._gpu_compositing:
            canvas.set_image(canvas._composite)
        return dirty

    def move(self, canvas, layer, last_pos, x: int, y: int):
        x, y = canvas._canvas_to_layer_point(layer, x, y)
        if last_pos:
            lx, ly = canvas._canvas_to_layer_point(layer, *last_pos)
            return canvas._erase_stroke_line(layer, lx, ly, x, y)
        dirty = canvas._erase_dab(layer, x, y)
        if not canvas._gpu_compositing:
            canvas.set_image(canvas._composite)
        return dirty

    def end(self, canvas, layer):
        if layer is not None:
            canvas._layer_stack.mark_layer_dirty(layer)
        if not canvas._gpu_compositing:
            canvas.set_image(canvas._composite)


class SmudgeTool(CanvasStrokeTool):
    mode = BrushToolMode.SMUDGE
    label = "Smudge Stroke"
    target = "image"

    def __init__(self):
        self._dirty_rect = None

    def begin(self, canvas, layer, x: int, y: int):
        self._dirty_rect = None
        x, y = canvas._canvas_to_layer_point(layer, x, y)
        canvas._begin_smudge(layer, x, y)
        return None

    def move(self, canvas, layer, last_pos, x: int, y: int):
        if not last_pos:
            return None
        lx, ly = canvas._canvas_to_layer_point(layer, *last_pos)
        x, y = canvas._canvas_to_layer_point(layer, x, y)
        dirty = canvas._smudge_stroke_line(layer, lx, ly, x, y)
        self._dirty_rect = canvas._union_rect(self._dirty_rect, dirty)
        return dirty

    def end(self, canvas, layer):
        if layer is not None and self._dirty_rect is not None:
            canvas._layer_stack.mark_layer_dirty(
                layer, layer.local_rect_to_canvas(self._dirty_rect))
        self._dirty_rect = None
        canvas._end_smudge()


class MaskPaintTool(CanvasStrokeTool):
    mode = BrushToolMode.MASK
    label = "Mask Stroke"
    target = "mask"

    def begin(self, canvas, layer, x: int, y: int):
        x, y = canvas._canvas_to_layer_point(layer, x, y)
        dirty, _stamp = canvas._dab_mask(layer.mask.data, x, y, erase=False)
        canvas._update_mask_overlay_region(layer, dirty)
        return dirty

    def move(self, canvas, layer, last_pos, x: int, y: int):
        x, y = canvas._canvas_to_layer_point(layer, x, y)
        if last_pos:
            lx, ly = canvas._canvas_to_layer_point(layer, *last_pos)
            dirty, _stamp = canvas._stroke_mask_line(
                layer.mask.data, lx, ly, x, y, erase=False)
        else:
            dirty, _stamp = canvas._dab_mask(layer.mask.data, x, y, erase=False)
        canvas._update_mask_overlay_region(layer, dirty)
        return dirty


class MaskEraserTool(CanvasStrokeTool):
    mode = BrushToolMode.MASK_ERASER
    label = "Mask Erase Stroke"
    target = "mask"

    def begin(self, canvas, layer, x: int, y: int):
        x, y = canvas._canvas_to_layer_point(layer, x, y)
        canvas._begin_mask_erase(layer)
        if canvas._mask_erase_stroke is None:
            return None
        dirty, _stamp = canvas._dab_mask(canvas._mask_erase_stroke, x, y, erase=False)
        self._preview(canvas, layer, dirty)
        return dirty

    def move(self, canvas, layer, last_pos, x: int, y: int):
        x, y = canvas._canvas_to_layer_point(layer, x, y)
        if canvas._mask_erase_stroke is None:
            canvas._begin_mask_erase(layer)
        if canvas._mask_erase_stroke is None:
            return None
        if last_pos:
            lx, ly = canvas._canvas_to_layer_point(layer, *last_pos)
            dirty, _stamp = canvas._stroke_mask_line(
                canvas._mask_erase_stroke, lx, ly, x, y, erase=False)
        else:
            dirty, _stamp = canvas._dab_mask(
                canvas._mask_erase_stroke, x, y, erase=False)
        self._preview(canvas, layer, dirty)
        return dirty

    def end(self, canvas, layer):
        dirty = canvas._mask_erase_dirty
        if layer is not None and dirty is not None:
            x0, y0, x1, y1 = dirty
            layer.mask.data[y0:y1, x0:x1] = np.minimum(
                layer.mask.data[y0:y1, x0:x1],
                1.0 - canvas._mask_erase_stroke[y0:y1, x0:x1])
            canvas._erase_layer_rect(
                layer, dirty, canvas._mask_erase_stroke[y0:y1, x0:x1])
            canvas._update_mask_overlay_region(layer, dirty)
        canvas._mask_erase_stroke = None
        canvas._mask_erase_dirty = None

    def _preview(self, canvas, layer, dirty):
        canvas._mask_erase_dirty = canvas._union_rect(canvas._mask_erase_dirty, dirty)
        if dirty is None:
            return
        if canvas._show_mask:
            x0, y0, x1, y1 = dirty
            preview = np.minimum(
                layer.mask.data[y0:y1, x0:x1],
                1.0 - canvas._mask_erase_stroke[y0:y1, x0:x1])
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
        canvas._layer_stack.mark_layer_dirty(layer, dirty)
        if canvas._gpu_compositing and canvas._gpu_compositor:
            canvas._gpu_compositor.mark_dirty(layer)
            canvas._gpu_compositor.composite()
            canvas._composite_stale = True
        else:
            canvas._composite = np.ascontiguousarray(
                canvas._layer_stack.composite())
            canvas.set_image(canvas._composite)
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
