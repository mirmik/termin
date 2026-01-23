"""
RenderSurface — абстракция целевой поверхности рендеринга.

Поверхность определяет "куда рендерим":
- WindowRenderSurface: рендер в окно (GLFW, Qt, etc.)
- OffscreenRenderSurface: рендер в offscreen FBO

Поверхность НЕ знает о сценах, камерах и пайплайнах — это забота RenderView и RenderEngine.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, TYPE_CHECKING, Tuple

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import (
        BackendWindow,
        FramebufferHandle,
        GraphicsBackend,
    )


class RenderSurface(ABC):
    """
    Абстрактная поверхность рендеринга.
    
    Определяет целевой буфер (FBO) и его размеры.
    Не содержит логики рендеринга — только предоставляет target.
    """

    @abstractmethod
    def get_framebuffer(self) -> "FramebufferHandle":
        """
        Возвращает FBO для рендеринга.
        
        Для окна это default framebuffer (id=0).
        Для offscreen — созданный offscreen FBO.
        """
        ...

    @abstractmethod
    def get_size(self) -> Tuple[int, int]:
        """
        Возвращает размер поверхности в пикселях (width, height).
        """
        ...

    @abstractmethod
    def make_current(self) -> None:
        """
        Делает контекст текущим (для OpenGL).
        
        Для offscreen может быть no-op если контекст уже активен.
        """
        ...

    def present(self) -> None:
        """
        Представляет результат рендеринга (swap buffers для окна).

        Для offscreen — no-op.
        """
        pass

    def set_on_resize(self, callback: Callable[[int, int], None] | None) -> None:
        """
        Set callback for resize events.

        For offscreen surfaces this is a no-op (size doesn't change dynamically).
        """
        pass

    def context_key(self) -> int:
        """
        Уникальный ключ контекста для кэширования VAO/шейдеров.
        
        По умолчанию используется id объекта.
        """
        return id(self)


class OffscreenRenderSurface(RenderSurface):
    """
    Offscreen поверхность рендеринга.
    
    Создаёт собственный FBO заданного размера.
    Требует активного OpenGL контекста при создании.
    
    Использование:
        # Создание offscreen поверхности
        surface = OffscreenRenderSurface(graphics, width=800, height=600)
        
        # Рендеринг
        engine.render_to_surface(surface, views)
        
        # Чтение результата
        pixels = surface.read_pixels()
    """

    def __init__(
        self,
        graphics: "GraphicsBackend",
        width: int,
        height: int,
    ):
        """
        Инициализирует offscreen поверхность.
        
        Параметры:
            graphics: Графический бэкенд (OpenGL).
            width: Ширина в пикселях.
            height: Высота в пикселях.
        """
        self._graphics = graphics
        self._width = width
        self._height = height
        self._framebuffer: "FramebufferHandle" = graphics.create_framebuffer((width, height))

    def get_framebuffer(self) -> "FramebufferHandle":
        return self._framebuffer

    def get_size(self) -> Tuple[int, int]:
        return (self._width, self._height)

    def make_current(self) -> None:
        # Для offscreen контекст должен быть уже активен
        pass

    def resize(self, width: int, height: int) -> None:
        """
        Изменяет размер offscreen поверхности.
        
        Пересоздаёт FBO с новыми размерами.
        """
        if width == self._width and height == self._height:
            return
        self._width = width
        self._height = height
        self._framebuffer.resize((width, height))

    def read_pixels(self) -> "np.ndarray":
        """
        Читает пиксели из offscreen буфера.
        
        Возвращает:
            numpy массив формата (height, width, 4) с RGBA значениями [0..255].
        """
        import numpy as np
        from OpenGL import GL as gl

        self._graphics.bind_framebuffer(self._framebuffer)
        
        w, h = self._width, self._height
        data = gl.glReadPixels(0, 0, w, h, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
        
        if isinstance(data, (bytes, bytearray)):
            arr = np.frombuffer(data, dtype=np.uint8)
        else:
            arr = np.array(data, dtype=np.uint8)
        
        # Reshape: OpenGL даёт данные снизу вверх, переворачиваем
        arr = arr.reshape((h, w, 4))
        arr = np.flipud(arr)
        
        return arr

    def delete(self) -> None:
        """
        Освобождает ресурсы offscreen поверхности.
        """
        if self._framebuffer is not None:
            self._framebuffer.delete()
            self._framebuffer = None


class WindowRenderSurface(RenderSurface):
    """
    RenderSurface для окна.

    Владеет ссылкой на BackendWindow и предоставляет доступ к его framebuffer.
    """

    def __init__(
        self,
        backend_window: "BackendWindow",
        on_resize: Callable[[int, int], None] | None = None,
    ):
        """
        Создаёт WindowRenderSurface.

        Параметры:
            backend_window: Платформенное окно (GLFW, Qt, etc.).
            on_resize: Опциональный колбэк при изменении размера framebuffer.
        """
        self._backend_window = backend_window
        self._on_resize = on_resize

        # Подписываемся на resize если нужно
        if on_resize is not None:
            backend_window.set_framebuffer_size_callback(self._handle_resize)

    @property
    def backend_window(self) -> "BackendWindow":
        """Платформенное окно."""
        return self._backend_window

    def _handle_resize(self, window, width: int, height: int) -> None:
        """Обработчик изменения размера framebuffer."""
        if self._on_resize is not None:
            self._on_resize(width, height)

    def set_on_resize(self, callback: Callable[[int, int], None] | None) -> None:
        """Set resize callback."""
        self._on_resize = callback
        if callback is not None:
            self._backend_window.set_framebuffer_size_callback(self._handle_resize)

    def get_framebuffer(self) -> "FramebufferHandle":
        return self._backend_window.get_window_framebuffer()

    def get_size(self) -> Tuple[int, int]:
        return self._backend_window.framebuffer_size()

    def window_size(self) -> Tuple[int, int]:
        """Возвращает логический размер окна (может отличаться от framebuffer на HiDPI)."""
        return self._backend_window.window_size()

    def make_current(self) -> None:
        self._backend_window.make_current()

    def present(self) -> None:
        self._backend_window.swap_buffers()

    def context_key(self) -> int:
        return id(self._backend_window)

    def should_close(self) -> bool:
        """Проверяет, должно ли окно закрыться."""
        return self._backend_window.should_close()

    def set_should_close(self, value: bool) -> None:
        """Устанавливает флаг закрытия окна."""
        self._backend_window.set_should_close(value)

    def request_update(self) -> None:
        """Запрашивает перерисовку окна."""
        self._backend_window.request_update()

    def get_cursor_pos(self) -> Tuple[float, float]:
        """Возвращает позицию курсора в пикселях окна."""
        return self._backend_window.get_cursor_pos()
