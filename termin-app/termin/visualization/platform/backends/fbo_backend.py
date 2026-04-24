"""Offscreen render surface backed by a tgfx2 TextureHandle.

The 3D engine composites all its viewports into this texture via
``PullRenderingManager::render_display`` (which routes through
``IRenderDevice::clear_texture`` + ``blit_to_texture`` — both
backends). Viewport3D (tcgui) then composites *this* texture into the
UI pass. No raw GL FBO anywhere: that is exactly what makes the
editor run on Vulkan too.

Name ``FBOSurface`` is kept only because existing callers import it
under that name; the old GL-FBO semantics are gone.

Usage::

    surface = FBOSurface(800, 600, ctx=tgfx2_ctx)
    display = Display(surface=surface, name="Editor")
    # On window resize:
    surface.resize(new_w, new_h)
"""

from __future__ import annotations

from typing import Callable

from tgfx._tgfx_native import Tgfx2Context, Tgfx2PixelFormat


class FBOSurface:
    """Offscreen composite surface on a tgfx2 color texture.

    Implements the Python vtable interface expected by
    ``_render_surface_new_from_python``. The key addition over the
    legacy FBO implementation is ``get_tgfx_color_tex_id()`` — that is
    what ``PullRenderingManager`` reads to pick the backend-neutral
    code path. ``get_framebuffer_id()`` still exists and returns 0
    for compatibility, but nothing should actually consume it now.
    """

    def __init__(self, width: int, height: int, ctx: Tgfx2Context) -> None:
        """
        Parameters
        ----------
        width, height : int
            Initial framebuffer size.
        ctx : Tgfx2Context
            Process-global tgfx2 context. Typically the borrowed one
            produced by ``Tgfx2Context.borrow(win.device_ptr(),
            win.context_ptr())`` where ``win`` is a ``BackendWindow``.
            The ctx owns the underlying device — this surface only
            holds non-owning texture handles whose lifetime is tied to
            ``close()`` / ``__del__``.
        """
        self._width: int = max(1, width)
        self._height: int = max(1, height)
        self._ctx: Tgfx2Context = ctx
        self._color_tex = None
        self._depth_tex = None
        self._tc_surface_ptr: int = 0

        # Called after the surface is resized: on_resize(w, h). Used by
        # viewport state holders (ViewportRenderState) to re-allocate
        # their own intermediate textures in lockstep.
        self.on_resize: Callable[[int, int], None] | None = None

        self._allocate()

        from termin._native.render import _render_surface_new_from_python
        self._tc_surface_ptr = _render_surface_new_from_python(self)

    # ------------------------------------------------------------------
    # Allocation / resize
    # ------------------------------------------------------------------

    def _allocate(self) -> None:
        # Color is RGBA8 with Sampled|ColorAttachment|CopySrc|CopyDst
        # (see Tgfx2Context.create_color_attachment comment). Depth is
        # D24 DepthStencilAttachment|Sampled — enough for 3D scenes,
        # and Sampled lets future post-effects read it back.
        self._color_tex = self._ctx.create_color_attachment(
            self._width, self._height, Tgfx2PixelFormat.RGBA8_UNorm
        )
        self._depth_tex = self._ctx.create_depth_attachment(
            self._width, self._height, Tgfx2PixelFormat.D24_UNorm
        )

    def _release(self) -> None:
        if self._color_tex is not None:
            self._ctx.destroy_texture(self._color_tex)
            self._color_tex = None
        if self._depth_tex is not None:
            self._ctx.destroy_texture(self._depth_tex)
            self._depth_tex = None

    def resize(self, width: int, height: int) -> None:
        w = max(1, width)
        h = max(1, height)
        if w == self._width and h == self._height:
            return

        self._release()
        self._width = w
        self._height = h
        self._allocate()

        if self._tc_surface_ptr:
            from termin._native.render import _render_surface_notify_resize
            _render_surface_notify_resize(self._tc_surface_ptr, self._width, self._height)
        if self.on_resize is not None:
            self.on_resize(self._width, self._height)

    # ------------------------------------------------------------------
    # Composite target — consumed by PullRenderingManager and Viewport3D
    # ------------------------------------------------------------------

    @property
    def color_tex(self):
        """The tgfx2 TextureHandle Viewport3D composites from.

        Valid as long as the surface is alive. Re-allocated on every
        ``resize()`` — callers that cache the handle must re-fetch on
        ``on_resize``.
        """
        return self._color_tex

    @property
    def depth_tex(self):
        return self._depth_tex

    @property
    def tc_surface_ptr(self) -> int:
        return self._tc_surface_ptr

    def tc_surface(self):
        return _TcSurfaceWrapper(self._tc_surface_ptr)

    def set_input_manager(self, input_manager_ptr: int) -> None:
        """Attach a tc_viewport_input_manager (as raw uintptr) to the
        underlying tc_render_surface. Passing 0 clears the binding.

        Mirrors SDLEmbeddedSurface::set_input_manager — required by the
        editor so DisplayInputRouter events reach the surface's dispatch
        path instead of being swallowed by the default scene-pipeline
        input manager.
        """
        if self._tc_surface_ptr == 0:
            return
        from termin._native.render import _render_surface_set_input_manager
        _render_surface_set_input_manager(self._tc_surface_ptr, input_manager_ptr)

    # ------------------------------------------------------------------
    # Python vtable interface (called by C++ tc_render_surface)
    # ------------------------------------------------------------------

    def get_tgfx_color_tex_id(self) -> int:
        """Return the tgfx2 TextureHandle id. Drives the new
        backend-neutral compositing path in PullRenderingManager.
        """
        if self._color_tex is None:
            return 0
        return int(self._color_tex.id)

    def get_framebuffer_id(self) -> int:
        # Legacy vtable slot — zero means "no raw FBO". Callers that
        # still key off this (Qt debugger overlay, etc.) will fall
        # through to their own fallback paths or skip; nothing in the
        # editor render loop depends on it now.
        return 0

    def framebuffer_size(self) -> tuple[int, int]:
        return (self._width, self._height)

    def make_current(self) -> None:
        pass

    def swap_buffers(self) -> None:
        pass

    def window_size(self) -> tuple[int, int]:
        return (self._width, self._height)

    def should_close(self) -> bool:
        return False

    def set_should_close(self, value: bool) -> None:
        pass

    def get_cursor_pos(self) -> tuple[float, float]:
        return (0.0, 0.0)

    def share_group_key(self) -> int:
        # Single-device invariant: every Python surface in the process
        # lives on the same IRenderDevice. A single share group key is
        # correct and makes the legacy tc_gpu_share_group cache collapse
        # to a single group — avoids duplicated per-context resource
        # tables.
        return 1

    # ------------------------------------------------------------------

    def close(self) -> None:
        """Release the tgfx2 textures + C++ render surface wrapper.

        Call explicitly before the host ``Tgfx2Context`` goes away
        (otherwise ``destroy_texture`` on a dead device may crash).
        The ``__del__`` hook is a best-effort fallback.
        """
        self._release()
        if self._tc_surface_ptr:
            from termin._native.render import _render_surface_free_external
            _render_surface_free_external(self._tc_surface_ptr)
            self._tc_surface_ptr = 0

    def __del__(self) -> None:
        # Best effort — if the Tgfx2Context was already torn down the
        # destroy will throw; we swallow silently at teardown.
        try:
            self.close()
        except Exception:
            pass


class _TcSurfaceWrapper:
    """Minimal wrapper with .ptr for Display.__init__ compatibility."""

    def __init__(self, ptr: int) -> None:
        self.ptr = ptr
