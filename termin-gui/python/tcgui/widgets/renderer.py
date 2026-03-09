"""OpenGL renderer for the widget-based UI system."""

from __future__ import annotations

import math
import numpy as np

from tgfx import GraphicsBackend, TcShader
from tcgui.font import FontTextureAtlas, get_default_font


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
uniform int u_texture_mode;  // 0=solid color, 1=font atlas (R→alpha), 2=RGBA image

in vec2 v_uv;
out vec4 FragColor;

void main(){
    if (u_texture_mode == 1) {
        // Font atlas: R channel as alpha mask, color from uniform
        float a = texture(u_texture, v_uv).r * u_color.a;
        FragColor = vec4(u_color.rgb, a);
    } else if (u_texture_mode == 2) {
        // RGBA image: full texture color multiplied by tint
        FragColor = texture(u_texture, v_uv) * u_color;
    } else {
        // Solid color
        FragColor = u_color;
    }
}
"""


class UIRenderer:
    """OpenGL renderer for UI widgets."""

    def __init__(self, graphics: GraphicsBackend, font: FontTextureAtlas | None = None):
        self._graphics = graphics
        self._font = font
        self._shader: TcShader | None = None

        # Viewport size in pixels
        self._viewport_w: int = 0
        self._viewport_h: int = 0

        # Scissor clip stack for nested begin_clip/end_clip
        self._clip_stack: list[tuple[int, int, int, int]] = []

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

    def begin(self, viewport_w: int, viewport_h: int):
        """Begin UI rendering pass."""
        self._viewport_w = viewport_w
        self._viewport_h = viewport_h

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

    def begin_clip(self, x: float, y: float, w: float, h: float):
        """Push scissor clip rect. Nested clips are intersected."""
        # Convert to GL bottom-left origin integers
        ix, iy, iw, ih = int(x), int(self._viewport_h - (y + h)), int(w), int(h)

        if self._clip_stack:
            # Intersect with current top-of-stack
            px, py, pw, ph = self._clip_stack[-1]
            x1 = max(ix, px)
            y1 = max(iy, py)
            x2 = min(ix + iw, px + pw)
            y2 = min(iy + ih, py + ph)
            iw = max(0, x2 - x1)
            ih = max(0, y2 - y1)
            ix, iy = x1, y1

        self._clip_stack.append((ix, iy, iw, ih))
        self._graphics.enable_scissor(ix, iy, iw, ih)

    def end_clip(self):
        """Pop scissor clip rect. Restores parent clip or disables scissor."""
        if self._clip_stack:
            self._clip_stack.pop()
        if self._clip_stack:
            px, py, pw, ph = self._clip_stack[-1]
            self._graphics.enable_scissor(px, py, pw, ph)
        else:
            self._graphics.disable_scissor()

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
        self._shader.ensure_ready()
        self._shader.use()
        self._graphics.check_gl_error("UIRenderer: after shader.use")
        self._shader.set_uniform_vec4("u_color", float(color[0]), float(color[1]), float(color[2]), float(color[3]))
        self._shader.set_uniform_int("u_texture_mode", 0)
        self._graphics.check_gl_error("UIRenderer: after set uniforms")

        # Draw
        self._graphics.draw_ui_vertices(vertices)
        self._graphics.check_gl_error("UIRenderer: after draw_rect")

    def draw_text(self, x: float, y: float, text: str,
                  color: tuple[float, float, float, float],
                  font_size: float = 14):
        """Draw text at pixel coordinates (baseline position)."""
        font = self.font  # Use property for lazy loading
        if not font or not text:
            return

        # Ensure all glyphs are in the atlas (triggers GPU sync if needed)
        font.ensure_glyphs(text, self._graphics)

        self._shader.ensure_ready()
        self._shader.use()
        self._shader.set_uniform_vec4("u_color", float(color[0]), float(color[1]), float(color[2]), float(color[3]))
        self._shader.set_uniform_int("u_texture_mode", 1)

        # Bind font texture
        texture_handle = font.ensure_texture(self._graphics)
        texture_handle.bind(0)
        self._shader.set_uniform_int("u_texture", 0)
        self._graphics.check_gl_error("UIRenderer: after text setup")

        # Scale factor from font atlas size to desired size
        scale = font_size / font.size

        # Ascent from font: distance from glyph image top to baseline
        ascent = font.ascent if hasattr(font, "ascent") else font.size

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

            # Glyph image top is ascent pixels above the baseline
            glyph_y = y - ascent * scale

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

            self._graphics.draw_ui_textured_quad(vertices)

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

    def draw_line(self, x1: float, y1: float, x2: float, y2: float,
                  color: tuple[float, float, float, float],
                  thickness: float = 1.0):
        """Draw a line between two pixel coordinates."""
        dx = x2 - x1
        dy = y2 - y1
        length = math.sqrt(dx * dx + dy * dy)
        if length < 0.001:
            return

        # Perpendicular normal
        half = thickness / 2.0
        nx = -dy / length * half
        ny = dx / length * half

        # 4 corners of the thin quad
        vertices_px = [
            (x1 + nx, y1 + ny),
            (x1 - nx, y1 - ny),
            (x2 + nx, y2 + ny),
            (x2 - nx, y2 - ny),
        ]

        # Convert to NDC
        ndc = np.array(
            [self._px_to_ndc(px, py) for px, py in vertices_px],
            dtype=np.float32,
        )

        self._shader.ensure_ready()
        self._shader.use()
        self._shader.set_uniform_vec4(
            "u_color",
            float(color[0]), float(color[1]),
            float(color[2]), float(color[3]),
        )
        self._shader.set_uniform_int("u_texture_mode", 0)

        self._graphics.draw_ui_vertices(ndc)

    def draw_rect_outline(self, x: float, y: float, w: float, h: float,
                          color: tuple[float, float, float, float],
                          thickness: float = 1.0):
        """Draw a rectangle outline (unfilled) at pixel coordinates."""
        self.draw_rect(x, y, w, thickness, color)                   # top
        self.draw_rect(x, y + h - thickness, w, thickness, color)   # bottom
        self.draw_rect(x, y, thickness, h, color)                   # left
        self.draw_rect(x + w - thickness, y, thickness, h, color)   # right

    def draw_image(self, x: float, y: float, w: float, h: float,
                   texture_handle,
                   tint: tuple[float, float, float, float] = (1, 1, 1, 1)):
        """Draw an RGBA textured quad at pixel coordinates."""
        self._shader.ensure_ready()
        self._shader.use()
        self._shader.set_uniform_vec4("u_color", float(tint[0]), float(tint[1]), float(tint[2]), float(tint[3]))
        self._shader.set_uniform_int("u_texture_mode", 2)

        texture_handle.bind(0)
        self._shader.set_uniform_int("u_texture", 0)

        # Convert to NDC
        nx, ny = self._px_to_ndc(x, y)
        nw, nh = self._size_to_ndc(w, h)

        left = nx
        right = nx + nw
        top = ny
        bottom = ny - nh

        # GL texture row 0 = numpy row 0 = image top, so v=0 at screen top
        vertices = np.array([
            [left, top, 0, 0],
            [right, top, 1, 0],
            [left, bottom, 0, 1],
            [right, bottom, 1, 1],
        ], dtype=np.float32)

        self._graphics.draw_ui_textured_quad(vertices)

    def upload_texture(self, data: np.ndarray):
        """Upload a numpy RGBA array as a GPU texture. Returns a texture handle.

        Parameters
        ----------
        data : np.ndarray
            Shape (H, W, 4) uint8 RGBA.
        """
        h, w = data.shape[0], data.shape[1]
        return self._graphics.create_texture(data, (w, h), channels=4,
                                             mipmap=False, clamp=True)

    def load_image(self, path: str):
        """Load an image file and upload as GPU texture. Returns a texture handle."""
        from PIL import Image
        img = Image.open(path).convert("RGBA")
        data = np.array(img, dtype=np.uint8)
        w, h = img.size
        return self._graphics.create_texture(data, (w, h), channels=4, mipmap=False, clamp=True)

    def measure_text(self, text: str, font_size: float = 14) -> tuple[float, float]:
        """Measure text dimensions in pixels."""
        font = self.font  # Use property for lazy loading
        if not font or not text:
            return (0, 0)

        # Ensure glyphs exist on CPU (no GPU sync needed just for measuring)
        font.ensure_glyphs(text)

        scale = font_size / font.size
        width = 0.0
        height = font_size

        for ch in text:
            if ch in font.glyphs:
                gw, _ = font.glyphs[ch]["size"]
                width += gw * scale

        return (width, height)
