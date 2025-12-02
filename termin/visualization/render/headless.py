"""
HeadlessContext — невидимое окно для создания OpenGL контекста.

Используется для offscreen рендеринга без отображения окна.
Контекст нужен для создания FBO, текстур, шейдеров и т.п.

Использование:
    # Создание headless контекста
    context = HeadlessContext()
    context.make_current()
    
    # Теперь можно использовать OpenGL
    graphics = OpenGLGraphicsBackend()
    offscreen = OffscreenRenderSurface(graphics, 800, 600)
    ...
    
    # Освобождение ресурсов
    context.destroy()
"""

from __future__ import annotations


class HeadlessContext:
    """
    Невидимое окно GLFW для создания OpenGL контекста.
    
    Позволяет выполнять OpenGL операции без создания видимого окна.
    """

    def __init__(self, width: int = 1, height: int = 1):
        """
        Создаёт невидимое окно и OpenGL контекст.
        
        Параметры:
            width: Ширина скрытого окна (по умолчанию 1).
            height: Высота скрытого окна (по умолчанию 1).
        """
        import glfw
        
        if not glfw.init():
            raise RuntimeError("Failed to initialize GLFW")
        
        # Настройки для создания современного OpenGL контекста
        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        
        # Делаем окно невидимым
        glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
        
        self._window = glfw.create_window(width, height, "headless", None, None)
        if not self._window:
            glfw.terminate()
            raise RuntimeError("Failed to create headless GLFW window")
        
        # Активируем контекст
        glfw.make_context_current(self._window)

    def make_current(self) -> None:
        """
        Делает контекст текущим.
        
        Вызывается перед OpenGL операциями.
        """
        import glfw
        if self._window is not None:
            glfw.make_context_current(self._window)

    def destroy(self) -> None:
        """
        Освобождает ресурсы контекста.
        
        После вызова контекст нельзя использовать.
        """
        import glfw
        if self._window is not None:
            glfw.destroy_window(self._window)
            self._window = None

    def __enter__(self) -> "HeadlessContext":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.destroy()
