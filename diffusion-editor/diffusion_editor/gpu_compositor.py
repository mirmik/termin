"""GPUCompositor — tgfx2 native layer compositing with premultiplied alpha."""

from __future__ import annotations

import numpy as np
from tcbase import log

from .layer_stack import LayerStack
from .layer import Layer

from tgfx import TcShader
from tgfx._tgfx_native import (
    Tgfx2Context,
    Tgfx2TextureHandle,
    Tgfx2BlendFactor,
    tc_shader_ensure_tgfx2,
)

# ---------------------------------------------------------------------------
# GLSL sources
# ---------------------------------------------------------------------------

_VERT_SRC = """
#version 330 core
layout(location=0) in vec3 a_position;
layout(location=1) in vec4 a_uv_pad;
out vec2 v_uv;
void main() {
    v_uv = a_uv_pad.xy;
    gl_Position = vec4(a_position.xy, 0.0, 1.0);
}
"""

# Premultiplied alpha compositing fragment shader.
# Converts straight-alpha texture to premultiplied on the fly.
_COMPOSITE_FRAG_SRC = """
#version 330 core
uniform sampler2D u_texture;
uniform float u_opacity;
in vec2 v_uv;
out vec4 FragColor;
void main() {
    vec4 t = texture(u_texture, v_uv);
    float a = t.a * u_opacity;
    FragColor = vec4(t.rgb * a, a);
}
"""

# Un-premultiply shader: converts premultiplied alpha back to straight alpha
# for display by the Canvas base class.
_UNPREMUL_FRAG_SRC = """
#version 330 core
uniform sampler2D u_texture;
in vec2 v_uv;
out vec4 FragColor;
void main() {
    vec4 pm = texture(u_texture, v_uv);
    if (pm.a > 0.001)
        FragColor = vec4(pm.rgb / pm.a, pm.a);
    else
        FragColor = vec4(0.0);
}
"""


def _full_screen_quad_verts() -> np.ndarray:
    # Vertex format matches draw_immediate_triangles: 7 floats per vertex
    # (x, y, z, r, g, b, a). We repurpose RGBA as (u, v, _, _) so the
    # shader can read UV out of loc 1 — same pattern tgfx2 bindings
    # document for immediate quads.
    # Clip-space -1..1 covers the whole offscreen target.
    return np.array([
        # x,    y,    z,    u,    v,    _,    _
        -1.0, -1.0, 0.0,  0.0, 0.0, 0.0, 0.0,
         1.0, -1.0, 0.0,  1.0, 0.0, 0.0, 0.0,
         1.0,  1.0, 0.0,  1.0, 1.0, 0.0, 0.0,
        -1.0, -1.0, 0.0,  0.0, 0.0, 0.0, 0.0,
         1.0,  1.0, 0.0,  1.0, 1.0, 0.0, 0.0,
        -1.0,  1.0, 0.0,  0.0, 1.0, 0.0, 0.0,
    ], dtype=np.float32)


