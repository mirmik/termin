"""Screenshot readback helpers for graphics-aware Termin MCP hosts."""

from __future__ import annotations

import base64
import time
from pathlib import Path
from typing import Any

import numpy as np

from termin.base import log
from termin.image import write_png_rgba8_file


def capture_surface_screenshot(
    surface: Any,
    device: Any,
    *,
    source_is_linear: bool = False,
    output_path: str | None = None,
    include_image: bool = False,
    default_dir: Path,
    default_prefix: str,
    log_prefix: str,
) -> dict[str, object]:
    """Read a Termin render surface color texture and save it as a PNG image."""
    if surface is None or not surface.is_valid():
        raise RuntimeError("Render surface is not available")
    if device is None:
        raise RuntimeError("Render device is not available")

    width, height = surface.framebuffer_size()
    width = int(width)
    height = int(height)
    if width <= 0 or height <= 0:
        raise RuntimeError(f"Render surface has invalid size {width}x{height}")

    return capture_texture_screenshot(
        surface.color_tex,
        device,
        width=width,
        height=height,
        source_is_linear=source_is_linear,
        output_path=output_path,
        include_image=include_image,
        default_dir=default_dir,
        default_prefix=default_prefix,
        log_prefix=log_prefix,
    )


def capture_texture_screenshot(
    texture: Any,
    device: Any,
    *,
    width: int,
    height: int,
    source_is_linear: bool = False,
    output_path: str | None = None,
    include_image: bool = False,
    default_dir: Path,
    default_prefix: str,
    log_prefix: str,
) -> dict[str, object]:
    """Save display RGB to PNG, encoding linear RGB sources to sRGB on export."""
    if texture is None:
        raise RuntimeError("Screenshot texture is not available")
    if device is None:
        raise RuntimeError("Render device is not available")
    width = int(width)
    height = int(height)
    if width <= 0 or height <= 0:
        raise RuntimeError(f"Screenshot texture has invalid size {width}x{height}")

    pixels = np.empty(width * height * 4, dtype=np.float32)
    if not device.read_texture_rgba_float(texture, pixels):
        raise RuntimeError("Failed to read screenshot texture")

    # tgfx2 readback returns rows in top-left CPU order for all backends.
    rgba = pixels.reshape((height, width, 4))
    np.clip(rgba, 0.0, 1.0, out=rgba)
    if source_is_linear:
        rgb = rgba[:, :, :3]
        rgb[:] = np.where(rgb <= 0.0031308, 12.92 * rgb, 1.055 * rgb ** (1.0 / 2.4) - 0.055)
    rgba8 = np.rint(rgba * 255.0).astype(np.uint8)

    path = _resolve_png_path(
        output_path,
        default_dir=default_dir,
        default_prefix=default_prefix,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    write_png_rgba8_file(path, rgba8)
    log.info(f"[{log_prefix}] captured screenshot: {path}")

    payload: dict[str, object] = {
        "path": str(path),
        "width": width,
        "height": height,
        "mime_type": "image/png",
    }
    if include_image:
        payload["base64"] = base64.b64encode(path.read_bytes()).decode("ascii")
    return payload


__all__ = ["capture_surface_screenshot", "capture_texture_screenshot"]


def _resolve_png_path(
    output_path: str | None,
    *,
    default_dir: Path,
    default_prefix: str,
) -> Path:
    if output_path:
        path = Path(output_path).expanduser()
        if path.suffix.lower() != ".png":
            if path.exists() and path.is_dir():
                return path / _default_png_name(default_prefix)
            return path.with_suffix(".png")
        return path

    return default_dir / _default_png_name(default_prefix)


def _default_png_name(prefix: str) -> str:
    return f"{prefix}-{time.strftime('%Y%m%d-%H%M%S')}.png"
