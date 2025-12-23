"""OpenGL context management and window framebuffer handles.

The main OpenGLGraphicsBackend is now in C++ (_native module).
This file contains:
- Context management for multi-context GPU resource cleanup
- Python framebuffer handles for window integration (GLFW, Qt, SDL)
"""

from __future__ import annotations

from typing import Callable, Dict, Tuple

from OpenGL import GL as gl

from termin.visualization.platform.backends.base import (
    FramebufferHandle,
    GPUTextureHandle,
)

# --- Context Management ---
# Used for switching contexts when deleting GPU resources in multi-context scenarios

_context_registry: Dict[int, Callable[[], None]] = {}
_current_context_key: int | None = None


def register_context(context_key: int, make_current: Callable[[], None]) -> None:
    """Register a context for resource cleanup."""
    global _current_context_key
    _context_registry[context_key] = make_current
    _current_context_key = context_key


def get_context_make_current(context_key: int) -> Callable[[], None] | None:
    """Get make_current function for a context."""
    original = _context_registry.get(context_key)
    if original is None:
        return None

    def wrapped():
        global _current_context_key
        original()
        _current_context_key = context_key

    return wrapped


def get_current_context_key() -> int | None:
    """Get currently active context key."""
    return _current_context_key


# --- Framebuffer Handles for Window Integration ---
# These are still needed because window backends (GLFW, Qt, SDL) create
# external FBOs that need Python wrappers with specific lifecycle management.


class _OpenGLColorTextureHandle(GPUTextureHandle):
    """Lightweight wrapper over an existing GL texture.
    Lifecycle managed by framebuffer, delete() is a no-op.
    """
    def __init__(self, tex_id: int):
        self._tex_id = tex_id

    def bind(self, unit: int = 0):
        gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self._tex_id or 0)

    def delete(self):
        pass

    def _set_tex_id(self, tex_id: int):
        self._tex_id = tex_id


class OpenGLFramebufferHandle(FramebufferHandle):
    """OpenGL framebuffer with color and depth attachments.

    Used for window FBO wrapping - when fbo_id is provided, the handle
    wraps an external FBO without owning it.
    """
    def __init__(
        self,
        size: Tuple[int, int],
        fbo_id: int | None = None,
        owns_attachments: bool = True,
        samples: int = 1,
    ):
        self._size = size
        self._owns_attachments = owns_attachments
        self._samples = samples
        self._fbo: int | None = None
        self._color_tex: int | None = None
        self._depth_rb: int | None = None
        self._color_handle = _OpenGLColorTextureHandle(0)
        if fbo_id is None:
            self._create()
        else:
            self._fbo = fbo_id

    @property
    def samples(self) -> int:
        return self._samples

    @property
    def is_msaa(self) -> bool:
        return self._samples > 1

    def set_external_target(self, fbo_id: int, size: Tuple[int, int]):
        """Rebind to an external FBO."""
        self._owns_attachments = False
        self._fbo = fbo_id
        self._size = size

    def get_size(self) -> Tuple[int, int]:
        return self._size

    def _create(self):
        w, h = self._size

        self._fbo = gl.glGenFramebuffers(1)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self._fbo)

        if self._samples > 1:
            # MSAA
            self._color_tex = gl.glGenTextures(1)
            gl.glBindTexture(gl.GL_TEXTURE_2D_MULTISAMPLE, self._color_tex)
            gl.glTexImage2DMultisample(
                gl.GL_TEXTURE_2D_MULTISAMPLE, self._samples,
                gl.GL_RGBA8, w, h, gl.GL_TRUE
            )
            gl.glFramebufferTexture2D(
                gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0,
                gl.GL_TEXTURE_2D_MULTISAMPLE, self._color_tex, 0
            )

            self._depth_rb = gl.glGenRenderbuffers(1)
            gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, self._depth_rb)
            gl.glRenderbufferStorageMultisample(
                gl.GL_RENDERBUFFER, self._samples,
                gl.GL_DEPTH_COMPONENT24, w, h
            )
            gl.glFramebufferRenderbuffer(
                gl.GL_FRAMEBUFFER, gl.GL_DEPTH_ATTACHMENT,
                gl.GL_RENDERBUFFER, self._depth_rb
            )
        else:
            # Standard FBO
            self._color_tex = gl.glGenTextures(1)
            gl.glBindTexture(gl.GL_TEXTURE_2D, self._color_tex)
            gl.glTexImage2D(
                gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8,
                w, h, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, None
            )
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)

            gl.glFramebufferTexture2D(
                gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0,
                gl.GL_TEXTURE_2D, self._color_tex, 0
            )

            self._depth_rb = gl.glGenRenderbuffers(1)
            gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, self._depth_rb)
            gl.glRenderbufferStorage(gl.GL_RENDERBUFFER, gl.GL_DEPTH_COMPONENT24, w, h)
            gl.glFramebufferRenderbuffer(
                gl.GL_FRAMEBUFFER, gl.GL_DEPTH_ATTACHMENT,
                gl.GL_RENDERBUFFER, self._depth_rb
            )

        status = gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER)
        if status != gl.GL_FRAMEBUFFER_COMPLETE:
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
            raise RuntimeError(f"Framebuffer incomplete: 0x{status:X}")

        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
        self._color_handle._set_tex_id(self._color_tex)

    def resize(self, size: Tuple[int, int]):
        if size == self._size and self._fbo is not None:
            return
        if not self._owns_attachments:
            self._size = size
            return
        self.delete()
        self._size = size
        self._create()

    def color_texture(self) -> GPUTextureHandle:
        return self._color_handle

    def delete(self):
        if not self._owns_attachments:
            self._fbo = None
            return
        if self._fbo is not None:
            gl.glDeleteFramebuffers(1, [self._fbo])
            self._fbo = None
        if self._color_tex is not None:
            gl.glDeleteTextures(1, [self._color_tex])
            self._color_tex = None
        if self._depth_rb is not None:
            gl.glDeleteRenderbuffers(1, [self._depth_rb])
            self._depth_rb = None


