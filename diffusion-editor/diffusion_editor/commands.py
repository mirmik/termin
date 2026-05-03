"""Command definitions for document mutations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

import numpy as np
from PIL import Image, ImageFilter

from .layer import Layer, DiffusionLayer, LamaLayer, InstructLayer
from .layer_stack import LayerStack
from .diffusion_brush import paste_result


class SnapshotCommand(Protocol):
    """Command interface executed against LayerStack with snapshot undo/redo."""

    @property
    def label(self) -> str:
        ...

    def apply(self, layer_stack: LayerStack) -> None:
        ...


@dataclass(frozen=True)
class AddLayerCommand:
    name: str
    image: np.ndarray | None = None
    label: str = "New Layer"

    def apply(self, layer_stack: LayerStack) -> None:
        layer_stack.add_layer(self.name, self.image)


@dataclass(frozen=True)
class InsertLayerCommand:
    layer: Layer
    label: str

    def apply(self, layer_stack: LayerStack) -> None:
        layer_stack.insert_layer(self.layer)


@dataclass(frozen=True)
class RemoveLayerCommand:
    layer: Layer
    label: str = "Remove Layer"

    def apply(self, layer_stack: LayerStack) -> None:
        layer_stack.remove_layer(self.layer)


@dataclass(frozen=True)
class MoveLayerCommand:
    layer: Layer
    new_parent: Layer | None
    index: int
    label: str = "Move Layer"

    def apply(self, layer_stack: LayerStack) -> None:
        layer_stack.move_layer(self.layer, self.new_parent, self.index)


@dataclass(frozen=True)
class SetLayerVisibilityCommand:
    layer: Layer
    visible: bool
    label: str = "Toggle Visibility"

    def apply(self, layer_stack: LayerStack) -> None:
        layer_stack.set_visibility(self.layer, self.visible)


@dataclass(frozen=True)
class SetLayerOpacityCommand:
    layer: Layer
    opacity: float
    label: str = "Set Opacity"

    def apply(self, layer_stack: LayerStack) -> None:
        layer_stack.set_opacity(self.layer, self.opacity)


@dataclass(frozen=True)
class FlattenLayersCommand:
    label: str = "Flatten Layers"

    def apply(self, layer_stack: LayerStack) -> None:
        layer_stack.flatten()


@dataclass(frozen=True)
class SnapshotCallbackCommand:
    """Command adapter for an arbitrary snapshot-based callback."""

    label: str
    apply_fn: Callable[[LayerStack], None]

    def apply(self, layer_stack: LayerStack) -> None:
        self.apply_fn(layer_stack)


@dataclass(frozen=True)
class DrawRectCommand:
    layer: Layer
    x: int
    y: int
    width: int
    height: int
    color: tuple[int, int, int, int] = (255, 0, 0, 255)
    thickness: int = 2
    label: str = "Draw Rectangle"

    def apply(self, layer_stack: LayerStack) -> None:
        x0 = max(0, self.x)
        y0 = max(0, self.y)
        x1 = min(self.layer.width, self.x + self.width)
        y1 = min(self.layer.height, self.y + self.height)
        if x0 >= x1 or y0 >= y1:
            return
        t = max(1, self.thickness)
        image = self.layer.image
        color = np.array(self.color, dtype=np.uint8)

        # Top edge
        te_bottom = min(y0 + t, y1)
        image[y0:te_bottom, x0:x1] = color
        # Bottom edge
        be_top = max(y1 - t, y0)
        image[be_top:y1, x0:x1] = color
        # Left edge (between top and bottom strips already drawn)
        le_right = min(x0 + t, x1)
        image[y0:y1, x0:le_right] = color
        # Right edge
        re_left = max(x1 - t, x0)
        image[y0:y1, re_left:x1] = color

        layer_stack.mark_layer_dirty(self.layer)
        if layer_stack.on_changed:
            layer_stack.on_changed()


@dataclass(frozen=True)
class DrawGridCommand:
    layer: Layer
    sections_x: int
    sections_y: int
    color: tuple[int, int, int, int] = (255, 0, 0, 128)
    thickness: int = 1
    label: str = "Draw Grid"

    def apply(self, layer_stack: LayerStack) -> None:
        t = max(1, self.thickness)
        image = self.layer.image
        w, h = self.layer.width, self.layer.height
        color = np.array(self.color, dtype=np.uint8)

        # Vertical lines
        for i in range(self.sections_x + 1):
            x = int(i * w / self.sections_x)
            x0 = max(0, min(x - t // 2, w))
            x1 = max(0, min(x + t // 2 + (t % 2), w))
            if x0 < x1:
                image[0:h, x0:x1] = color

        # Horizontal lines
        for i in range(self.sections_y + 1):
            y = int(i * h / self.sections_y)
            y0 = max(0, min(y - t // 2, h))
            y1 = max(0, min(y + t // 2 + (t % 2), h))
            if y0 < y1:
                image[y0:y1, 0:w] = color

        layer_stack.mark_layer_dirty(self.layer)
        if layer_stack.on_changed:
            layer_stack.on_changed()


@dataclass(frozen=True)
class ClearLayerMaskCommand:
    layer: DiffusionLayer | LamaLayer | InstructLayer
    label: str

    def apply(self, layer_stack: LayerStack) -> None:
        self.layer.clear_mask()
        if layer_stack.on_changed:
            layer_stack.on_changed()


@dataclass(frozen=True)
class SetDiffusionIpAdapterRectCommand:
    layer: DiffusionLayer
    rect: tuple[int, int, int, int]
    label: str = "Set IP-Adapter Rect"

    def apply(self, layer_stack: LayerStack) -> None:
        self.layer.ip_adapter_rect = self.rect
        if layer_stack.on_changed:
            layer_stack.on_changed()


@dataclass(frozen=True)
class ClearDiffusionIpAdapterRectCommand:
    layer: DiffusionLayer
    label: str = "Clear IP-Adapter Rect"

    def apply(self, layer_stack: LayerStack) -> None:
        self.layer.ip_adapter_rect = None
        if layer_stack.on_changed:
            layer_stack.on_changed()


@dataclass(frozen=True)
class SetManualPatchRectCommand:
    layer: DiffusionLayer | InstructLayer
    rect: tuple[int, int, int, int]
    label: str

    def apply(self, layer_stack: LayerStack) -> None:
        self.layer.manual_patch_rect = self.rect
        if layer_stack.on_changed:
            layer_stack.on_changed()


@dataclass(frozen=True)
class ClearManualPatchRectCommand:
    layer: DiffusionLayer | InstructLayer
    label: str

    def apply(self, layer_stack: LayerStack) -> None:
        self.layer.manual_patch_rect = None
        if layer_stack.on_changed:
            layer_stack.on_changed()


@dataclass(frozen=True)
class ReplaceLayerMaskCommand:
    layer: DiffusionLayer | LamaLayer | InstructLayer
    mask: np.ndarray
    label: str = "Apply Segmentation Mask"

    def apply(self, layer_stack: LayerStack) -> None:
        self.layer.mask = self.mask.copy()
        if layer_stack.on_changed:
            layer_stack.on_changed()


@dataclass(frozen=True)
class ApplyGeneratedResultCommand:
    """Apply a generated patch result into a layer image and invalidate caches."""

    layer: DiffusionLayer | LamaLayer | InstructLayer
    result_image: Image.Image
    label: str

    def apply(self, layer_stack: LayerStack) -> None:
        layer = self.layer
        layer.image[:] = 0
        if layer.has_mask():
            mask_pil = Image.fromarray(layer.mask, "L")
            mask_pil = mask_pil.filter(ImageFilter.MaxFilter(7))
            mask_pil = mask_pil.filter(ImageFilter.GaussianBlur(radius=4))
            mask_arg = np.array(mask_pil, dtype=np.uint8)
        else:
            mask_arg = None
        paste_result(
            layer.image,
            self.result_image,
            layer.patch_x,
            layer.patch_y,
            layer.patch_w,
            layer.patch_h,
            mask=mask_arg,
        )
        layer_stack.mark_layer_dirty(layer)
        if layer_stack.on_changed:
            layer_stack.on_changed()
