"""Command definitions for document mutations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

import numpy as np
from PIL import Image, ImageFilter

from .layer import Layer
from .tool import DiffusionTool
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
class ClearLayerMaskCommand:
    layer: Layer
    label: str

    def apply(self, layer_stack: LayerStack) -> None:
        if self.layer.tool is not None:
            self.layer.tool.clear_mask()
        if layer_stack.on_changed:
            layer_stack.on_changed()


@dataclass(frozen=True)
class SetIpAdapterRectCommand:
    layer: Layer
    rect: tuple[int, int, int, int]
    label: str = "Set IP-Adapter Rect"

    def apply(self, layer_stack: LayerStack) -> None:
        tool = self.layer.tool
        if isinstance(tool, DiffusionTool):
            tool.ip_adapter_rect = self.rect
        if layer_stack.on_changed:
            layer_stack.on_changed()


@dataclass(frozen=True)
class ClearIpAdapterRectCommand:
    layer: Layer
    label: str = "Clear IP-Adapter Rect"

    def apply(self, layer_stack: LayerStack) -> None:
        tool = self.layer.tool
        if isinstance(tool, DiffusionTool):
            tool.ip_adapter_rect = None
        if layer_stack.on_changed:
            layer_stack.on_changed()


@dataclass(frozen=True)
class SetManualPatchRectCommand:
    layer: Layer
    rect: tuple[int, int, int, int]
    label: str

    def apply(self, layer_stack: LayerStack) -> None:
        tool = self.layer.tool
        if tool is not None and hasattr(tool, 'manual_patch_rect'):
            tool.manual_patch_rect = self.rect
        if layer_stack.on_changed:
            layer_stack.on_changed()


@dataclass(frozen=True)
class ClearManualPatchRectCommand:
    layer: Layer
    label: str

    def apply(self, layer_stack: LayerStack) -> None:
        tool = self.layer.tool
        if tool is not None and hasattr(tool, 'manual_patch_rect'):
            tool.manual_patch_rect = None
        if layer_stack.on_changed:
            layer_stack.on_changed()


@dataclass(frozen=True)
class ReplaceLayerMaskCommand:
    layer: Layer
    mask: np.ndarray
    label: str = "Apply Segmentation Mask"

    def apply(self, layer_stack: LayerStack) -> None:
        if self.layer.tool is not None:
            self.layer.tool.mask = self.mask.copy()
        if layer_stack.on_changed:
            layer_stack.on_changed()


@dataclass(frozen=True)
class ApplyGeneratedResultCommand:
    """Apply a generated patch result into a layer image and invalidate caches."""

    layer: Layer
    result_image: Image.Image
    label: str

    def apply(self, layer_stack: LayerStack) -> None:
        layer = self.layer
        tool = layer.tool
        if tool is None:
            return
        layer.image[:] = 0
        if tool.has_mask():
            mask_pil = Image.fromarray(tool.mask, "L")
            mask_pil = mask_pil.filter(ImageFilter.MaxFilter(7))
            mask_pil = mask_pil.filter(ImageFilter.GaussianBlur(radius=4))
            mask_arg = np.array(mask_pil, dtype=np.uint8)
        else:
            mask_arg = None
        paste_result(
            layer.image,
            self.result_image,
            tool.patch_x,
            tool.patch_y,
            tool.patch_w,
            tool.patch_h,
            mask=mask_arg,
        )
        layer_stack.mark_layer_dirty(layer)
        if layer_stack.on_changed:
            layer_stack.on_changed()
