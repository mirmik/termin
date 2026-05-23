"""tgfx2-backed renderer for the widget-based UI system.

``UIRenderer(font=None)``, ``font`` property, ``begin``, ``end``,
``begin_clip``, ``end_clip``, ``draw_rect``, ``draw_rect_outline``,
``draw_line``, ``draw_text``, ``draw_text_centered``, ``draw_image``,
``upload_texture``, ``load_image``, ``measure_text``.

Internally the renderer drives a ``Tgfx2Context`` (created lazily on
first ``begin()``) and keeps an offscreen native tgfx2 color+depth
texture pair as its draw target. ``end_compose()`` returns that color
texture to the host presenter. Common 2D primitives, simple textures
and text are delegated to the C++ ``Canvas2DRenderer``. The local UI
shader remains for image preview modes that need channel selection or
HDR highlighting.
"""

from __future__ import annotations

import math

import numpy as np

from tgfx import Canvas2DRenderer, TcShader
from tgfx.font import FontTextureAtlas, get_default_font
from tgfx._tgfx_native import (
    Tgfx2Context,
    Tgfx2TextureHandle,
    Tgfx2ShaderStage,
    tc_shader_ensure_tgfx2,
    CULL_NONE,
)
from tcbase.profiler import Profiler
from tcbase import log

_prof = Profiler.instance()


# UI shader: solid colour (mode 0) and RGBA-image sampling (mode 2).
# Font-atlas sampling lives in Text2DRenderer; this shader does not
# carry mode 1.
#
# Single source for both backends. Under Vulkan (`#define VULKAN 1`
# injected by shaderc) the per-draw state lives in a `layout(push_
# constant)` block; under OpenGL it is a plain UBO bound at binding
# 14 (the slot used by tgfx2's push-constant ring buffer — see
# `TGFX2_PUSH_CONSTANTS_BINDING`). Same `UIPush pc` struct on both
# sides, so the Python packer does not fork. `#version 450 core`
# requires GL 4.3+ core (BackendWindow bumps the context to match).
_UI_SHADER_COMMON_PUSH = """
struct UIPushData {
    mat4 u_projection;
    vec4 u_color;
    int  u_texture_mode;
    int  u_channel_mode;
    int  u_highlight_hdr;
};
#ifdef VULKAN
layout(push_constant) uniform UIPushBlock { UIPushData pc; };
#else
layout(std140, binding = 14) uniform UIPushBlock { UIPushData pc; };
#endif
"""

UI_VERTEX_SHADER = """#version 450 core
""" + _UI_SHADER_COMMON_PUSH + """
layout(location=0) in vec3 a_pos;    // (x_pixel, y_pixel, 0)
layout(location=1) in vec4 a_uv_pad; // (u, v, _, _)

layout(location=0) out vec2 v_uv;

void main() {
    gl_Position = pc.u_projection * vec4(a_pos.xy, 0.0, 1.0);
    v_uv = a_uv_pad.xy;
}
"""

UI_FRAGMENT_SHADER = """#version 450 core
""" + _UI_SHADER_COMMON_PUSH + """
layout(binding = 4) uniform sampler2D u_texture;

layout(location=0) in vec2 v_uv;
layout(location=0) out vec4 FragColor;

void main() {
    if (pc.u_texture_mode == 2) {
        vec4 c = texture(u_texture, v_uv);
        vec3 rgb;
        if (pc.u_channel_mode == 5)      rgb = vec3(pow(clamp(1.0 - c.r, 0.0, 1.0), 0.25));
        else if (pc.u_channel_mode == 1) rgb = vec3(c.r);
        else if (pc.u_channel_mode == 2) rgb = vec3(c.g);
        else if (pc.u_channel_mode == 3) rgb = vec3(c.b);
        else if (pc.u_channel_mode == 4) rgb = vec3(c.a);
        else                             rgb = c.rgb;
        if (pc.u_highlight_hdr == 1) {
            float max_val = max(max(c.r, c.g), c.b);
            if (max_val > 1.0) {
                float intensity = clamp((max_val - 1.0) / 2.0, 0.0, 1.0);
                rgb = mix(rgb, vec3(1.0, 0.0, 1.0), 0.5 + intensity * 0.5);
            }
        }
        float alpha = pc.u_channel_mode == 0 ? c.a : 1.0;
        FragColor = vec4(rgb, alpha) * pc.u_color;
    } else {
        FragColor = pc.u_color;
    }
}
"""

