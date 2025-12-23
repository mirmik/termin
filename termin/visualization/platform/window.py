"""
Window — фасад для совместимости со старым API.

Объединяет Display и SimpleDisplayInputManager в один класс,
предоставляя старый API Window для examples и простых приложений.
"""

from __future__ import annotations

from typing import Callable, List, Optional, Tuple, TYPE_CHECKING

from termin.visualization.core.display import Display
from termin.visualization.core.viewport import Viewport
from termin.visualization.platform.backends.base import (
    Action,
    GraphicsBackend,
    MouseButton,
    WindowBackend,
    BackendWindow,
)
from termin.visualization.platform.input_manager import SimpleDisplayInputManager
from termin.visualization.render.surface import RenderSurface, WindowRenderSurface

if TYPE_CHECKING:
    from termin.visualization.core.camera import CameraComponent
    from termin.visualization.core.entity import Entity
    from termin.visualization.core.scene import Scene
    from termin.visualization.ui.canvas import Canvas


class Window:
    """
    Фасад, объединяющий Display и SimpleDisplayInputManager.

    Предоставляет старый API Window для совместимости с examples.
    Внутри создаёт:
    - BackendWindow (платформенное окно)
    - WindowRenderSurface (поверхность рендеринга)
    - Display (управление viewport'ами)
    - SimpleDisplayInputManager (обработка ввода)
    """

    def __init__(
        self,
        width: int,
        height: int,
        title: str,
        graphics: GraphicsBackend,
        window_backend: WindowBackend,
        share: Optional["Window | BackendWindow"] = None,
        **backend_kwargs,
    ):
        """
        Создаёт окно с дисплеем и обработчиком ввода.

        Параметры:
            width: Ширина окна в пикселях.
            height: Высота окна в пикселях.
            title: Заголовок окна.
            graphics: Графический бэкенд.
            window_backend: Бэкенд для создания окна.
            share: Окно для sharing OpenGL контекста.
            **backend_kwargs: Дополнительные параметры для бэкенда.
        """
        self.graphics = graphics
        self.window_backend = window_backend

        # Определяем share handle
        share_handle: Optional[BackendWindow] = None
        if isinstance(share, Window):
            share_handle = share.handle
        elif isinstance(share, BackendWindow):
            share_handle = share

        # Создаём платформенное окно
        self._backend_window: BackendWindow = window_backend.create_window(
            width, height, title, share=share_handle, **backend_kwargs
        )
        self._backend_window.set_user_pointer(self)

        # Создаём surface и display
        self._render_surface = WindowRenderSurface(self._backend_window)
        self._display = Display(self._render_surface)

        # Создаём input manager
        self._input_manager = SimpleDisplayInputManager(
            backend_window=self._backend_window,
            display=self._display,
            on_request_update=self._request_update,
        )

        # Колбэки для внешнего кода (совместимость)
        self.on_mouse_button_event: Optional[
            Callable[[MouseButton, Action, float, float, Optional[Viewport]], None]
        ] = None
        self.on_mouse_move_event: Optional[
            Callable[[float, float, Optional[Viewport]], None]
        ] = None
        self.after_render_handler: Optional[Callable[["Window"], None]] = None

        self._world_mode = "game"

    @property
    def handle(self) -> BackendWindow:
        """Платформенное окно (BackendWindow)."""
        return self._backend_window

    @property
    def display(self) -> Display:
        """Display для управления viewport'ами."""
        return self._display

    @property
    def render_surface(self) -> RenderSurface:
        """RenderSurface для рендеринга."""
        return self._render_surface

    @property
    def viewports(self) -> List[Viewport]:
        """Список viewport'ов (делегирует в Display)."""
        return self._display.viewports

    def set_world_mode(self, mode: str) -> None:
        """Устанавливает режим работы ('game' или 'editor')."""
        self._world_mode = mode

    def close(self) -> None:
        """Закрывает окно."""
        if self._backend_window is not None:
            self._backend_window.close()
            self._backend_window = None

    @property
    def should_close(self) -> bool:
        """Проверяет, должно ли окно закрыться."""
        return self._backend_window is None or self._backend_window.should_close()

    def make_current(self) -> None:
        """Делает контекст текущим."""
        if self._backend_window is not None:
            self._backend_window.make_current()

    def add_viewport(
        self,
        scene: "Scene",
        camera: "CameraComponent",
        rect: Tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0),
        canvas: Optional["Canvas"] = None,
    ) -> Viewport:
        """
        Создаёт и добавляет viewport.

        Параметры:
            scene: Сцена для рендеринга.
            camera: Камера для рендеринга.
            rect: Нормализованный прямоугольник (x, y, w, h).
            canvas: Опциональная 2D канва.

        Возвращает:
            Созданный Viewport.
        """
        if not self._backend_window.drives_render():
            self.make_current()

        return self._display.create_viewport(
            scene=scene,
            camera=camera,
            rect=rect,
            canvas=canvas,
        )

    def update(self, dt: float) -> None:
        """Reserved for future per-window updates."""
        pass

    def viewport_rect_to_pixels(self, viewport: Viewport) -> Tuple[int, int, int, int]:
        """Преобразует rect viewport'а в пиксели."""
        return self._display.viewport_rect_to_pixels(viewport)

    def _request_update(self) -> None:
        """Запрашивает перерисовку."""
        if self._backend_window is not None:
            self._backend_window.request_update()

    def _viewport_under_cursor(self, x: float, y: float) -> Optional[Viewport]:
        """Находит viewport под курсором."""
        return self._display.viewport_at_pixels(x, y)


# Backwards compatibility
GLWindow = Window
