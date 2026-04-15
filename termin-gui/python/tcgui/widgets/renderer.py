"""tgfx2-backed renderer for the widget-based UI system.

Public API is byte-compatible with the previous tgfx1 version:
``__init__(graphics, font)``, ``font`` property, ``begin``, ``end``,
``begin_clip``, ``end_clip``, ``draw_rect``, ``draw_rect_outline``,
``draw_line``, ``draw_text``, ``draw_text_centered``, ``draw_image``,
``upload_texture``, ``load_image``, ``measure_text``.

Internally the renderer drives a ``Tgfx2Context`` (created lazily on
first ``begin()``) and keeps an offscreen tgfx1 FBO as its draw
target. At ``end()`` it blits the offscreen to the default
framebuffer via tgfx1 ``blit_framebuffer``. This mirrors the
production pattern used by ``present.py`` and lets diffusion-editor
and tcplot consumers remain unchanged.

Text is delegated to ``Text2DRenderer``. Rects / lines / images use a
small UI shader compiled once per holder through
``tc_shader_ensure_tgfx2``.
"""

from __future__ import annotations

import math

import numpy as np

from tgfx import GraphicsBackend, TcShader
from tgfx.font import FontTextureAtlas, get_default_font
from tgfx.text2d import Text2DRenderer
from tgfx._tgfx_native import (
    Tgfx2Context,
    Tgfx2TextureHandle,
    tc_shader_ensure_tgfx2,
    wrap_fbo_color_as_tgfx2,
    wrap_fbo_depth_as_tgfx2,
    wrap_gl_texture_as_tgfx2,
    CULL_NONE,
    PIXEL_RGBA8,
)


# UI shader: solid colour (mode 0) and RGBA-image sampling (mode 2).
# Font-atlas sampling lives in Text2DRenderer; this shader does not
# carry mode 1.
UI_VERTEX_SHADER = """#version 330 core
layout(location=0) in vec3 a_pos;    // (x_pixel, y_pixel, 0)
layout(location=1) in vec4 a_uv_pad; // (u, v, _, _)

uniform mat4 u_projection;

out vec2 v_uv;

void main() {
    gl_Position = u_projection * vec4(a_pos.xy, 0.0, 1.0);
    v_uv = a_uv_pad.xy;
}
"""

UI_FRAGMENT_SHADER = """#version 330 core
uniform sampler2D u_texture;
uniform vec4 u_color;
uniform int u_texture_mode;   // 0 = solid colour, 2 = RGBA image (tinted)

in vec2 v_uv;
out vec4 FragColor;

void main() {
    if (u_texture_mode == 2) {
        FragColor = texture(u_texture, v_uv) * u_color;
    } else {
        FragColor = u_color;
    }
}
"""


def _build_ortho_pixel_to_ndc(w: float, h: float) -> np.ndarray:
    """Ortho projection: pixel coords (y+ down) → NDC (y+ up)."""
    if w <= 0 or h <= 0:
        return np.eye(4, dtype=np.float32)
    return np.array(
        [
            [2.0 / w,  0.0,     0.0, -1.0],
            [0.0,    -2.0 / h,  0.0,  1.0],
            [0.0,     0.0,     -1.0,  0.0],
            [0.0,     0.0,      0.0,  1.0],
        ],
        dtype=np.float32,
    )