# Python-side struct layout mirroring UIPushData. mat4 = 64 bytes
# std140-aligned, vec4 = 16 bytes, int = 4 bytes (padded to 16 in
# std140 BUT push_constant uses scalar/natural alignment; we align
# manually). Total 96 bytes — well under the 128-byte push-constant
# range that VulkanRenderDevice reserves. Encoded little-endian
# native floats (x86_64 / arm64).
import struct as _struct
_UI_PUSH_FMT = "=16f4f3I4x"   # projection, color, texture_mode/channel/hdr + pad
_UI_PUSH_SIZE = _struct.calcsize(_UI_PUSH_FMT)


def _build_ortho_pixel_to_ndc(w: float, h: float) -> np.ndarray:
    """Ortho projection: pixel coords (y+ down) → clip-space (y+ down).

    Matches the unified Vulkan-native NDC convention used in tgfx:
    pixel_y=0 (top of the window) maps to clip_y=-1, pixel_y=h maps
    to clip_y=+1. On OpenGL this is enforced by a one-time
    glClipControl(GL_UPPER_LEFT) in OpenGLRenderDevice.
    """
    if w <= 0 or h <= 0:
        return np.eye(4, dtype=np.float32)
    return np.array(
        [
            [2.0 / w,  0.0,     0.0, -1.0],
            [0.0,     2.0 / h,  0.0, -1.0],
            [0.0,     0.0,      1.0,  0.0],
            [0.0,     0.0,      0.0,  1.0],
        ],
        dtype=np.float32,
    )


