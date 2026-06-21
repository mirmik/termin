"""
OffscreenContext - dedicated GL context for legacy offscreen editor rendering.

All GPU resources created through this path live in this context. Displays can
share context with it, which allows rendering in one context and blitting the
result to any display.
"""

from __future__ import annotations


class OffscreenContext:
    """Dedicated offscreen GL context for rendering."""

    CONTEXT_KEY: int = 0

    def __init__(self):
        """Create hidden SDL window with an OpenGL context."""
        import sdl2
        from sdl2 import video

        self._window = None
        self._gl_context = None

        # SDL must be initialized by caller (e.g., in run_editor.py).
        video.SDL_GL_SetAttribute(video.SDL_GL_CONTEXT_MAJOR_VERSION, 3)
        video.SDL_GL_SetAttribute(video.SDL_GL_CONTEXT_MINOR_VERSION, 3)
        video.SDL_GL_SetAttribute(
            video.SDL_GL_CONTEXT_PROFILE_MASK,
            video.SDL_GL_CONTEXT_PROFILE_CORE,
        )
        video.SDL_GL_SetAttribute(video.SDL_GL_DOUBLEBUFFER, 1)
        video.SDL_GL_SetAttribute(video.SDL_GL_DEPTH_SIZE, 24)

        # Use 8-bit color: no banding in normal paths, no Windows HDR issues.
        video.SDL_GL_SetAttribute(video.SDL_GL_RED_SIZE, 8)
        video.SDL_GL_SetAttribute(video.SDL_GL_GREEN_SIZE, 8)
        video.SDL_GL_SetAttribute(video.SDL_GL_BLUE_SIZE, 8)

        flags = video.SDL_WINDOW_OPENGL | video.SDL_WINDOW_HIDDEN

        self._window = video.SDL_CreateWindow(
            b"OffscreenContext",
            0,
            0,
            1,
            1,
            flags,
        )

        if not self._window:
            raise RuntimeError(f"Failed to create SDL window: {sdl2.SDL_GetError()}")

        self._gl_context = video.SDL_GL_CreateContext(self._window)
        if not self._gl_context:
            video.SDL_DestroyWindow(self._window)
            self._window = None
            raise RuntimeError(f"Failed to create GL context: {sdl2.SDL_GetError()}")

        # Make the GL context current. tgfx2 devices created later load GL
        # function pointers through their own constructors.
        self.make_current()

    @property
    def gl_context(self):
        """GL context for sharing with display/window surfaces."""
        return self._gl_context

    @property
    def context_key(self) -> int:
        """Context key for GPU resources."""
        return self.CONTEXT_KEY

    def make_current(self) -> None:
        """Activate the GL context."""
        from sdl2 import video

        if self._window is not None and self._gl_context is not None:
            result = video.SDL_GL_MakeCurrent(self._window, self._gl_context)
            if result != 0:
                import sdl2
                from tcbase import log

                log.error(f"[OffscreenContext] SDL_GL_MakeCurrent failed: {sdl2.SDL_GetError()}")

    def is_valid(self) -> bool:
        """Return whether the context still owns native resources."""
        return self._window is not None and self._gl_context is not None

    def destroy(self) -> None:
        """Release native context resources."""
        from sdl2 import video

        if self._gl_context is not None:
            video.SDL_GL_DeleteContext(self._gl_context)
            self._gl_context = None

        if self._window is not None:
            video.SDL_DestroyWindow(self._window)
            self._window = None

    def __enter__(self) -> "OffscreenContext":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.destroy()
