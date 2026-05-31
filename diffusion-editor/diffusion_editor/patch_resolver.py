"""Source patch preparation shared by generation tools."""

from __future__ import annotations

import numpy as np
from PIL import Image

from .diffusion_brush import extract_patch
from .generation_types import GenerationError, PatchSource, Rect
from .layer import Layer


def clip_rect_to_array(rect: Rect, image: np.ndarray) -> Rect:
    x0, y0, x1, y1 = rect
    h, w = image.shape[:2]
    x0 = max(0, min(int(x0), w))
    x1 = max(0, min(int(x1), w))
    y0 = max(0, min(int(y0), h))
    y1 = max(0, min(int(y1), h))
    return x0, y0, x1, y1


def source_patch_from_layer_patch(
        layer: Layer,
        composite: np.ndarray) -> PatchSource | GenerationError | None:
    if layer.patch_rect is None:
        return None

    raw_rect = layer.local_rect_to_canvas(layer.patch_rect)
    rect = clip_rect_to_array(raw_rect, composite)
    x0, y0, x1, y1 = rect
    if x1 - x0 < 1 or y1 - y0 < 1:
        return GenerationError(
            message="Patch is outside the image",
            log_message=(
                f"Layer patch rect is outside composite for layer {layer.name}: "
                f"local={layer.patch_rect} canvas={raw_rect}"
            ),
        )
    image = Image.fromarray(composite[y0:y1, x0:x1]).convert("RGB")
    return PatchSource(image=image, canvas_rect=rect, source="patch")


def source_patch_from_mask(
        layer: Layer,
        composite: np.ndarray,
        *,
        min_patch_size: int = 512,
        padding_scale: float = 1.25) -> PatchSource | None:
    if not layer.has_mask():
        return None
    bbox = layer.mask_bbox()
    center = layer.mask_center()
    if bbox is None or center is None:
        return None
    bx0, by0, bx1, by1 = bbox
    patch_size = max(bx1 - bx0, by1 - by0)
    patch_size = max(int(patch_size * padding_scale), min_patch_size)
    cx, cy = center
    patch, x0, y0, width, height = extract_patch(
        composite, cx, cy, patch_size=patch_size)
    return PatchSource(
        image=patch,
        canvas_rect=(x0, y0, x0 + width, y0 + height),
        source="mask_bbox",
    )


def resolve_source_patch(
        layer: Layer,
        composite: np.ndarray) -> PatchSource | GenerationError | None:
    patch = source_patch_from_layer_patch(layer, composite)
    if patch is not None:
        return patch
    return source_patch_from_mask(layer, composite)
