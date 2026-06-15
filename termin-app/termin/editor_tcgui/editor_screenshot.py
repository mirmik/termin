"""Screenshot helpers for the tcgui editor viewport."""

from __future__ import annotations

import base64
import tempfile
import time
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from tcbase import log


def capture_editor_viewport_screenshot(
    editor: Any,
    *,
    output_path: str | None = None,
    include_image: bool = False,
) -> dict[str, object]:
    """Read the editor viewport FBO and save it as a PNG image."""
    surface = editor._fbo_surface
    if surface is None or not surface.is_valid():
        raise RuntimeError("Editor viewport FBO surface is not available")

    width, height = surface.framebuffer_size()
    width = int(width)
    height = int(height)
    if width <= 0 or height <= 0:
        raise RuntimeError(f"Editor viewport FBO has invalid size {width}x{height}")

    device = editor._ctx.device
    pixels = np.empty(width * height * 4, dtype=np.float32)
    if not device.read_texture_rgba_float(surface.color_tex, pixels):
        raise RuntimeError("Failed to read editor viewport color texture")

    # tgfx2 readback returns rows in top-left CPU order for all backends.
    rgba = pixels.reshape((height, width, 4))
    rgba8 = np.clip(rgba * 255.0, 0.0, 255.0).astype(np.uint8)

    path = _resolve_screenshot_path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgba8, mode="RGBA").save(path)
    log.info(f"[EditorScreenshot] captured editor viewport screenshot: {path}")

    payload: dict[str, object] = {
        "path": str(path),
        "width": width,
        "height": height,
        "mime_type": "image/png",
    }
    if include_image:
        payload["base64"] = base64.b64encode(path.read_bytes()).decode("ascii")
    return payload


def _resolve_screenshot_path(output_path: str | None) -> Path:
    if output_path:
        path = Path(output_path).expanduser()
        if path.suffix.lower() != ".png":
            if path.exists() and path.is_dir():
                return path / _default_screenshot_name()
            return path.with_suffix(".png")
        return path

    return Path(tempfile.gettempdir()) / "termin-editor-screenshots" / _default_screenshot_name()


def _default_screenshot_name() -> str:
    return f"termin-editor-{time.strftime('%Y%m%d-%H%M%S')}.png"