class GPUCompositor:
    """Composites a LayerStack on the GPU using tgfx2 native textures.

    Layers upload as ``Tgfx2TextureHandle`` RGBA8 textures. The first
    pass composites them with premultiplied alpha into ``_main_tex``;
    a second pass un-premultiplies into ``_display_tex`` whose handle
    is handed to the Canvas for display.
    """

    def __init__(self, layer_stack: LayerStack):
        self._stack = layer_stack

        # Per-layer GPU textures, keyed by ``id(layer)`` — Tgfx2TextureHandle.
        self._layer_textures: dict[int, Tgfx2TextureHandle] = {}
        self._layer_tex_size: dict[int, tuple[int, int]] = {}
        self._dirty_layers: set[int] = set()

        # Offscreen color attachments (created lazily on first composite).
        self._main_tex: Tgfx2TextureHandle | None = None
        self._display_tex: Tgfx2TextureHandle | None = None
        self._fbo_w = 0
        self._fbo_h = 0

        # Temp color attachments pool for group-opacity subtrees.
        self._temp_texs: list[Tgfx2TextureHandle] = []
        self._temp_texs_in_use: int = 0

        # tgfx2 context + compiled shaders (lazy).
        self._holder: Tgfx2Context | None = None
        self._ctx = None
        self._composite_tc: TcShader | None = None
        self._unpremul_tc: TcShader | None = None
        self._composite_vs = None
        self._composite_fs = None
        self._unpremul_vs = None
        self._unpremul_fs = None

        self._quad_verts = _full_screen_quad_verts()

        self._dirty = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def composite(self):
        """Composite all visible layers into the display texture."""
        w, h = self._stack.width, self._stack.height
        if w == 0 or h == 0:
            return

        self._ensure_context()
        self._ensure_attachments(w, h)
        self._sync_dirty_textures()

        ctx = self._ctx
        ctx.begin_frame()

        # --- Main pass: accumulate layers with premultiplied-alpha blending ---
        ctx.begin_pass(
            color=self._main_tex,
            depth=Tgfx2TextureHandle(),  # no depth
            clear_color_enabled=True,
            r=0.0, g=0.0, b=0.0, a=0.0,
            clear_depth=1.0,
            clear_depth_enabled=False,
        )
        ctx.set_viewport(0, 0, w, h)
        ctx.set_depth_test(False)
        ctx.set_blend(True)
        ctx.set_blend_func(Tgfx2BlendFactor.One,
                           Tgfx2BlendFactor.OneMinusSrcAlpha)
        ctx.bind_shader(self._composite_vs, self._composite_fs)

        # Bottom-to-top: reversed list order (last in list = bottom).
        # Need to close the current pass to re-target for nested
        # group-opacity subtrees, so we track the active target stack.
        for layer in reversed(self._stack.layers):
            self._render_layer_tree(layer, self._main_tex)

        ctx.end_pass()

        # --- Un-premultiply pass: main_tex → display_tex ---
        ctx.begin_pass(
            color=self._display_tex,
            depth=Tgfx2TextureHandle(),
            clear_color_enabled=True,
            r=0.0, g=0.0, b=0.0, a=0.0,
            clear_depth=1.0,
            clear_depth_enabled=False,
        )
        ctx.set_viewport(0, 0, w, h)
        ctx.set_blend(False)
        ctx.bind_shader(self._unpremul_vs, self._unpremul_fs)
        ctx.bind_sampled_texture(0, self._main_tex)
        ctx.set_uniform_int("u_texture", 0)
        ctx.draw_immediate_triangles(self._quad_verts, 6)
        ctx.end_pass()

        ctx.end_frame()
        self._dirty = False

    def get_display_gl_id(self) -> int:
        """Return the raw GL texture id of the final composited image.

        The compositor owns its own ``Tgfx2Context`` (separate device
        from the UIRenderer's), so handing out our ``Tgfx2TextureHandle``
        directly would land in the wrong device's pool on the consumer
        side. Instead we expose the underlying GL texture id; the
        consumer wraps it with ``wrap_gl_texture_as_tgfx2`` in its own
        holder for the draw.
        """
        if self._display_tex is None or self._holder is None:
            return 0
        return int(self._holder.get_gl_id(self._display_tex))

    def display_size(self) -> tuple[int, int]:
        """(width, height) of the current display texture, or (0, 0)."""
        return (self._fbo_w, self._fbo_h)

    def mark_dirty(self, layer: Layer | None = None):
        """Mark a layer (or the whole stack) for re-upload + re-composite."""
        self._dirty = True
        if layer is not None:
            self._dirty_layers.add(id(layer))
        else:
            for l in self._stack._all_layers_flat():
                self._dirty_layers.add(id(l))

    def rebuild(self):
        """Full rebuild after structural change (add/remove/reorder)."""
        self._cleanup_stale_textures()
        self._dirty = True
        self._dirty_layers = {id(l) for l in self._stack._all_layers_flat()}

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    def readback(self) -> np.ndarray:
        """GPU -> CPU: read the display texture into a numpy uint8 RGBA array."""
        if self._display_tex is None or self._holder is None:
            w, h = self._stack.width, self._stack.height
            if w == 0 or h == 0:
                return np.zeros((1, 1, 4), dtype=np.uint8)
            return np.zeros((h, w, 4), dtype=np.uint8)

        from termin._native.render import RenderingManager
        render_engine = RenderingManager.instance().render_engine
        if render_engine is None:
            log.error("GPUCompositor.readback: no render engine")
            h, w = self._fbo_h, self._fbo_w
            return np.zeros((h, w, 4), dtype=np.uint8)
        render_engine.ensure_tgfx2()
        device = render_engine.tgfx2_device
        if device is None:
            log.error("GPUCompositor.readback: tgfx2 device unavailable")
            h, w = self._fbo_h, self._fbo_w
            return np.zeros((h, w, 4), dtype=np.uint8)

        buf = np.empty((self._fbo_h * self._fbo_w * 4,), dtype=np.float32)
        ok = device.read_texture_rgba_float(self._display_tex, buf)
        if not ok:
            log.error("GPUCompositor.readback: read_texture_rgba_float failed")
            h, w = self._fbo_h, self._fbo_w
            return np.zeros((h, w, 4), dtype=np.uint8)

        float_data = buf.reshape((self._fbo_h, self._fbo_w, 4))
        result = np.clip(float_data * 255.0, 0, 255).astype(np.uint8)
        # OpenGL reads bottom-up; flip to top-down.
        result = np.ascontiguousarray(result[::-1])
        return result

    def dispose(self):
        """Release all GPU resources."""
        if self._holder is None:
            # Nothing was ever created.
            self._layer_textures.clear()
            self._layer_tex_size.clear()
            self._dirty_layers.clear()
            self._temp_texs.clear()
            return

        for tex in self._layer_textures.values():
            self._holder.destroy_texture(tex)
        self._layer_textures.clear()
        self._layer_tex_size.clear()
        self._dirty_layers.clear()

        for tex in self._temp_texs:
            self._holder.destroy_texture(tex)
        self._temp_texs.clear()
        self._temp_texs_in_use = 0

        if self._main_tex is not None:
            self._holder.destroy_texture(self._main_tex)
            self._main_tex = None
        if self._display_tex is not None:
            self._holder.destroy_texture(self._display_tex)
            self._display_tex = None

    # ------------------------------------------------------------------
    # Lazy initialisation
    # ------------------------------------------------------------------

    def _ensure_context(self):
        if self._holder is None:
            self._holder = Tgfx2Context()
            self._ctx = self._holder.context
        if self._composite_vs is None:
            self._composite_tc = TcShader.from_sources(
                _VERT_SRC, _COMPOSITE_FRAG_SRC, "", "gpu_compositor_composite")
            pair = tc_shader_ensure_tgfx2(self._ctx, self._composite_tc)
            if not pair.vs or not pair.fs:
                raise RuntimeError(
                    "GPUCompositor: composite shader compile failed")
            self._composite_vs = pair.vs
            self._composite_fs = pair.fs

            self._unpremul_tc = TcShader.from_sources(
                _VERT_SRC, _UNPREMUL_FRAG_SRC, "", "gpu_compositor_unpremul")
            pair = tc_shader_ensure_tgfx2(self._ctx, self._unpremul_tc)
            if not pair.vs or not pair.fs:
                raise RuntimeError(
                    "GPUCompositor: unpremul shader compile failed")
            self._unpremul_vs = pair.vs
            self._unpremul_fs = pair.fs

    def _ensure_attachments(self, w: int, h: int):
        if (self._main_tex is not None
                and self._fbo_w == w and self._fbo_h == h):
            return

        # Destroy old and recreate — the sizes change rarely (canvas resize).
        if self._main_tex is not None:
            self._holder.destroy_texture(self._main_tex)
        if self._display_tex is not None:
            self._holder.destroy_texture(self._display_tex)
        for tex in self._temp_texs:
            self._holder.destroy_texture(tex)
        self._temp_texs.clear()
        self._temp_texs_in_use = 0

        self._main_tex = self._holder.create_color_attachment(w, h)
        self._display_tex = self._holder.create_color_attachment(w, h)
        self._fbo_w = w
        self._fbo_h = h

    # ------------------------------------------------------------------
    # Texture sync
    # ------------------------------------------------------------------

    def _sync_dirty_textures(self):
        w, h = self._stack.width, self._stack.height
        for layer in self._stack._all_layers_flat():
            lid = id(layer)
            img = np.ascontiguousarray(layer.image).reshape(-1)
            if lid not in self._layer_textures:
                tex = self._holder.create_texture_rgba8(w, h, img)
                self._layer_textures[lid] = tex
                self._layer_tex_size[lid] = (w, h)
                self._dirty_layers.discard(lid)
            elif lid in self._dirty_layers:
                prev_w, prev_h = self._layer_tex_size.get(lid, (0, 0))
                if prev_w == w and prev_h == h:
                    self._holder.upload_texture(self._layer_textures[lid], img)
                else:
                    # Size changed — reallocate.
                    self._holder.destroy_texture(self._layer_textures[lid])
                    tex = self._holder.create_texture_rgba8(w, h, img)
                    self._layer_textures[lid] = tex
                    self._layer_tex_size[lid] = (w, h)
                self._dirty_layers.discard(lid)

    def _cleanup_stale_textures(self):
        live_ids = {id(l) for l in self._stack._all_layers_flat()}
        stale = [lid for lid in self._layer_textures if lid not in live_ids]
        if not stale:
            return
        for lid in stale:
            if self._holder is not None:
                self._holder.destroy_texture(self._layer_textures[lid])
            del self._layer_textures[lid]
            self._layer_tex_size.pop(lid, None)
            self._dirty_layers.discard(lid)

    # ------------------------------------------------------------------
    # Compositing helpers
    # ------------------------------------------------------------------

    def _render_layer_tree(self, layer: Layer, target_tex: Tgfx2TextureHandle):
        """Recursively composite a layer (and its children) into *target_tex*."""
        if not layer.visible or layer.opacity <= 0:
            return

        has_children = bool(layer.children)
        needs_group = has_children and layer.opacity < 1.0

        if needs_group:
            # Open a nested pass on a temp attachment.
            temp = self._acquire_temp_tex()
            ctx = self._ctx
            # End the current (parent) pass, render the group into temp,
            # then reopen the parent pass on target_tex to blend temp in.
            ctx.end_pass()
            ctx.begin_pass(
                color=temp,
                depth=Tgfx2TextureHandle(),
                clear_color_enabled=True,
                r=0.0, g=0.0, b=0.0, a=0.0,
                clear_depth=1.0,
                clear_depth_enabled=False,
            )
            ctx.set_viewport(0, 0, self._fbo_w, self._fbo_h)
            ctx.set_depth_test(False)
            ctx.set_blend(True)
            ctx.set_blend_func(Tgfx2BlendFactor.One,
                               Tgfx2BlendFactor.OneMinusSrcAlpha)
            ctx.bind_shader(self._composite_vs, self._composite_fs)

            for child in reversed(layer.children):
                self._render_layer_tree(child, temp)
            self._draw_layer_quad(layer, opacity=1.0)

            ctx.end_pass()
            # Reopen parent pass; begin_pass with clear_color_enabled=False
            # preserves existing contents of target_tex.
            ctx.begin_pass(
                color=target_tex,
                depth=Tgfx2TextureHandle(),
                clear_color_enabled=False,
                r=0.0, g=0.0, b=0.0, a=0.0,
                clear_depth=1.0,
                clear_depth_enabled=False,
            )
            ctx.set_viewport(0, 0, self._fbo_w, self._fbo_h)
            ctx.set_depth_test(False)
            ctx.set_blend(True)
            ctx.set_blend_func(Tgfx2BlendFactor.One,
                               Tgfx2BlendFactor.OneMinusSrcAlpha)
            ctx.bind_shader(self._composite_vs, self._composite_fs)

            self._draw_texture_quad(temp, layer.opacity)
            self._release_temp_tex(temp)
        else:
            if has_children:
                for child in reversed(layer.children):
                    self._render_layer_tree(child, target_tex)
            self._draw_layer_quad(layer, layer.opacity)

    def _draw_layer_quad(self, layer: Layer, opacity: float):
        lid = id(layer)
        tex = self._layer_textures.get(lid)
        if tex is None:
            return
        self._draw_texture_quad(tex, opacity)

    def _draw_texture_quad(self, texture: Tgfx2TextureHandle, opacity: float):
        ctx = self._ctx
        ctx.bind_sampled_texture(0, texture)
        ctx.set_uniform_int("u_texture", 0)
        ctx.set_uniform_float("u_opacity", float(opacity))
        ctx.draw_immediate_triangles(self._quad_verts, 6)

    # ------------------------------------------------------------------
    # Temp texture pool
    # ------------------------------------------------------------------

    def _acquire_temp_tex(self) -> Tgfx2TextureHandle:
        if self._temp_texs_in_use < len(self._temp_texs):
            tex = self._temp_texs[self._temp_texs_in_use]
        else:
            tex = self._holder.create_color_attachment(self._fbo_w, self._fbo_h)
            self._temp_texs.append(tex)
        self._temp_texs_in_use += 1
        return tex

    def _release_temp_tex(self, tex: Tgfx2TextureHandle):
        self._temp_texs_in_use = max(0, self._temp_texs_in_use - 1)
