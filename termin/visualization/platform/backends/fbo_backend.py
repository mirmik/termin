"""FBO-based render surface backend for termin-gui integration.

Creates a tc_render_surface backed by an OpenGL Framebuffer Object (FBO).
The 3D engine renders into the FBO; the tcgui Viewport3D widget blits
it to the screen. No separate SDL window is created.

Usage::

    surface = FBOSurface(width=800, height=600)
    display = Display(surface=surface, name="Editor")
    # In tcgui Viewport3D.layout() on resize:
    surface.resize(new_w, new_h)
"""

from __future__ import annotations

from typing import Callable


class FBOSurface:
    """OpenGL FBO-backed render surface.

    Implements the Python vtable interface expected by
    ``_render_surface_new_from_python``:

    - ``get_framebuffer_id()`` → OpenGL FBO id
    - ``framebuffer_size()``   → (w, h) in pixels
    - ``make_current()``       → no-op (tcgui owns the context)
    - ``swap_buffers()``       → no-op (tcgui handles buffer swap)
    - ``window_size()``        → same as framebuffer_size
    - ``should_close()``       → always False
    - ``set_should_close(v)``  → ignored
    - ``get_cursor_pos()``     → (0.0, 0.0); widget provides coords
    - ``share_group_key()``    → 0 (falls back to context_key)
    """

    def __init__(self, width: int, height: int) -> None:
        self._width: int = width
        self._height: int = height
        self._fbo: int = 0
        self._color_tex: int = 0
        self._depth_rb: int = 0
        self._tc_surface_ptr: int = 0

        # Called after FBO is recreated on resize: on_resize(w, h)
        self.on_resize: Callable[[int, int], None] | None = None

        self._create_fbo(width, height)

        from termin._native.render import _render_surface_new_from_python
        self._tc_surface_ptr = _render_surface_new_from_python(self)

    # ------------------------------------------------------------------
    # FBO management
    # ------------------------------------------------------------------

    def _create_fbo(self, width: int, height: int) -> None:
        from OpenGL.GL import (
            glGenFramebuffers, glBindFramebuffer, GL_FRAMEBUFFER,
            glGenTextures, glBindTexture, GL_TEXTURE_2D,
            glTexImage2D, GL_RGBA8, GL_RGBA, GL_UNSIGNED_BYTE,
            glTexParameteri, GL_TEXTURE_MIN_FILTER, GL_TEXTURE_MAG_FILTER,
            GL_LINEAR, glFramebufferTexture2D, GL_COLOR_ATTACHMENT0,
            glGenRenderbuffers, glBindRenderbuffer, GL_RENDERBUFFER,
            glRenderbufferStorage, GL_DEPTH_COMPONENT24,
            glFramebufferRenderbuffer, GL_DEPTH_ATTACHMENT,
            glCheckFramebufferStatus, GL_FRAMEBUFFER_COMPLETE,
        )
        from tcbase import log

        w = max(1, width)
        h = max(1, height)

        self._fbo = int(glGenFramebuffers(1))
        glBindFramebuffer(GL_FRAMEBUFFER, self._fbo)

        self._color_tex = int(glGenTextures(1))
        glBindTexture(GL_TEXTURE_2D, self._color_tex)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, None)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, self._color_tex, 0)

        self._depth_rb = int(glGenRenderbuffers(1))
        glBindRenderbuffer(GL_RENDERBUFFER, self._depth_rb)
        glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH_COMPONENT24, w, h)
        glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, self._depth_rb)

        status = glCheckFramebufferStatus(GL_FRAMEBUFFER)
        if status != GL_FRAMEBUFFER_COMPLETE:
            log.error(f"[FBOSurface] Framebuffer incomplete: status=0x{status:04X}")

        glBindFramebuffer(GL_FRAMEBUFFER, 0)

    def _delete_fbo(self) -> None:
        from OpenGL.GL import (
            glDeleteFramebuffers, glDeleteTextures, glDeleteRenderbuffers,
        )
        if self._fbo:
            glDeleteFramebuffers(1, [self._fbo])
        if self._color_tex:
            glDeleteTextures(1, [self._color_tex])
        if self._depth_rb:
            glDeleteRenderbuffers(1, [self._depth_rb])
        self._fbo = 0
        self._color_tex = 0
        self._depth_rb = 0

    def resize(self, width: int, height: int) -> None:
        """Recreate FBO at new dimensions and notify Display."""
        if width == self._width and height == self._height:
            return
        self._delete_fbo()
        self._width = max(1, width)
        self._height = max(1, height)
        self._create_fbo(self._width, self._height)
        if self.on_resize is not None:
            self.on_resize(self._width, self._height)

    # ------------------------------------------------------------------
    # Properties for Viewport3D
    # ------------------------------------------------------------------

    @property
    def color_texture_id(self) -> int:
        """Raw OpenGL texture ID of the color attachment."""
        return self._color_tex

    @property
    def tc_surface_ptr(self) -> int:
        return self._tc_surface_ptr

    def tc_surface(self):
        """Return object with .ptr for Display compatibility."""
        return _TcSurfaceWrapper(self._tc_surface_ptr)

    # ------------------------------------------------------------------
    # Python vtable interface (called by C++ via _render_surface_new_from_python)
    # ------------------------------------------------------------------

    def get_framebuffer_id(self) -> int:
        return self._fbo

    def framebuffer_size(self) -> tuple[int, int]:
        return (self._width, self._height)

    def make_current(self) -> None:
        pass  # Context owned by tcgui's SDL window

    def swap_buffers(self) -> None:
        pass  # tcgui handles the buffer swap

    def window_size(self) -> tuple[int, int]:
        return (self._width, self._height)

    def should_close(self) -> bool:
        return False

    def set_should_close(self, value: bool) -> None:
        pass

    def get_cursor_pos(self) -> tuple[float, float]:
        return (0.0, 0.0)  # Viewport3D widget provides cursor coordinates

    def share_group_key(self) -> int:
        return 0  # Falls back to context_key; single shared GL context

    # ------------------------------------------------------------------

    def __del__(self) -> None:
        self._delete_fbo()


class _TcSurfaceWrapper:
    """Minimal wrapper with .ptr for Display.__init__ compatibility."""

    def __init__(self, ptr: int) -> None:
        self.ptr = ptr
