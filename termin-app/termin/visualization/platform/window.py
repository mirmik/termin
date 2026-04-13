"""
Window — фасад для совместимости со старым API.

Объединяет Display и DisplayInputRouter в один класс,
предоставляя старый API Window для examples и простых приложений.
"""

from __future__ import annotations

from typing import Callable, List, Optional, Tuple, TYPE_CHECKING

from termin.visualization.core.display import Display
from termin.visualization.core.viewport import Viewport
from tcbase import (
    Action,
    MouseButton,
)
from termin.visualization.platform.input_manager import DisplayInputRouter

if TYPE_CHECKING:
    from termin.visualization.core.camera import CameraComponent
    from termin.visualization.core.scene import Scene
    from tgfx import GraphicsBackend
    from termin._native.platform import SDLWindowBackend, SDLWindowRenderSurface


class Window:
    """
    Фасад, объединяющий Display и DisplayInputRouter.

    Предоставляет старый API Window для совместимости с examples.
    Внутри создаёт:
    - SDLWindowRenderSurface (C++ окно + поверхность рендеринга)
    - Display (управление viewport'ами)
    - DisplayInputRouter (маршрутизация ввода на viewport'ы)
    """

    def __init__(
        self,
        width: int,
        height: int,
        title: str,
        graphics: "GraphicsBackend",
        backend: "SDLWindowBackend",
        share: Optional["Window | SDLWindowRenderSurface"] = None,
    ):
        """
        Создаёт окно с дисплеем и обработчиком ввода.

        Параметры:
            width: Ширина окна в пикселях.
            height: Высота окна в пикселях.
            title: Заголовок окна.
            graphics: Графический бэкенд.
            backend: C++ SDLWindowBackend.
            share: Окно для sharing OpenGL контекста.
        """
        from termin._native.platform import SDLWindowRenderSurface

        self._graphics = graphics
        self._backend = backend

        # Определяем share surface
        share_surface: Optional[SDLWindowRenderSurface] = None
        if isinstance(share, Window):
            share_surface = share._surface
        elif share is not None:
            share_surface = share

        # Создаём C++ SDLWindowRenderSurface (окно + surface)
        self._surface: SDLWindowRenderSurface = SDLWindowRenderSurface(
            width, height, title, backend, share_surface
        )
        self._surface.set_graphics(graphics)

        # Создаём Display
        self._display = Display(self._surface)

        # Создаём input router (auto-attaches to display's surface)
        self._input_router = DisplayInputRouter(self._display.tc_display_ptr)

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
    def surface(self) -> "SDLWindowRenderSurface":
        """C++ SDLWindowRenderSurface."""
        return self._surface

    @property
    def display(self) -> Display:
        """Display для управления viewport'ами."""
        return self._display

    @property
    def viewports(self) -> List[Viewport]:
        """Список viewport'ов (делегирует в Display)."""
        return self._display.viewports

    def set_world_mode(self, mode: str) -> None:
        """Устанавливает режим работы ('game' или 'editor')."""
        self._world_mode = mode

    def close(self) -> None:
        """Закрывает окно."""
        # C++ surface handles cleanup
        self._surface = None

    @property
    def should_close(self) -> bool:
        """Проверяет, должно ли окно закрыться."""
        return self._surface is None or self._surface.should_close()

    def make_current(self) -> None:
        """Делает контекст текущим."""
        if self._surface is not None:
            self._surface.make_current()

    def swap_buffers(self) -> None:
        """Swap buffers."""
        if self._surface is not None:
            self._surface.swap_buffers()

    def poll_events(self) -> None:
        """Poll SDL events."""
        self._backend.poll_events()

    def add_viewport(
        self,
        scene: "Scene",
        camera: "CameraComponent",
        rect: Tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0),
    ) -> Viewport:
        """
        Создаёт и добавляет viewport.

        Параметры:
            scene: Сцена для рендеринга.
            camera: Камера для рендеринга.
            rect: Нормализованный прямоугольник (x, y, w, h).

        Возвращает:
            Созданный Viewport.
        """
        self.make_current()

        return self._display.create_viewport(
            scene=scene,
            camera=camera,
            rect=rect,
        )

    def update(self, dt: float) -> None:
        """Reserved for future per-window updates."""
        pass

    def viewport_rect_to_pixels(self, viewport: Viewport) -> Tuple[int, int, int, int]:
        """Преобразует rect viewport'а в пиксели."""
        return self._display.viewport_rect_to_pixels(viewport)

    def _request_update(self) -> None:
        """Запрашивает перерисовку."""
        if self._surface is not None:
            self._surface.request_update()

    def _viewport_under_cursor(self, x: float, y: float) -> Optional[Viewport]:
        """Находит viewport под курсором."""
        return self._display.viewport_at_pixels(x, y)

    def get_size(self) -> Tuple[int, int]:
        """Returns framebuffer size."""
        if self._surface is not None:
            return self._surface.get_size()
        return (0, 0)


# Backwards compatibility
GLWindow = Window
