# termin/visualization/ui/font.py
from PIL import Image, ImageDraw, ImageFont
import numpy as np

import os
import sys

from termin._native import log
from termin.visualization.platform.backends.base import GraphicsBackend, GPUTextureHandle


def find_system_font() -> str | None:
    """Find a system font file."""
    candidates = []

    if sys.platform == "win32":
        fonts_dir = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")
        candidates = [
            os.path.join(fonts_dir, "segoeui.ttf"),
            os.path.join(fonts_dir, "arial.ttf"),
            os.path.join(fonts_dir, "tahoma.ttf"),
        ]
    elif sys.platform == "darwin":
        candidates = [
            "/System/Library/Fonts/SFNSText.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial.ttf",
        ]
    else:  # Linux
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
            "/usr/share/fonts/TTF/DejaVuSans.ttf",
        ]

    for path in candidates:
        if os.path.exists(path):
            return path
    return None


_default_font_atlas: "FontTextureAtlas | None" = None


def get_default_font(size: int = 14) -> "FontTextureAtlas | None":
    """Get or create default system font atlas."""
    global _default_font_atlas
    if _default_font_atlas is None:
        font_path = find_system_font()
        if font_path:
            try:
                _default_font_atlas = FontTextureAtlas(font_path, size)
            except Exception:
                log.warning("[Font] Failed to load system font", exc_info=True)
    return _default_font_atlas


class FontTextureAtlas:
    def __init__(self, path: str, size: int = 32):
        if not os.path.exists(path):
            raise FileNotFoundError(f"Font file not found: {path}")
        self.font = ImageFont.truetype(path, size)
        self.size = size
        self.glyphs = {}
        self._handle: GPUTextureHandle | None = None
        self._atlas_data = None
        self.tex_w = 0
        self.tex_h = 0
        self._build_atlas()

    @property
    def texture(self) -> GPUTextureHandle | None:
        """Backend texture handle (uploaded lazily once a context exists)."""
        return self._handle

    def ensure_texture(self, graphics: GraphicsBackend) -> GPUTextureHandle:
        """Uploads atlas into the current graphics backend if not done yet."""
        if self._handle is not None:
            # Check if texture is still valid.
            # Drain stale GL errors first so glIsTexture doesn't pick them up.
            import OpenGL.GL as gl
            while gl.glGetError() != gl.GL_NO_ERROR:
                pass
            if not gl.glIsTexture(self._handle.get_id()):
                log.warn(f"ensure_texture: texture {self._handle.get_id()} invalid, recreating")
                self._handle = None
        if self._handle is None:
            self._handle = self._upload_texture(graphics)
        return self._handle

    def _build_atlas(self):
        chars = [chr(i) for i in range(32, 127)]
        padding = 2

        ascent, descent = self.font.getmetrics()
        line_height = ascent + descent
        self.ascent = ascent

        max_w = 0

        glyph_images = []
        for ch in chars:
            try:
                bbox = self.font.getbbox(ch)
                w = bbox[2] - bbox[0]
            except (TypeError, AttributeError, ValueError):
                continue

            # Each glyph image is full line_height tall.
            # Drawing at y=0 puts baseline at y=ascent automatically.
            img = Image.new("L", (w, line_height))
            draw = ImageDraw.Draw(img)
            draw.text((-bbox[0], 0), ch, fill=255, font=self.font)

            glyph_images.append((ch, img))
            max_w = max(max_w, w)

        cols = 16
        rows = (len(glyph_images) + cols - 1) // cols
        cell_w = max_w + padding
        cell_h = line_height + padding
        atlas_w = cols * cell_w
        atlas_h = rows * cell_h
        self.tex_w = atlas_w
        self.tex_h = atlas_h

        atlas = Image.new("L", (atlas_w, atlas_h))

        x = y = 0
        for i, (ch, img) in enumerate(glyph_images):
            atlas.paste(img, (x, y))
            w, h = img.size
            self.glyphs[ch] = {
                "uv": (
                    x / atlas_w,
                    y / atlas_h,
                    (x + w) / atlas_w,
                    (y + h) / atlas_h
                ),
                "size": (w, h)
            }
            x += cell_w
            if (i + 1) % cols == 0:
                x = 0
                y += cell_h

        # Keep CPU-side atlas; upload to GPU later when a graphics context is guaranteed.
        self._atlas_data = np.array(atlas, dtype=np.uint8)

    def _upload_texture(self, graphics: GraphicsBackend) -> GPUTextureHandle:
        if self._atlas_data is None:
            raise RuntimeError("Font atlas data is missing; cannot upload texture.")
        return graphics.create_texture(self._atlas_data, (self.tex_w, self.tex_h), channels=1, mipmap=False, clamp=True)