class UIRenderer:
    """UI widget renderer backed by tgfx2."""

    def __init__(self, graphics: Tgfx2Context,
                 font: FontTextureAtlas | None = None):
        """UIRenderer backed by tgfx2.

        Parameters
        ----------
        graphics : Tgfx2Context
            The process-wide tgfx2 context (device + RenderContext2) to
            draw through. Obtained from the application host:
            ``Tgfx2Context.from_window(window.device_ptr(), window.context_ptr())``
            at the top level, or ``Tgfx2Context.from_context(ctx2)``
            inside framegraph passes. Required — UIRenderer never
            creates a Tgfx2Context on its own, because that would mint
            a second IRenderDevice and break cross-widget TextureHandle
            sharing.
        font : FontTextureAtlas or None
            Default font; falls back to the process-default atlas.
        """
        if graphics is None:
            raise ValueError(
                "UIRenderer requires a graphics= Tgfx2Context. Get one "
                "from the host (Tgfx2Context.from_window) or from an "
                "active RenderContext2 (Tgfx2Context.from_context).")
        self._font = font

        # Viewport dimensions in pixels. Updated each begin().
        self._viewport_w: int = 0
        self._viewport_h: int = 0

        # CPU scissor stack for nested begin_clip/end_clip. Stored in
        # top-left-origin viewport pixel coordinates.
        self._clip_stack: list[tuple[int, int, int, int]] = []

        # --- tgfx2 resources ---
        self._graphics: Tgfx2Context = graphics
        # Do NOT pre-fetch `graphics.context` here: the returned wrapper
        # uses nanobind's `reference_internal` which creates a Python-
        # level cycle (wrapper keeps graphics alive, graphics object
        # keeps a pointer to itself through nanobind's type registry).
        # The cycle collector then tries to break it at shutdown and
        # hits undefined order, segfaulting when it calls free on an
        # object whose backing C++ already died. Fetch lazily on first
        # begin().
        self._ctx = None
        self._canvas: Canvas2DRenderer | None = None
        self._canvas_active: bool = False

        self._ui_tc_shader: TcShader | None = None
        self._ui_vs = None
        self._ui_fs = None

        # Owned offscreen color + depth textures. Allocated on first
        # begin() / reallocated when the viewport size changes.
        self._offscreen_color_tex: Tgfx2TextureHandle | None = None
        self._offscreen_depth_tex: Tgfx2TextureHandle | None = None
        self._offscreen_size: tuple[int, int] = (0, 0)

        # 1×1 white fallback texture bound at sampler slot 4 on every
        # solid-colour draw (see _ensure_init for the rationale).
        self._placeholder_tex: Tgfx2TextureHandle | None = None

        # Set in begin() if we were the ones to open the frame on the
        # lender's RenderContext2. end_compose() uses it to decide
        # whether to close symmetrically.
        self._opened_frame: bool = False

        # Color attachment the current begin()/end_compose() is drawing
        # into — either _offscreen_color_tex (standalone) or the host's
        # target_color (in-scene).
        self._current_target: Tgfx2TextureHandle | None = None
        self._trace_frame: int = 0

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
    def graphics(self) -> Tgfx2Context:
        """The Tgfx2Context the renderer draws through.

        Publicly exposed for embedded sub-renderers (tcplot Plot3D,
        custom widgets) that want to issue their own tgfx2 draw calls
        into the same render pass.
        """
        return self._graphics

    # ------------------------------------------------------------------
    # Lazy tgfx2 init
    # ------------------------------------------------------------------

    def _ensure_init(self, w: int, h: int, need_offscreen: bool = True) -> None:
        """Compile the UI shader and (if needed) allocate the offscreen
        FBO. Called on the first begin() and whenever the viewport size
        changes. The Tgfx2Context is already set up by __init__.

        ``need_offscreen`` is False on the framegraph in-scene path: the
        host hands us its own target_color, so we skip allocating the
        renderer's own offscreen color/depth pair.
        """
        if self._ctx is None:
            # Fetched lazily — see __init__ comment on cycle collection.
            self._ctx = self._graphics.context
        if self._canvas is None:
            self._canvas = Canvas2DRenderer(self.font)

        if self._ui_vs is None:
            # Register the UI shader with the tc_shader registry — hash-
            # based dedup keeps compiled VkShaderModules / GL programs
            # alive across UIRenderer instances (each new RenderContext2
            # on Play/Stop otherwise re-runs shaderc).
            if self._ui_tc_shader is None:
                self._ui_tc_shader = TcShader.from_sources(
                    UI_VERTEX_SHADER, UI_FRAGMENT_SHADER,
                    geometry="", name="UIEngineVSFS")
            pair = tc_shader_ensure_tgfx2(self._ctx, self._ui_tc_shader)
            self._ui_vs = pair.vs
            self._ui_fs = pair.fs
            if not self._ui_vs or not self._ui_fs:
                raise RuntimeError("UIRenderer: UI shader compile failed")

        if need_offscreen and self._offscreen_size != (w, h):
            if self._offscreen_color_tex is not None:
                self._graphics.destroy_texture(self._offscreen_color_tex)
                self._offscreen_color_tex = None
            if self._offscreen_depth_tex is not None:
                self._graphics.destroy_texture(self._offscreen_depth_tex)
                self._offscreen_depth_tex = None
            self._offscreen_color_tex = self._graphics.create_color_attachment(w, h)
            self._offscreen_depth_tex = self._graphics.create_depth_attachment(w, h)
            self._offscreen_size = (w, h)

        if self._placeholder_tex is None:
            # 1×1 white texture bound at binding 4 whenever the UI shader
            # runs in solid-colour mode (texture_mode=0). Vulkan's
            # validator rejects draws that leave a shader-declared
            # `layout(binding=4) uniform sampler2D` slot empty even if
            # the fragment branch never samples from it. OpenGL doesn't
            # care, but the same placeholder on both sides keeps the
            # bind sequence identical and cheap.
            white = np.array([[[255, 255, 255, 255]]], dtype=np.uint8)
            self._placeholder_tex = self._graphics.create_texture_rgba8(
                1, 1, white.reshape(-1))

    # ------------------------------------------------------------------
    # Frame lifecycle
    # ------------------------------------------------------------------

    def begin(
        self,
        viewport_w: int,
        viewport_h: int,
        background_color: tuple[float, float, float, float] | None = None,
        target_color=None,
    ) -> None:
        """Begin UI rendering pass.

        Parameters
        ----------
        target_color : Tgfx2TextureHandle or None
            Externally-provided color attachment to draw into. When set
            (framegraph in-scene path), the pass opens with LoadOp::Load
            and the widgets composite on top of whatever the previous
            pass rendered — no offscreen, no final blit. When ``None``
            (standalone hosts: the project-picker launcher, tcgui demos,
            legacy ``render()``), the renderer draws into its own
            offscreen color+depth pair, which ``end_compose`` then hands
            back to the host to present.
        background_color : (r, g, b, a) or None
            Only meaningful in standalone mode (target_color is None) —
            the colour the offscreen is cleared to before widgets draw.
            Ignored when target_color is set (otherwise we'd wipe the
            host's previous content every frame).
        """
        self._viewport_w = int(viewport_w)
        self._viewport_h = int(viewport_h)
        self._trace_frame += 1
        trace = self._trace_frame <= 40 or self._trace_frame % 120 == 0
        if trace:
            log.info(
                f"[UIRenderer] compose#{self._trace_frame}: begin "
                f"size={self._viewport_w}x{self._viewport_h} "
                f"external_target={target_color is not None}")

        using_external_target = target_color is not None

        if trace:
            log.info(f"[UIRenderer] compose#{self._trace_frame}: ensure_init begin")
        self._ensure_init(self._viewport_w, self._viewport_h,
                          need_offscreen=not using_external_target)
        if trace:
            log.info(f"[UIRenderer] compose#{self._trace_frame}: ensure_init end")

        ctx = self._ctx

        # Open a frame if the lender hasn't. Standalone hosts (the
        # project-picker launcher, tcgui demos) just call render_compose
        # and expect the renderer to manage the frame itself; framegraph
        # passes enter with a frame already live from the engine's tick.
        # Track who opened it so end_compose can close symmetrically.
        self._opened_frame = not ctx.in_frame
        if self._opened_frame:
            if trace:
                log.info(f"[UIRenderer] compose#{self._trace_frame}: begin_frame begin")
            ctx.begin_frame()
            if trace:
                log.info(f"[UIRenderer] compose#{self._trace_frame}: begin_frame end")

        if using_external_target:
            # In-scene path: draw straight into the host's target with
            # LoadOp::Load so the previous pass' content stays visible
            # under UI-transparent regions. No depth attached — UI
            # draws with depth_test=False anyway.
            if trace:
                log.info(f"[UIRenderer] compose#{self._trace_frame}: begin_pass external begin")
            ctx.begin_pass(
                color=target_color,
                clear_color_enabled=False,
                clear_depth_enabled=False,
            )
            if trace:
                log.info(f"[UIRenderer] compose#{self._trace_frame}: begin_pass external end")
            self._current_target = target_color
        else:
            # Standalone path: own offscreen cleared to background_color
            # (transparent by default). The clear colour leaks through
            # any UI-transparent pixels once the host presents/blits.
            # Depth is cleared to 1.0 so 3D embedded renderers (tcplot
            # Plot3D, Viewport3D) get a fresh depth buffer each frame.
            if background_color is not None:
                bg_r, bg_g, bg_b, bg_a = background_color
            else:
                bg_r = bg_g = bg_b = bg_a = 0.0
            if trace:
                log.info(f"[UIRenderer] compose#{self._trace_frame}: begin_pass offscreen begin")
            ctx.begin_pass(
                color=self._offscreen_color_tex,
                depth=self._offscreen_depth_tex,
                clear_color_enabled=True,
                r=bg_r, g=bg_g, b=bg_b, a=bg_a,
                clear_depth=1.0,
                clear_depth_enabled=True,
            )
            if trace:
                log.info(f"[UIRenderer] compose#{self._trace_frame}: begin_pass offscreen end")
            self._current_target = self._offscreen_color_tex
        ctx.set_viewport(0, 0, self._viewport_w, self._viewport_h)
        ctx.set_cull(CULL_NONE)
        ctx.set_depth_test(False)
        ctx.set_blend(True)
        # Explicit blend func — don't rely on defaults. Other renderers
        # on the same shared Tgfx2Context (the diffusion-editor's
        # GPUCompositor) set their own blend func to One / OneMinusSrcAlpha
        # for premultiplied-alpha compositing, and that leaks into the
        # UIRenderer pass if we don't reassert ours. Symptom was white
        # halos around text and red-tinted image after the compositor
        # ran. Standard over-alpha for color.
        from tgfx._tgfx_native import Tgfx2BlendFactor
        ctx.set_blend_func(Tgfx2BlendFactor.SrcAlpha,
                           Tgfx2BlendFactor.OneMinusSrcAlpha)

        self._canvas.set_default_font(self.font)
        if trace:
            log.info(f"[UIRenderer] compose#{self._trace_frame}: canvas.begin begin")
        self._canvas.begin(self._ctx, self._viewport_w, self._viewport_h)
        if trace:
            log.info(f"[UIRenderer] compose#{self._trace_frame}: canvas.begin end")
        self._canvas_active = True

    def end(self):
        """End UI rendering pass and return the composite texture.

        Raw default-framebuffer presentation is not part of UIRenderer.
        Hosts must present the returned TextureHandle through their
        platform window/surface layer.
        """
        return self.end_compose()

    def end_compose(self):
        """End the UI pass and return the offscreen composite texture.

        Returns the tgfx2 TextureHandle the caller should publish to
        the window surface (BackendWindow.present, custom GL blit,
        etc.). ``None`` if begin() was never called.
        """
        if self._ctx is None:
            return None

        trace = getattr(self, "_trace_frame", 0) <= 40 or getattr(self, "_trace_frame", 0) % 120 == 0
        if self._canvas is not None and self._canvas_active:
            if trace:
                log.info(f"[UIRenderer] compose#{self._trace_frame}: canvas.end begin")
            self._canvas.end()
            if trace:
                log.info(f"[UIRenderer] compose#{self._trace_frame}: canvas.end end")
            self._canvas_active = False
        if trace:
            log.info(f"[UIRenderer] compose#{self._trace_frame}: end_pass begin")
        self._ctx.end_pass()
        if trace:
            log.info(f"[UIRenderer] compose#{self._trace_frame}: end_pass end")
        # Match the begin_frame decision from begin(): close only the
        # frame we opened. Command list ownership belongs to whoever
        # started it.
        if self._opened_frame:
            if trace:
                log.info(f"[UIRenderer] compose#{self._trace_frame}: end_frame begin")
            self._ctx.end_frame()
            if trace:
                log.info(f"[UIRenderer] compose#{self._trace_frame}: end_frame end")
            self._opened_frame = False

        self._clip_stack.clear()

        if trace:
            log.info(
                f"[UIRenderer] compose#{self._trace_frame}: end texture={self._offscreen_color_tex}")
        return self._offscreen_color_tex

    def close(self) -> None:
        """Release owned offscreen textures. Call before the GL
        context the holder lives on gets destroyed."""
        if self._graphics is None:
            return
        if self._offscreen_color_tex is not None:
            self._graphics.destroy_texture(self._offscreen_color_tex)
            self._offscreen_color_tex = None
        if self._offscreen_depth_tex is not None:
            self._graphics.destroy_texture(self._offscreen_depth_tex)
            self._offscreen_depth_tex = None
        self._offscreen_size = (0, 0)
        if self._canvas is not None:
            self._canvas.release_gpu()

    # ------------------------------------------------------------------
    # Scissor / clip stack
    # ------------------------------------------------------------------

    def begin_clip(self, x: float, y: float, w: float, h: float) -> None:
        """Push scissor clip rect. Nested clips are intersected.

        Coordinates are top-left origin in pixels — same convention the
        widget tree uses. tgfx2's ``set_scissor`` is backend-neutral on
        that contract: Vulkan uses it verbatim, OpenGL internally flips
        to bottom-left. Keep no manual flip here — it would double-flip
        on one of the backends and leave text input content outside the
        clip rect on the other.
        """
        ix0 = math.floor(x)
        iy0 = math.floor(y)
        ix1 = math.ceil(x + w)
        iy1 = math.ceil(y + h)

        if self._clip_stack:
            px, py, pw, ph = self._clip_stack[-1]
            ix0 = max(ix0, px)
            iy0 = max(iy0, py)
            ix1 = min(ix1, px + pw)
            iy1 = min(iy1, py + ph)

        ix0 = max(0, ix0)
        iy0 = max(0, iy0)
        ix1 = min(self._viewport_w, ix1)
        iy1 = min(self._viewport_h, iy1)

        iw = max(0, ix1 - ix0)
        ih = max(0, iy1 - iy0)
        if iw == 0:
            ix0 = min(max(0, ix0), self._viewport_w)
        if ih == 0:
            iy0 = min(max(0, iy0), self._viewport_h)

        self._clip_stack.append((ix0, iy0, iw, ih))
        if self._canvas is not None and self._canvas_active:
            self._canvas.begin_clip(x, y, w, h)
        else:
            self._ctx.set_scissor(ix0, iy0, iw, ih)

    def end_clip(self) -> None:
        """Pop scissor clip rect. Restore parent clip or disable."""
        if self._clip_stack:
            self._clip_stack.pop()
        if self._clip_stack:
            px, py, pw, ph = self._clip_stack[-1]
            if self._canvas is not None and self._canvas_active:
                self._canvas.end_clip()
            else:
                self._ctx.set_scissor(px, py, pw, ph)
        else:
            if self._canvas is not None and self._canvas_active:
                self._canvas.end_clip()
            else:
                self._ctx.clear_scissor()

    # ------------------------------------------------------------------
    # Primitive drawing helpers
    # ------------------------------------------------------------------

    def _suspend_canvas_for_legacy_draw(self) -> None:
        if self._canvas is not None and self._canvas_active:
            self._canvas.end()
            self._canvas_active = False

    def _resume_canvas_after_legacy_draw(self) -> None:
        if self._canvas is None or self._ctx is None:
            return
        self._canvas.set_default_font(self.font)
        self._canvas.begin(self._ctx, self._viewport_w, self._viewport_h)
        self._canvas_active = True
        for x, y, w, h in self._clip_stack:
            self._canvas.begin_clip(x, y, w, h)

    def _push_ui_state(
        self,
        color: tuple[float, float, float, float],
        texture_mode: int,
        channel_mode: int = 0,
        highlight_hdr: bool = False,
    ) -> None:
        """Pack the per-draw UI state into a push-constant block and
        bind it. Single byte layout for both backends — under Vulkan
        vkCmdPushConstants ships it; under OpenGL the tgfx2 ring UBO
        at binding 14 picks it up. Shader source is the same on both
        sides (`pc.u_projection`, `pc.u_color`, texture mode and preview
        channel flags)."""
        ctx = self._ctx
        ctx.bind_shader(self._ui_vs, self._ui_fs)
        # Projection is row-major in Python but GLSL expects column-major
        # mat4. Transpose here once instead of a shader-side transpose
        # marker (set_uniform_mat4 had a transpose flag; push_constants
        # is raw bytes).
        self._suspend_canvas_for_legacy_draw()
        proj = _build_ortho_pixel_to_ndc(
            float(self._viewport_w), float(self._viewport_h),
        )
        proj_cm = np.ascontiguousarray(proj.T, dtype=np.float32)
        data = _struct.pack(
            _UI_PUSH_FMT,
            *proj_cm.flatten().tolist(),
            float(color[0]), float(color[1]),
            float(color[2]), float(color[3]),
            int(texture_mode),
            int(channel_mode),
            1 if highlight_hdr else 0,
        )
        # np.frombuffer would give a read-only view; nanobind needs a
        # C-contiguous writable-ish ndarray, so copy into a fresh array.
        ctx.set_push_constants(np.asarray(bytearray(data), dtype=np.uint8))

    def _bind_ui_shader_solid(
        self, color: tuple[float, float, float, float],
    ) -> None:
        # Kept as a thin wrapper so the draw_rect / draw_line call sites
        # don't have to know about push constants. The placeholder bind
        # is there so Vulkan's validator sees a valid descriptor set
        # even when the fragment shader's sample path is unreachable.
        self._push_ui_state(color, 0)
        if self._placeholder_tex is not None:
            self._ctx.bind_sampled_texture(4, self._placeholder_tex)

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
        if self._canvas is not None and self._canvas_active:
            self._canvas.draw_rect(x, y, w, h, color, border_radius)

    def draw_rect_outline(
        self, x: float, y: float, w: float, h: float,
        color: tuple[float, float, float, float],
        thickness: float = 1.0,
    ) -> None:
        """Draw an unfilled rectangle outline."""
        if self._canvas is not None and self._canvas_active:
            self._canvas.draw_rect_outline(x, y, w, h, color, thickness)

    def draw_line(
        self, x1: float, y1: float, x2: float, y2: float,
        color: tuple[float, float, float, float],
        thickness: float = 1.0,
    ) -> None:
        """Draw a thick line between two pixel coordinates."""
        if self._canvas is not None and self._canvas_active:
            self._canvas.draw_line(x1, y1, x2, y2, color, thickness)

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
        if not font or not text or self._canvas is None or not self._canvas_active:
            return

        # Canvas2DRenderer/Text2DRenderer use top-left anchoring, while
        # the public UIRenderer API historically takes a baseline y.
        top_y = y - font.ascent_at(font_size)

        with _prof.section("text2d.draw"):
            self._canvas.draw_text(
                text, x, top_y, float(font_size), color, font, "left",
            )

    def draw_text_centered(
        self, cx: float, cy: float, text: str,
        color: tuple[float, float, float, float],
        font_size: float = 14,
    ) -> None:
        """Draw text centered on (cx, cy)."""
        font = self.font
        if not font or not text:
            return

        with _prof.section("draw_text_centered.measure"):
            # Route through self.measure_text so glyphs get baked at
            # this size before the width query — otherwise the first
            # draw at a new size would centre on a zero width (atlas
            # has per-size caches; unbaked size means missing entries).
            text_width, _ = self.measure_text(text, font_size)
        x = cx - text_width / 2
        line_height = float(font.line_height_at(font_size))
        ascent = float(font.ascent_at(font_size))
        y = cy - line_height / 2 + ascent
        self.draw_text(x, y, text, color, font_size)

    def measure_text(
        self, text: str, font_size: float = 14,
    ) -> tuple[float, float]:
        """Measure pixel (width, height) of ``text`` at ``font_size``."""
        font = self.font
        if not font or not text:
            return (0.0, 0.0)

        # Bake glyphs at this size so the measurement is accurate for
        # strings we haven't drawn yet. CPU-only — GPU re-upload is
        # deferred to the next draw call (which passes a ctx).
        font.ensure_glyphs(text, font_size)
        return font.measure_text(text, font_size)

    def ascent_at(self, font_size: float = 14) -> float:
        font = self.font
        if not font:
            return font_size * 0.8
        return float(font.ascent_at(font_size))

    def line_height_at(self, font_size: float = 14) -> float:
        font = self.font
        if not font:
            return font_size
        return float(font.line_height_at(font_size))

    # ------------------------------------------------------------------
    # Images
    # ------------------------------------------------------------------

    def draw_image(
        self, x: float, y: float, w: float, h: float,
        texture_handle,
        tint: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
    ) -> None:
        """Draw an RGBA texture at pixel coordinates, multiplied by ``tint``.

        ``texture_handle`` is a ``Tgfx2TextureHandle`` from
        ``upload_texture`` / ``load_image``.
        """
        if w <= 0 or h <= 0 or texture_handle is None:
            return

        ctx = self._ctx

        if self._canvas is not None and self._canvas_active:
            self._canvas.draw_texture(texture_handle, x, y, w, h, tint)
        else:
            self._push_ui_state(tint, 2)
            ctx.bind_sampled_texture(4, texture_handle)
            verts = self._emit_quad(x, y, x + w, y + h, 0.0, 0.0, 1.0, 1.0)
            ctx.draw_immediate_triangles(verts, 6)
            self._resume_canvas_after_legacy_draw()

    def upload_texture(self, data: np.ndarray) -> Tgfx2TextureHandle:
        """Upload a numpy RGBA array as a new GPU texture.

        Parameters
        ----------
        data : np.ndarray
            Shape (H, W, 4) uint8 RGBA.
        """
        if self._graphics is None:
            raise RuntimeError(
                "UIRenderer.upload_texture called before first begin() — "
                "the Tgfx2Context is not initialised yet"
            )
        h, w = data.shape[0], data.shape[1]
        flat = np.ascontiguousarray(data).reshape(-1)
        return self._graphics.create_texture_rgba8(w, h, flat)

    def update_texture(
        self, handle: Tgfx2TextureHandle, data: np.ndarray,
    ) -> None:
        """Replace the full contents of an existing GPU texture.

        ``data`` must match the texture's original (width, height,
        RGBA) dimensions.
        """
        if self._graphics is None:
            raise RuntimeError(
                "UIRenderer.update_texture called before first begin()"
            )
        flat = np.ascontiguousarray(data).reshape(-1)
        self._graphics.upload_texture(handle, flat)

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
        if self._graphics is None:
            raise RuntimeError(
                "UIRenderer.update_texture_region called before first begin()"
            )
        flat = np.ascontiguousarray(data).reshape(-1)
        self._graphics.upload_texture_region(
            handle, int(x), int(y), int(w), int(h), flat,
        )

    def destroy_texture(self, handle: Tgfx2TextureHandle) -> None:
        """Release a GPU texture previously returned by ``upload_texture``."""
        if self._graphics is None or handle is None:
            return
        self._graphics.destroy_texture(handle)

    def draw_texture(
        self, x: float, y: float, w: float, h: float,
        handle: Tgfx2TextureHandle, tex_w: int, tex_h: int,
        *,
        flip_v: bool = False,
        channel_mode: int = 0,
        highlight_hdr: bool = False,
        tint: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
    ) -> None:
        """Draw a tgfx2 TextureHandle as a subregion of the current UI pass.

        The handle must belong to *this* renderer's device — i.e. both
        objects must share the same ``Tgfx2Context``. That invariant
        holds by construction in a BackendWindow-hosted editor where
        every renderer borrows one process-global context. Use this
        works on both OpenGL and Vulkan.

        ``flip_v=True`` samples the texture with V axis inverted —
        use this for GL-native render targets where texel (0, 0) is
        the bottom-left corner.
        """
        if w <= 0 or h <= 0 or handle is None or self._ctx is None:
            return

        if channel_mode == 0 and not highlight_hdr and self._canvas is not None and self._canvas_active:
            self._canvas.draw_texture(handle, x, y, w, h, tint, flip_v)
            return

        ctx = self._ctx
        self._push_ui_state(tint, 2, channel_mode, highlight_hdr)
        ctx.bind_sampled_texture(4, handle)

        if flip_v:
            verts = self._emit_quad(x, y, x + w, y + h, 0.0, 1.0, 1.0, 0.0)
        else:
            verts = self._emit_quad(x, y, x + w, y + h, 0.0, 0.0, 1.0, 1.0)
        ctx.draw_immediate_triangles(verts, 6)
        self._resume_canvas_after_legacy_draw()

    def load_image(self, path: str) -> Tgfx2TextureHandle:
        """Load an image file and upload it as a GPU texture."""
        from PIL import Image
        img = Image.open(path).convert("RGBA")
        data = np.array(img, dtype=np.uint8)
        return self.upload_texture(data)