class UIRenderer:
    """UI widget renderer backed by tgfx2."""

    def __init__(
        self,
        graphics: GraphicsBackend,
        font: FontTextureAtlas | None = None,
    ):
        # tgfx1 singleton is kept around because the offscreen FBO is
        # created through it and the final composite to the default
        # framebuffer goes through ``blit_framebuffer``. It is NOT
        # used for any rendering state or draw calls.
        self._graphics = graphics
        self._font = font

        # Viewport dimensions in pixels. Updated each begin().
        self._viewport_w: int = 0
        self._viewport_h: int = 0

        # CPU scissor stack for nested begin_clip/end_clip. Stored in
        # GL (bottom-left, y+ up) pixel coordinates.
        self._clip_stack: list[tuple[int, int, int, int]] = []

        # --- Lazy tgfx2 resources — created on first begin() ---
        self._holder: Tgfx2Context | None = None
        self._ctx = None
        self._text2d: Text2DRenderer | None = None

        self._ui_tc_shader: TcShader | None = None
        self._ui_vs = None
        self._ui_fs = None

        # Offscreen target wired through tgfx1 FramebufferHandle +
        # wrap_fbo_color_as_tgfx2 each frame.
        self._offscreen_fbo = None
        self._window_fbo = None
        self._offscreen_size: tuple[int, int] = (0, 0)

    # ------------------------------------------------------------------
    # Font property
    # ------------------------------------------------------------------

    @property
    def font(self) -> FontTextureAtlas | None:
        if self._font is None:
            self._font = get_default_font()
        return self._font

    @font.setter
    def font(self, value: FontTextureAtlas | None):
        self._font = value

    @property
    def holder(self) -> Tgfx2Context | None:
        """The Tgfx2Context the renderer draws through.

        Publicly exposed for embedded sub-renderers (tcplot Plot3D,
        custom widgets) that want to issue their own tgfx2 draw calls
        into the same render pass. Valid only between ``begin()`` and
        ``end()`` — before ``begin()`` the context does not exist yet.
        """
        return self._holder

    # ------------------------------------------------------------------
    # Lazy tgfx2 init
    # ------------------------------------------------------------------

    def _ensure_init(self, w: int, h: int) -> None:
        """Create Tgfx2Context, compile UI shader, allocate offscreen
        FBO. Called on the first begin() and whenever the viewport
        size changes."""
        if self._holder is None:
            self._holder = Tgfx2Context()
            self._ctx = self._holder.context
            self._text2d = Text2DRenderer(font=self._font)

        if self._ui_tc_shader is None:
            self._ui_tc_shader = TcShader.from_sources(
                UI_VERTEX_SHADER, UI_FRAGMENT_SHADER, "", "UIRenderer"
            )
            self._ui_tc_shader.ensure_ready()
            pair = tc_shader_ensure_tgfx2(self._ctx, self._ui_tc_shader)
            if not pair.vs or not pair.fs:
                raise RuntimeError(
                    "UIRenderer: tc_shader_ensure_tgfx2 returned null handles"
                )
            self._ui_vs = pair.vs
            self._ui_fs = pair.fs

        if self._offscreen_size != (w, h):
            self._offscreen_fbo = self._graphics.create_framebuffer(w, h, 1, "")
            self._window_fbo = self._graphics.create_external_framebuffer(0, w, h)
            self._offscreen_size = (w, h)

    # ------------------------------------------------------------------
    # Frame lifecycle
    # ------------------------------------------------------------------

    def begin(self, viewport_w: int, viewport_h: int) -> None:
        """Begin UI rendering pass."""
        self._viewport_w = int(viewport_w)
        self._viewport_h = int(viewport_h)

        self._ensure_init(self._viewport_w, self._viewport_h)

        ctx = self._ctx

        ctx.begin_frame()
        offscreen_tex2 = wrap_fbo_color_as_tgfx2(ctx, self._offscreen_fbo)
        offscreen_depth2 = wrap_fbo_depth_as_tgfx2(ctx, self._offscreen_fbo)
        # Clear to transparent black so areas the UI does not touch
        # remain transparent after composite. Depth is cleared to 1.0
        # so 3D embedded renderers (tcplot Plot3D, Viewport3D) get a
        # fresh depth buffer each frame.
        ctx.begin_pass(
            color=offscreen_tex2,
            depth=offscreen_depth2,
            clear_color_enabled=True,
            r=0.0, g=0.0, b=0.0, a=0.0,
            clear_depth=1.0,
            clear_depth_enabled=True,
        )
        ctx.set_viewport(0, 0, self._viewport_w, self._viewport_h)
        ctx.set_cull(CULL_NONE)
        ctx.set_depth_test(False)
        ctx.set_blend(True)

        # Text2D uses the same projection matrix — its begin() sets
        # its own u_projection on its own shader, so we must call it
        # here after the ctx is in a pass. Go through the `font`
        # property so the default system font is lazily resolved if
        # the caller did not supply one.
        self._text2d.begin(self._holder, self._viewport_w, self._viewport_h,
                           font=self.font)

    def end(self) -> None:
        """End UI rendering pass, composite offscreen to default FB."""
        if self._ctx is None:
            return

        self._text2d.end()
        self._ctx.end_pass()
        self._ctx.end_frame()

        # Drop any remaining scissor state so legacy tgfx1 rendering
        # after this (if any) starts with a clean slate.
        self._clip_stack.clear()

        # Composite offscreen → default framebuffer.
        self._graphics.blit_framebuffer(
            self._offscreen_fbo,
            self._window_fbo,
            (0, 0, self._viewport_w, self._viewport_h),
            (0, 0, self._viewport_w, self._viewport_h),
            True,
            False,
        )

    # ------------------------------------------------------------------
    # Scissor / clip stack
    # ------------------------------------------------------------------

    def begin_clip(self, x: float, y: float, w: float, h: float) -> None:
        """Push scissor clip rect. Nested clips are intersected."""
        ix = int(x)
        iy = int(self._viewport_h - (y + h))  # GL bottom-left origin
        iw = int(w)
        ih = int(h)

        if self._clip_stack:
            px, py, pw, ph = self._clip_stack[-1]
            x1 = max(ix, px)
            y1 = max(iy, py)
            x2 = min(ix + iw, px + pw)
            y2 = min(iy + ih, py + ph)
            iw = max(0, x2 - x1)
            ih = max(0, y2 - y1)
            ix, iy = x1, y1

        self._clip_stack.append((ix, iy, iw, ih))
        self._ctx.set_scissor(ix, iy, iw, ih)

    def end_clip(self) -> None:
        """Pop scissor clip rect. Restore parent clip or disable."""
        if self._clip_stack:
            self._clip_stack.pop()
        if self._clip_stack:
            px, py, pw, ph = self._clip_stack[-1]
            self._ctx.set_scissor(px, py, pw, ph)
        else:
            self._ctx.clear_scissor()

    # ------------------------------------------------------------------
    # Primitive drawing helpers
    # ------------------------------------------------------------------

    def _bind_ui_shader_solid(
        self, color: tuple[float, float, float, float],
    ) -> None:
        ctx = self._ctx
        ctx.bind_shader(self._ui_vs, self._ui_fs)
        proj = _build_ortho_pixel_to_ndc(
            float(self._viewport_w), float(self._viewport_h),
        )
        ctx.set_uniform_mat4("u_projection", proj.flatten().tolist(), True)
        ctx.set_uniform_vec4(
            "u_color",
            float(color[0]), float(color[1]),
            float(color[2]), float(color[3]),
        )
        ctx.set_uniform_int("u_texture_mode", 0)

    def _emit_quad(
        self,
        px0: float, py0: float, px1: float, py1: float,
        u0: float, v0: float, u1: float, v1: float,
    ) -> np.ndarray:
        """Return 6 CCW (in y+ down pixel coords) vertices for a
        quad spanning (px0, py0)-(px1, py1) with given UVs. The
        winding survives the ortho Y-flip and default back-face
        culling: triangles end up CCW in NDC."""
        return np.array(
            [
                # Triangle 1: TL, BL, BR
                px0, py0, 0.0, u0, v0, 0.0, 0.0,
                px0, py1, 0.0, u0, v1, 0.0, 0.0,
                px1, py1, 0.0, u1, v1, 0.0, 0.0,
                # Triangle 2: TL, BR, TR
                px0, py0, 0.0, u0, v0, 0.0, 0.0,
                px1, py1, 0.0, u1, v1, 0.0, 0.0,
                px1, py0, 0.0, u1, v0, 0.0, 0.0,
            ],
            dtype=np.float32,
        )

    # ------------------------------------------------------------------
    # Public draw API
    # ------------------------------------------------------------------

    def draw_rect(
        self, x: float, y: float, w: float, h: float,
        color: tuple[float, float, float, float],
        border_radius: float = 0,
    ) -> None:
        """Draw a filled rectangle. ``border_radius`` is currently
        ignored (the legacy implementation also ignored it)."""
        if w <= 0 or h <= 0:
            return
        self._bind_ui_shader_solid(color)
        verts = self._emit_quad(x, y, x + w, y + h, 0.0, 0.0, 1.0, 1.0)
        self._ctx.draw_immediate_triangles(verts, 6)

    def draw_rect_outline(
        self, x: float, y: float, w: float, h: float,
        color: tuple[float, float, float, float],
        thickness: float = 1.0,
    ) -> None:
        """Draw an unfilled rectangle outline."""
        self.draw_rect(x, y, w, thickness, color)                   # top
        self.draw_rect(x, y + h - thickness, w, thickness, color)   # bottom
        self.draw_rect(x, y, thickness, h, color)                   # left
        self.draw_rect(x + w - thickness, y, thickness, h, color)   # right

    def draw_line(
        self, x1: float, y1: float, x2: float, y2: float,
        color: tuple[float, float, float, float],
        thickness: float = 1.0,
    ) -> None:
        """Draw a thick line between two pixel coordinates."""
        dx = x2 - x1
        dy = y2 - y1
        length = math.sqrt(dx * dx + dy * dy)
        if length < 0.001:
            return

        half = thickness / 2.0
        # Perpendicular unit vector × half-thickness
        nx = -dy / length * half
        ny = dx / length * half

        # Quad corners in pixel coords. Naming mirrors `_emit_quad`
        # expectations (tl/bl/br/tr) so winding stays consistent.
        ax, ay = x1 + nx, y1 + ny  # "TL" — start, +normal
        bx, by = x1 - nx, y1 - ny  # "BL" — start, -normal
        cx, cy = x2 - nx, y2 - ny  # "BR" — end, -normal
        dx_, dy_ = x2 + nx, y2 + ny  # "TR" — end, +normal

        self._bind_ui_shader_solid(color)
        verts = np.array(
            [
                ax, ay, 0.0, 0.0, 0.0, 0.0, 0.0,  # "TL"
                bx, by, 0.0, 0.0, 1.0, 0.0, 0.0,  # "BL"
                cx, cy, 0.0, 1.0, 1.0, 0.0, 0.0,  # "BR"
                ax, ay, 0.0, 0.0, 0.0, 0.0, 0.0,  # "TL"
                cx, cy, 0.0, 1.0, 1.0, 0.0, 0.0,  # "BR"
                dx_, dy_, 0.0, 1.0, 0.0, 0.0, 0.0,  # "TR"
            ],
            dtype=np.float32,
        )
        self._ctx.draw_immediate_triangles(verts, 6)

    # ------------------------------------------------------------------
    # Text
    # ------------------------------------------------------------------

    def draw_text(
        self, x: float, y: float, text: str,
        color: tuple[float, float, float, float],
        font_size: float = 14,
    ) -> None:
        """Draw text at the given pixel position. ``y`` is the
        baseline (legacy convention), not the top of the text box."""
        font = self.font
        if not font or not text or self._text2d is None:
            return

        scale = font_size / font.size
        ascent = font.ascent if hasattr(font, "ascent") else font.size

        # Translate baseline → top-of-glyph for Text2DRenderer, which
        # uses top-left anchoring.
        top_y = y - ascent * scale

        self._text2d.draw(
            text, x, top_y,
            color=color, size=float(font_size), anchor="left",
        )

    def draw_text_centered(
        self, cx: float, cy: float, text: str,
        color: tuple[float, float, float, float],
        font_size: float = 14,
    ) -> None:
        """Draw text centered on (cx, cy)."""
        font = self.font
        if not font or not text or self._text2d is None:
            return

        # Legacy semantics: convert to a draw_text call at the baseline.
        scale = font_size / font.size
        text_width = sum(
            font.glyphs[ch]["size"][0] * scale
            for ch in text if ch in font.glyphs
        )
        x = cx - text_width / 2
        y = cy + font_size / 2  # baseline offset (legacy)
        self.draw_text(x, y, text, color, font_size)

    def measure_text(
        self, text: str, font_size: float = 14,
    ) -> tuple[float, float]:
        """Measure pixel (width, height) of ``text`` at ``font_size``."""
        font = self.font
        if not font or not text:
            return (0.0, 0.0)

        font.ensure_glyphs(text)

        scale = font_size / font.size
        width = sum(
            font.glyphs[ch]["size"][0] * scale
            for ch in text if ch in font.glyphs
        )
        return (width, float(font_size))

    # ------------------------------------------------------------------
    # Images
    # ------------------------------------------------------------------

    def draw_image(
        self, x: float, y: float, w: float, h: float,
        texture_handle,
        tint: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
    ) -> None:
        """Draw an RGBA texture at pixel coordinates, multiplied by ``tint``.

        Accepts either a tgfx2 ``Tgfx2TextureHandle`` (returned from
        ``upload_texture`` / ``load_image``) or a legacy tgfx1
        ``GPUTextureHandle`` (created by widgets that still call
        ``graphics.create_texture`` directly — notably Canvas). tgfx1
        handles are wrapped as non-owning tgfx2 handles for the
        duration of this draw call and destroyed afterwards. This
        shim will go away in Phase 5 when Canvas migrates.
        """
        if w <= 0 or h <= 0 or texture_handle is None:
            return

        # Detect legacy tgfx1 GPUTextureHandle by its distinctive
        # methods and wrap it as a tgfx2 handle. Tgfx2TextureHandle
        # is a POD id struct with no get_id method.
        wrapped_handle = None
        if isinstance(texture_handle, Tgfx2TextureHandle):
            tex2 = texture_handle
        elif hasattr(texture_handle, "get_id"):
            tex2 = wrap_gl_texture_as_tgfx2(
                self._holder,
                texture_handle.get_id(),
                texture_handle.get_width(),
                texture_handle.get_height(),
                PIXEL_RGBA8,
            )
            wrapped_handle = tex2  # destroy after draw
        else:
            return

        ctx = self._ctx
        ctx.bind_shader(self._ui_vs, self._ui_fs)
        proj = _build_ortho_pixel_to_ndc(
            float(self._viewport_w), float(self._viewport_h),
        )
        ctx.set_uniform_mat4("u_projection", proj.flatten().tolist(), True)
        ctx.set_uniform_vec4(
            "u_color",
            float(tint[0]), float(tint[1]),
            float(tint[2]), float(tint[3]),
        )
        ctx.set_uniform_int("u_texture_mode", 2)
        ctx.set_uniform_int("u_texture", 0)
        ctx.bind_sampled_texture(0, tex2)

        verts = self._emit_quad(x, y, x + w, y + h, 0.0, 0.0, 1.0, 1.0)
        ctx.draw_immediate_triangles(verts, 6)

        # Non-owning wrappers of legacy GL textures must be released.
        # The underlying GL texture is untouched — only the HandlePool
        # entry is freed. Safe to do immediately because the draw
        # above already flushed synchronously.
        if wrapped_handle is not None:
            self._holder.destroy_texture(wrapped_handle)

    def upload_texture(self, data: np.ndarray) -> Tgfx2TextureHandle:
        """Upload a numpy RGBA array as a new GPU texture.

        Parameters
        ----------
        data : np.ndarray
            Shape (H, W, 4) uint8 RGBA.
        """
        if self._holder is None:
            raise RuntimeError(
                "UIRenderer.upload_texture called before first begin() — "
                "the Tgfx2Context is not initialised yet"
            )
        h, w = data.shape[0], data.shape[1]
        flat = np.ascontiguousarray(data).reshape(-1)
        return self._holder.create_texture_rgba8(w, h, flat)

    def update_texture(
        self, handle: Tgfx2TextureHandle, data: np.ndarray,
    ) -> None:
        """Replace the full contents of an existing GPU texture.

        ``data`` must match the texture's original (width, height,
        RGBA) dimensions.
        """
        if self._holder is None:
            raise RuntimeError(
                "UIRenderer.update_texture called before first begin()"
            )
        flat = np.ascontiguousarray(data).reshape(-1)
        self._holder.upload_texture(handle, flat)

    def update_texture_region(
        self, handle: Tgfx2TextureHandle,
        x: int, y: int, w: int, h: int,
        data: np.ndarray,
    ) -> None:
        """Upload a rectangular region of an existing GPU texture.

        ``data`` is the **region** (shape ``(h, w, channels)``), not
        the full image — tightly packed RGBA bytes. Origin is top-left
        in pixel space, same convention as the rest of the UIRenderer.
        Used by Canvas for incremental overlay updates during painting.
        """
        if self._holder is None:
            raise RuntimeError(
                "UIRenderer.update_texture_region called before first begin()"
            )
        flat = np.ascontiguousarray(data).reshape(-1)
        self._holder.upload_texture_region(
            handle, int(x), int(y), int(w), int(h), flat,
        )

    def destroy_texture(self, handle: Tgfx2TextureHandle) -> None:
        """Release a GPU texture previously returned by ``upload_texture``."""
        if self._holder is None or handle is None:
            return
        self._holder.destroy_texture(handle)

    def draw_external_gl_texture(
        self, x: float, y: float, w: float, h: float,
        gl_tex_id: int, tex_w: int, tex_h: int,
        *,
        flip_v: bool = False,
        tint: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
    ) -> None:
        """Draw a raw GL RGBA texture id as a subregion of the current
        UI pass.

        Used by Viewport3D to composite an external 3D engine's
        shared color texture onto the UI offscreen. The texture id
        must be valid in the current GL context (typically via a
        shared GL context / share group).

        ``flip_v=True`` samples the texture with V axis inverted —
        use this for GL-native render targets where texel (0, 0) is
        the bottom-left corner.
        """
        if w <= 0 or h <= 0 or gl_tex_id == 0 or self._ctx is None:
            return

        tex2 = wrap_gl_texture_as_tgfx2(
            self._holder, int(gl_tex_id),
            int(tex_w), int(tex_h), PIXEL_RGBA8,
        )
        try:
            ctx = self._ctx
            ctx.bind_shader(self._ui_vs, self._ui_fs)
            proj = _build_ortho_pixel_to_ndc(
                float(self._viewport_w), float(self._viewport_h),
            )
            ctx.set_uniform_mat4("u_projection", proj.flatten().tolist(), True)
            ctx.set_uniform_vec4(
                "u_color",
                float(tint[0]), float(tint[1]),
                float(tint[2]), float(tint[3]),
            )
            ctx.set_uniform_int("u_texture_mode", 2)
            ctx.set_uniform_int("u_texture", 0)
            ctx.bind_sampled_texture(0, tex2)

            if flip_v:
                verts = self._emit_quad(x, y, x + w, y + h, 0.0, 1.0, 1.0, 0.0)
            else:
                verts = self._emit_quad(x, y, x + w, y + h, 0.0, 0.0, 1.0, 1.0)
            ctx.draw_immediate_triangles(verts, 6)
        finally:
            # Non-owning wrapper: release the HandlePool entry but
            # leave the underlying GL texture alone.
            self._holder.destroy_texture(tex2)

    def load_image(self, path: str) -> Tgfx2TextureHandle:
        """Load an image file and upload it as a GPU texture."""
        from PIL import Image
        img = Image.open(path).convert("RGBA")
        data = np.array(img, dtype=np.uint8)
        return self.upload_texture(data)
