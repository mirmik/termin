"""OpenGL renderer for the widget-based UI system."""

from __future__ import annotations

import numpy as np

from termin.visualization.platform.backends.base import GraphicsBackend
from termin._native.render import TcShader
from termin.visualization.ui.font import FontTextureAtlas, get_default_font


# Built-in UI shaders
UI_VERTEX_SHADER = """
#version 330 core
layout(location=0) in vec2 a_position;
layout(location=1) in vec2 a_uv;

out vec2 v_uv;

void main(){
    v_uv = a_uv;
    gl_Position = vec4(a_position, 0, 1);
}
"""

UI_FRAGMENT_SHADER = """
#version 330 core
uniform sampler2D u_texture;
uniform vec4 u_color;
uniform bool u_use_texture;

in vec2 v_uv;
out vec4 FragColor;

void main(){
    float alpha = u_color.a;
    if (u_use_texture) {
        alpha *= texture(u_texture, v_uv).r;
    }
    FragColor = vec4(u_color.rgb, alpha);
}
"""


class UIRenderer:
    """OpenGL renderer for UI widgets."""

    def __init__(self, graphics: GraphicsBackend, font: FontTextureAtlas | None = None):
        self._graphics = graphics
        self._font = font
        self._shader: TcShader | None = None
        self._context_key: int | None = None

        # Viewport size in pixels
        self._viewport_w: int = 0
        self._viewport_h: int = 0

    @property
    def font(self) -> FontTextureAtlas | None:
        if self._font is None:
            self._font = get_default_font()
        return self._font

    @font.setter
    def font(self, value: FontTextureAtlas | None):
        self._font = value

    def _ensure_shader(self):
        if self._shader is None:
            self._shader = TcShader.from_sources(UI_VERTEX_SHADER, UI_FRAGMENT_SHADER, "", "UIRenderer")

    def begin(self, viewport_w: int, viewport_h: int, context_key: int | None = None):
        """Begin UI rendering pass."""
        from termin._native import log

        self._viewport_w = viewport_w
        self._viewport_h = viewport_h
        self._context_key = context_key

        if context_key is None:
            log.warn("[UIRenderer] context_key is None, using 0")

        self._ensure_shader()

        # Setup OpenGL state for 2D UI
        self._graphics.set_cull_face(False)
        self._graphics.set_depth_test(False)
        self._graphics.set_blend(True)
        self._graphics.set_blend_func("src_alpha", "one_minus_src_alpha")

    def end(self):
        """End UI rendering pass, restore state."""
        self._graphics.set_cull_face(True)
        self._graphics.set_blend(False)
        self._graphics.set_depth_test(True)

    def _px_to_ndc(self, x: float, y: float) -> tuple[float, float]:
        """Convert pixel coordinates to NDC (-1..1)."""
        nx = (x / self._viewport_w) * 2.0 - 1.0
        ny = 1.0 - (y / self._viewport_h) * 2.0  # Y is flipped
        return (nx, ny)

    def _size_to_ndc(self, w: float, h: float) -> tuple[float, float]:
        """Convert pixel size to NDC size."""
        nw = (w / self._viewport_w) * 2.0
        nh = (h / self._viewport_h) * 2.0
        return (nw, nh)

    def draw_rect(self, x: float, y: float, w: float, h: float,
                  color: tuple[float, float, float, float],
                  border_radius: float = 0):
        """Draw a filled rectangle at pixel coordinates."""
        # Convert to NDC
        nx, ny = self._px_to_ndc(x, y)
        nw, nh = self._size_to_ndc(w, h)

        # Build quad vertices (2 triangles as triangle strip)
        left = nx
        right = nx + nw
        top = ny
        bottom = ny - nh

        vertices = np.array([
            [left, top],
            [right, top],
            [left, bottom],
            [right, bottom],
        ], dtype=np.float32)

        # Bind shader and set uniforms
        key = self._context_key if self._context_key is not None else 0
        self._shader.ensure_ready()
        self._shader.use()
        self._graphics.check_gl_error("UIRenderer: after shader.use")
        self._shader.set_uniform_vec4("u_color", float(color[0]), float(color[1]), float(color[2]), float(color[3]))
        self._shader.set_uniform_int("u_use_texture", 0)
        self._graphics.check_gl_error("UIRenderer: after set uniforms")

        # Draw
        key = self._context_key if self._context_key is not None else 0
        self._graphics.draw_ui_vertices(key, vertices)
        self._graphics.check_gl_error("UIRenderer: after draw_rect")

    def draw_text(self, x: float, y: float, text: str,
                  color: tuple[float, float, float, float],
                  font_size: float = 14):
        """Draw text at pixel coordinates (baseline position)."""
        font = self.font  # Use property for lazy loading
        if not font or not text:
            return

        key = self._context_key if self._context_key is not None else 0
        self._shader.ensure_ready()
        self._shader.use()
        self._shader.set_uniform_vec4("u_color", float(color[0]), float(color[1]), float(color[2]), float(color[3]))
        self._shader.set_uniform_int("u_use_texture", 1)

        # Bind font texture
        key = self._context_key if self._context_key is not None else 0
        texture_handle = font.ensure_texture(self._graphics, context_key=key)
        texture_handle.bind(0)
        self._shader.set_uniform_int("u_texture", 0)
        self._graphics.check_gl_error("UIRenderer: after text setup")

        # Scale factor from font atlas size to desired size
        scale = font_size / font.size

        cursor_x = x
        for ch in text:
            if ch not in font.glyphs:
                continue

            glyph = font.glyphs[ch]
            gw, gh = glyph["size"]
            u0, v0, u1, v1 = glyph["uv"]

            # Glyph dimensions in pixels at current scale
            char_w = gw * scale
            char_h = gh * scale

            # Position (y is baseline, glyph extends downward)
            glyph_y = y - char_h

            # Convert to NDC
            nx, ny = self._px_to_ndc(cursor_x, glyph_y)
            nw, nh = self._size_to_ndc(char_w, char_h)

            left = nx
            right = nx + nw
            top = ny
            bottom = ny - nh

            vertices = np.array([
                [left, top, u0, v0],
                [right, top, u1, v0],
                [left, bottom, u0, v1],
                [right, bottom, u1, v1],
            ], dtype=np.float32)

            self._graphics.draw_ui_textured_quad(key, vertices)

            cursor_x += char_w

    def draw_text_centered(self, cx: float, cy: float, text: str,
                           color: tuple[float, float, float, float],
                           font_size: float = 14):
        """Draw text centered at the given pixel position."""
        font = self.font  # Use property for lazy loading
        if not font or not text:
            return

        # Measure text width
        scale = font_size / font.size
        text_width = 0.0
        for ch in text:
            if ch in font.glyphs:
                gw, _ = font.glyphs[ch]["size"]
                text_width += gw * scale

        # Center position
        x = cx - text_width / 2
        y = cy + font_size / 2  # baseline offset

        self.draw_text(x, y, text, color, font_size)

    def measure_text(self, text: str, font_size: float = 14) -> tuple[float, float]:
        """Measure text dimensions in pixels."""
        font = self.font  # Use property for lazy loading
        if not font or not text:
            return (0, 0)

        scale = font_size / font.size
        width = 0.0
        height = font_size

        for ch in text:
            if ch in font.glyphs:
                gw, _ = font.glyphs[ch]["size"]
                width += gw * scale

        return (width, height)