class _OpenGLDepthTextureHandle(GPUTextureHandle):
    """Wrapper for depth texture (shadow mapping)."""
    def __init__(self, tex_id: int):
        self._tex_id = tex_id

    def bind(self, unit: int = 0):
        gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self._tex_id or 0)

    def delete(self):
        pass

    def _set_tex_id(self, tex_id: int):
        self._tex_id = tex_id


class OpenGLShadowFramebufferHandle(FramebufferHandle):
    """Framebuffer for shadow mapping with depth texture."""

    def __init__(self, size: Tuple[int, int]):
        self._size = size
        self._fbo: int | None = None
        self._depth_tex: int | None = None
        self._depth_handle = _OpenGLDepthTextureHandle(0)
        self._create()

    def get_size(self) -> Tuple[int, int]:
        return self._size

    def _create(self):
        w, h = self._size

        self._fbo = gl.glGenFramebuffers(1)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self._fbo)

        self._depth_tex = gl.glGenTextures(1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self._depth_tex)
        gl.glTexImage2D(
            gl.GL_TEXTURE_2D, 0, gl.GL_DEPTH_COMPONENT24,
            w, h, 0, gl.GL_DEPTH_COMPONENT, gl.GL_FLOAT, None
        )

        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_BORDER)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_BORDER)

        border_color = (1.0, 1.0, 1.0, 1.0)
        gl.glTexParameterfv(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_BORDER_COLOR, border_color)

        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_COMPARE_MODE, gl.GL_COMPARE_REF_TO_TEXTURE)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_COMPARE_FUNC, gl.GL_LEQUAL)

        gl.glFramebufferTexture2D(
            gl.GL_FRAMEBUFFER, gl.GL_DEPTH_ATTACHMENT,
            gl.GL_TEXTURE_2D, self._depth_tex, 0
        )

        gl.glDrawBuffer(gl.GL_NONE)
        gl.glReadBuffer(gl.GL_NONE)

        status = gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER)
        if status != gl.GL_FRAMEBUFFER_COMPLETE:
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
            raise RuntimeError(f"Shadow framebuffer incomplete: 0x{status:X}")

        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
        self._depth_handle._set_tex_id(self._depth_tex)

    def resize(self, size: Tuple[int, int]):
        if size == self._size and self._fbo is not None:
            return
        self.delete()
        self._size = size
        self._create()

    def color_texture(self) -> GPUTextureHandle:
        return self._depth_handle

    def depth_texture(self) -> GPUTextureHandle:
        return self._depth_handle

    def delete(self):
        if self._fbo is not None:
            gl.glDeleteFramebuffers(1, [self._fbo])
            self._fbo = None
        if self._depth_tex is not None:
            gl.glDeleteTextures(1, [self._depth_tex])
            self._depth_tex = None
