"""
DisplayInputManager — обработка ввода для Display.

SimpleDisplayInputManager — базовый обработчик для простых приложений (examples).
Роутит события мыши/клавиатуры в сцену через InputComponent'ы.

EditorDisplayInputManager — расширенный обработчик для редактора.
Добавляет поддержку picking, gizmo, editor mode.
"""

from __future__ import annotations

from typing import Callable, Optional, Tuple, TYPE_CHECKING

from termin.visualization.platform.backends.base import (
    Action,
    Key,
    MouseButton,
)

if TYPE_CHECKING:
    from termin.visualization.core.display import Display
    from termin.visualization.core.viewport import Viewport
    from termin.visualization.platform.backends.base import BackendWindow
    from termin.visualization.render.surface import WindowRenderSurface


class SimpleDisplayInputManager:
    """
    Простой обработчик ввода для Display.

    Роутит события мыши и клавиатуры в сцену:
    - Mouse button → on_mouse_button в InputComponent'ах
    - Mouse move → on_mouse_move в InputComponent'ах
    - Scroll → on_scroll в InputComponent'ах
    - Key → on_key в InputComponent'ах

    Также обрабатывает:
    - Canvas UI события
    - Object click (raycast + on_click)
    - ESC для закрытия окна
    """

    def __init__(
        self,
        backend_window: "BackendWindow",
        display: "Display",
        on_request_update: Callable[[], None] | None = None,
    ):
        """
        Создаёт SimpleDisplayInputManager.

        Параметры:
            backend_window: Платформенное окно для подписки на события.
            display: Display для роутинга событий в viewport'ы.
            on_request_update: Колбэк для запроса перерисовки.
        """
        self._backend_window = backend_window
        self._display = display
        self._on_request_update = on_request_update

        self._active_viewport: Optional["Viewport"] = None
        self._last_cursor: Optional[Tuple[float, float]] = None

        # Подписываемся на события окна
        backend_window.set_cursor_pos_callback(self._handle_cursor_pos)
        backend_window.set_scroll_callback(self._handle_scroll)
        backend_window.set_mouse_button_callback(self._handle_mouse_button)
        backend_window.set_key_callback(self._handle_key)

    @property
    def display(self) -> "Display":
        """Display, к которому привязан input manager."""
        return self._display

    @property
    def backend_window(self) -> "BackendWindow":
        """Платформенное окно."""
        return self._backend_window

    def _request_update(self) -> None:
        """Запрашивает перерисовку."""
        if self._on_request_update is not None:
            self._on_request_update()
        else:
            self._backend_window.request_update()

    def _viewport_under_cursor(self, x: float, y: float) -> Optional["Viewport"]:
        """Находит viewport под курсором."""
        return self._display.viewport_at_pixels(x, y)

    def _viewport_rect_to_pixels(self, viewport: "Viewport") -> Tuple[int, int, int, int]:
        """Преобразует rect viewport'а в пиксели."""
        return self._display.viewport_rect_to_pixels(viewport)

    # ----------------------------------------------------------------
    # Event handlers
    # ----------------------------------------------------------------

    def _handle_mouse_button(self, window, button: MouseButton, action: Action, mods: int) -> None:
        """Обработчик нажатия кнопки мыши."""
        print(f"[SimpleDisplayInputManager] mouse_button: {button} {action}", flush=True)
        x, y = self._backend_window.get_cursor_pos()
        viewport = self._viewport_under_cursor(x, y)

        # UI click handling
        if viewport and viewport.canvas:
            rect = self._viewport_rect_to_pixels(viewport)
            if action == Action.PRESS:
                if viewport.canvas.mouse_down(x, y, rect):
                    return
            elif action == Action.RELEASE:
                if viewport.canvas.mouse_up(x, y, rect):
                    return

        # Track active viewport for drag operations
        if action == Action.PRESS:
            self._active_viewport = viewport
        if action == Action.RELEASE:
            self._last_cursor = None
            if viewport is None:
                viewport = self._active_viewport
            self._active_viewport = None

        # Dispatch to scene
        if viewport is not None:
            viewport.scene.dispatch_input(
                viewport, "on_mouse_button",
                button=button, action=action, mods=mods
            )

        # Object click handling (raycast)
        if viewport is not None and action == Action.PRESS and button == MouseButton.LEFT:
            cam = viewport.camera
            if cam is not None:
                rect = self._viewport_rect_to_pixels(viewport)
                ray = cam.screen_point_to_ray(x, y, viewport_rect=rect)
                hit = viewport.scene.raycast(ray)
                if hit is not None:
                    entity = hit.entity
                    for comp in entity.components:
                        on_click = getattr(comp, "on_click", None)
                        if on_click is not None:
                            on_click(hit, button)

        self._request_update()

    def _handle_cursor_pos(self, window, x: float, y: float) -> None:
        """Обработчик движения мыши."""
        if self._last_cursor is None:
            dx = dy = 0.0
        else:
            dx = x - self._last_cursor[0]
            dy = y - self._last_cursor[1]

        self._last_cursor = (x, y)
        viewport = self._active_viewport or self._viewport_under_cursor(x, y)

        # Canvas hover
        if viewport and viewport.canvas:
            rect = self._viewport_rect_to_pixels(viewport)
            viewport.canvas.mouse_move(x, y, rect)

        # Dispatch to scene
        if viewport is not None:
            viewport.scene.dispatch_input(
                viewport, "on_mouse_move",
                x=x, y=y, dx=dx, dy=dy
            )

        self._request_update()

    def _handle_scroll(self, window, xoffset: float, yoffset: float) -> None:
        """Обработчик скролла."""
        x, y = self._backend_window.get_cursor_pos()
        viewport = self._viewport_under_cursor(x, y) or self._active_viewport

        if viewport is not None:
            viewport.scene.dispatch_input(
                viewport, "on_scroll",
                xoffset=xoffset, yoffset=yoffset
            )

        self._request_update()

    def _handle_key(self, window, key: Key, scancode: int, action: Action, mods: int) -> None:
        """Обработчик нажатия клавиши."""
        # ESC closes window
        if key == Key.ESCAPE and action == Action.PRESS:
            self._backend_window.set_should_close(True)

        viewport = self._active_viewport or (
            self._display.viewports[0] if self._display.viewports else None
        )

        if viewport is not None:
            viewport.scene.dispatch_input(
                viewport, "on_key",
                key=key, scancode=scancode, action=action, mods=mods
            )

        self._request_update()
