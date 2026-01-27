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
    from termin._native.platform import SDLWindow, SDLWindowBackend


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


class SDLWindowRenderSurface:
    """
    SDL окно как render surface.

    Владеет tc_render_surface и tc_input_manager.
    НЕ наследуется от RenderSurface - это обёртка над C объектами.
    """

    _callbacks_initialized: bool = False

    def __init__(
        self,
        sdl_window: "SDLWindow",
        graphics: "GraphicsBackend",
        backend: "SDLWindowBackend",
    ):
        """
        Создаёт SDLWindowRenderSurface.

        Параметры:
            sdl_window: SDL окно (из termin._native.platform.SDLWindow).
            graphics: Графический бэкенд для создания framebuffer handle.
            backend: SDL backend для poll_events.
        """
        self._sdl_window = sdl_window
        self._graphics = graphics
        self._backend = backend
        self._tc_surface_ptr: int = 0
        self._tc_input_manager_ptr: int = 0

        # Устанавливаем graphics для окна
        sdl_window.set_graphics(graphics)

        # Инициализируем глобальные callbacks один раз
        self._init_callbacks()

        # Создаём tc_render_surface
        from termin._native.render import _render_surface_new_external
        self._tc_surface_ptr = _render_surface_new_external(self)

        # Подписываемся на SDL события для передачи в input_manager
        sdl_window.set_framebuffer_size_callback(self._handle_resize)
        sdl_window.set_mouse_button_callback(self._handle_mouse_button)
        sdl_window.set_cursor_pos_callback(self._handle_cursor_pos)
        sdl_window.set_scroll_callback(self._handle_scroll)
        sdl_window.set_key_callback(self._handle_key)

    @classmethod
    def _init_callbacks(cls) -> None:
        """Инициализирует глобальные callbacks для external surfaces."""
        if cls._callbacks_initialized:
            return
        cls._callbacks_initialized = True

        from termin._native.render import (
            _set_render_surface_get_framebuffer_callback,
            _set_render_surface_get_size_callback,
            _set_render_surface_make_current_callback,
            _set_render_surface_swap_buffers_callback,
            _set_render_surface_context_key_callback,
            _set_render_surface_poll_events_callback,
            _set_render_surface_get_window_size_callback,
            _set_render_surface_should_close_callback,
            _set_render_surface_set_should_close_callback,
            _set_render_surface_get_cursor_pos_callback,
        )

        def get_framebuffer(surface: "SDLWindowRenderSurface") -> int:
            fb = surface._sdl_window.get_window_framebuffer()
            return fb.fbo_id if fb else 0

        def get_size(surface: "SDLWindowRenderSurface") -> Tuple[int, int]:
            return surface._sdl_window.framebuffer_size()

        def make_current(surface: "SDLWindowRenderSurface") -> None:
            surface._sdl_window.make_current()

        def swap_buffers(surface: "SDLWindowRenderSurface") -> None:
            surface._sdl_window.swap_buffers()

        def context_key(surface: "SDLWindowRenderSurface") -> int:
            return id(surface._sdl_window)

        def poll_events(surface: "SDLWindowRenderSurface") -> None:
            surface._backend.poll_events()

        def get_window_size(surface: "SDLWindowRenderSurface") -> Tuple[int, int]:
            return surface._sdl_window.window_size()

        def should_close(surface: "SDLWindowRenderSurface") -> bool:
            return surface._sdl_window.should_close()

        def set_should_close(surface: "SDLWindowRenderSurface", value: bool) -> None:
            surface._sdl_window.set_should_close(value)

        def get_cursor_pos(surface: "SDLWindowRenderSurface") -> Tuple[float, float]:
            return surface._sdl_window.get_cursor_pos()

        _set_render_surface_get_framebuffer_callback(get_framebuffer)
        _set_render_surface_get_size_callback(get_size)
        _set_render_surface_make_current_callback(make_current)
        _set_render_surface_swap_buffers_callback(swap_buffers)
        _set_render_surface_context_key_callback(context_key)
        _set_render_surface_poll_events_callback(poll_events)
        _set_render_surface_get_window_size_callback(get_window_size)
        _set_render_surface_should_close_callback(should_close)
        _set_render_surface_set_should_close_callback(set_should_close)
        _set_render_surface_get_cursor_pos_callback(get_cursor_pos)

    # =========================================================================
    # SDL Event Handlers - forward to tc_input_manager
    # =========================================================================

    def _handle_resize(self, window, width: int, height: int) -> None:
        """Обработчик изменения размера framebuffer."""
        if self._tc_surface_ptr:
            from termin._native.render import _render_surface_notify_resize
            _render_surface_notify_resize(self._tc_surface_ptr, width, height)

    def _handle_mouse_button(self, window, button: int, action: int, mods: int) -> None:
        """Обработчик кликов мыши."""
        if self._tc_input_manager_ptr:
            from termin._native.render import _input_manager_on_mouse_button
            _input_manager_on_mouse_button(self._tc_input_manager_ptr, button, action, mods)

    def _handle_cursor_pos(self, window, x: float, y: float) -> None:
        """Обработчик движения мыши."""
        if self._tc_input_manager_ptr:
            from termin._native.render import _input_manager_on_mouse_move
            _input_manager_on_mouse_move(self._tc_input_manager_ptr, x, y)

    def _handle_scroll(self, window, x: float, y: float, mods: int) -> None:
        """Обработчик скролла."""
        if self._tc_input_manager_ptr:
            from termin._native.render import _input_manager_on_scroll
            _input_manager_on_scroll(self._tc_input_manager_ptr, x, y, mods)

    def _handle_key(self, window, key: int, scancode: int, action: int, mods: int) -> None:
        """Обработчик клавиатуры."""
        if self._tc_input_manager_ptr:
            from termin._native.render import _input_manager_on_key
            _input_manager_on_key(self._tc_input_manager_ptr, key, scancode, action, mods)

    # =========================================================================
    # Input Manager
    # =========================================================================

    def set_input_manager(self, input_manager_ptr: int) -> None:
        """Устанавливает tc_input_manager для получения событий."""
        self._tc_input_manager_ptr = input_manager_ptr
        # Связываем input_manager с surface на C стороне
        if self._tc_surface_ptr:
            from termin._native.render import _render_surface_set_input_manager
            _render_surface_set_input_manager(self._tc_surface_ptr, input_manager_ptr)

    @property
    def input_manager_ptr(self) -> int:
        """Указатель на tc_input_manager."""
        return self._tc_input_manager_ptr

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def sdl_window(self) -> "SDLWindow":
        """SDL окно."""
        return self._sdl_window

    @property
    def tc_surface_ptr(self) -> int:
        """Указатель на tc_render_surface."""
        return self._tc_surface_ptr

    @property
    def backend(self) -> "SDLWindowBackend":
        """SDL backend."""
        return self._backend

    # =========================================================================
    # Surface Methods (convenience, delegate to C via vtable)
    # =========================================================================

    def get_framebuffer(self) -> "FramebufferHandle":
        return self._sdl_window.get_window_framebuffer()

    def get_size(self) -> Tuple[int, int]:
        return self._sdl_window.framebuffer_size()

    def window_size(self) -> Tuple[int, int]:
        return self._sdl_window.window_size()

    def make_current(self) -> None:
        self._sdl_window.make_current()

    def swap_buffers(self) -> None:
        self._sdl_window.swap_buffers()

    def poll_events(self) -> None:
        self._backend.poll_events()

    def should_close(self) -> bool:
        return self._sdl_window.should_close()

    def set_should_close(self, value: bool) -> None:
        self._sdl_window.set_should_close(value)

    def get_cursor_pos(self) -> Tuple[float, float]:
        return self._sdl_window.get_cursor_pos()

    def context_key(self) -> int:
        return id(self._sdl_window)

    # =========================================================================
    # Cleanup
    # =========================================================================

    def __del__(self) -> None:
        """Освобождает tc_render_surface."""
        if self._tc_surface_ptr:
            try:
                from termin._native.render import _render_surface_free_external
                _render_surface_free_external(self._tc_surface_ptr)
            except ImportError:
                pass
            self._tc_surface_ptr = 0
