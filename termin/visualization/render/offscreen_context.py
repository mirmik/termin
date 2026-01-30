"""
OffscreenContext — dedicated GL context для offscreen рендеринга.

Все GPU ресурсы живут в этом контексте. Дисплеи share context с ним,
что позволяет рендерить в одном контексте и блитать результат на любой дисплей.

Преимущества:
- Симметричность: все дисплеи равноправны
- Независимость: рендеринг работает даже без дисплеев
- Один context_key для всех ресурсов
- Scene pipelines могут охватывать viewports на разных дисплеях

Использование:
    # Создание контекста
    context = OffscreenContext()

    # Все дисплеи должны share context с ним
    window_backend = SDLEmbeddedWindowBackend(share_context=context.gl_context)

    # Рендеринг
    context.make_current()
    # ... render to FBOs ...

    # Освобождение
    context.destroy()
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import GraphicsBackend


class OffscreenContext:
    """
    Dedicated offscreen GL context для рендеринга.

    Создаёт hidden SDL window с GL context. Все GPU ресурсы
    (FBO, текстуры, шейдеры, VAO) живут в этом контексте.

    Дисплеи создаются с shared context, что позволяет:
    - Рендерить всё в одном контексте
    - Блитать FBO на любой дисплей
    - Избежать дублирования ресурсов
    """

    # Единственный context_key - всё в одном контексте
    CONTEXT_KEY: int = 0

    def __init__(self):
        """Создаёт hidden SDL window с GL context."""
        import sdl2
        from sdl2 import video

        self._window = None
        self._gl_context = None
        self._graphics: Optional[GraphicsBackend] = None

        # SDL must be initialized by caller (e.g., in run_editor.py)

        # OpenGL 3.3 Core
        video.SDL_GL_SetAttribute(video.SDL_GL_CONTEXT_MAJOR_VERSION, 3)
        video.SDL_GL_SetAttribute(video.SDL_GL_CONTEXT_MINOR_VERSION, 3)
        video.SDL_GL_SetAttribute(
            video.SDL_GL_CONTEXT_PROFILE_MASK,
            video.SDL_GL_CONTEXT_PROFILE_CORE,
        )
        video.SDL_GL_SetAttribute(video.SDL_GL_DOUBLEBUFFER, 1)
        video.SDL_GL_SetAttribute(video.SDL_GL_DEPTH_SIZE, 24)

        # Use 10-bit color (best balance: no banding, no Windows HDR issues)
        video.SDL_GL_SetAttribute(video.SDL_GL_RED_SIZE, 10)
        video.SDL_GL_SetAttribute(video.SDL_GL_GREEN_SIZE, 10)
        video.SDL_GL_SetAttribute(video.SDL_GL_BLUE_SIZE, 10)

        # Hidden window - minimal size, not visible
        flags = video.SDL_WINDOW_OPENGL | video.SDL_WINDOW_HIDDEN

        self._window = video.SDL_CreateWindow(
            b"OffscreenContext",
            0, 0,
            1, 1,  # minimal size
            flags,
        )

        if not self._window:
            raise RuntimeError(f"Failed to create SDL window: {sdl2.SDL_GetError()}")

        self._gl_context = video.SDL_GL_CreateContext(self._window)
        if not self._gl_context:
            video.SDL_DestroyWindow(self._window)
            self._window = None
            raise RuntimeError(f"Failed to create GL context: {sdl2.SDL_GetError()}")

        # Make current and initialize graphics backend
        self.make_current()

        from termin.graphics import OpenGLGraphicsBackend
        self._graphics = OpenGLGraphicsBackend()

        # Ensure OpenGL functions are loaded
        self._graphics.ensure_ready()

    @property
    def graphics(self) -> "GraphicsBackend":
        """GraphicsBackend для этого контекста."""
        return self._graphics

    @property
    def gl_context(self):
        """
        GL context для sharing с дисплеями.

        Передайте это значение в SDLEmbeddedWindowBackend при создании
        окон, чтобы они использовали shared context.
        """
        return self._gl_context

    @property
    def context_key(self) -> int:
        """
        Context key для GPU ресурсов.

        Всегда возвращает CONTEXT_KEY (0), так как все ресурсы
        живут в одном контексте.
        """
        return self.CONTEXT_KEY

    def make_current(self) -> None:
        """
        Активирует GL контекст.

        Вызывайте перед любыми OpenGL операциями.
        """
        from sdl2 import video

        if self._window is not None and self._gl_context is not None:
            result = video.SDL_GL_MakeCurrent(self._window, self._gl_context)
            if result != 0:
                import sdl2
                from termin._native import log
                log.error(f"[OffscreenContext] SDL_GL_MakeCurrent failed: {sdl2.SDL_GetError()}")

    def is_valid(self) -> bool:
        """Проверяет, валиден ли контекст."""
        return self._window is not None and self._gl_context is not None

    def destroy(self) -> None:
        """
        Освобождает ресурсы контекста.

        После вызова контекст нельзя использовать.
        """
        from sdl2 import video

        if self._gl_context is not None:
            video.SDL_GL_DeleteContext(self._gl_context)
            self._gl_context = None

        if self._window is not None:
            video.SDL_DestroyWindow(self._window)
            self._window = None

        self._graphics = None

    def __enter__(self) -> "OffscreenContext":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.destroy()
