"""
EditorDisplayInputManager — обработка ввода для редактора.

Расширяет функциональность SimpleDisplayInputManager:
- Поддержка editor mode vs game mode
- Picking через ID buffer
- Внешние колбэки для редакторских событий
"""

from __future__ import annotations

import time
from typing import Callable, Optional, Tuple, TYPE_CHECKING

from termin.visualization.platform.backends.base import (
    Action,
    Key,
    MouseButton,
)
from termin.visualization.core.camera import CameraController
from termin.visualization.core.entity import Entity
from termin.visualization.core.picking import rgb_to_id
from termin.visualization.core.input_events import (
    MouseButtonEvent,
    MouseMoveEvent,
    ScrollEvent,
    KeyEvent,
)

if TYPE_CHECKING:
    from termin.visualization.core.display import Display
    from termin.visualization.core.viewport import Viewport
    from termin.visualization.platform.backends.base import (
        BackendWindow,
        FramebufferHandle,
        GraphicsBackend,
    )


class EditorDisplayInputManager:
    """
    Обработчик ввода для редактора.

    Поддерживает два режима:
    - "editor": редакторский режим с picking, гизмо, внешними колбэками
    - "game": игровой режим, роутит события в сцену

    Для picking требуется доступ к FBO pool через get_fbo_pool колбэк.
    """

    def __init__(
        self,
        backend_window: "BackendWindow",
        display: "Display",
        graphics: "GraphicsBackend",
        get_fbo_pool: Callable[[], dict] | None = None,
        on_request_update: Callable[[], None] | None = None,
        on_mouse_button_event: Callable[[MouseButton, Action, float, float, Optional["Viewport"]], None] | None = None,
        on_mouse_move_event: Callable[[float, float, Optional["Viewport"]], None] | None = None,
    ):
        """
        Создаёт EditorDisplayInputManager.

        Параметры:
            backend_window: Платформенное окно для подписки на события.
            display: Display для роутинга событий в viewport'ы.
            graphics: GraphicsBackend для чтения пикселей из FBO.
            get_fbo_pool: Колбэк для получения FBO pool (для picking).
            on_request_update: Колбэк для запроса перерисовки.
            on_mouse_button_event: Колбэк для внешней обработки кликов.
            on_mouse_move_event: Колбэк для внешней обработки движения мыши.
        """
        self._backend_window = backend_window
        self._display = display
        self._graphics = graphics
        self._get_fbo_pool = get_fbo_pool
        self._on_request_update = on_request_update
        self._on_mouse_button_event = on_mouse_button_event
        self._on_mouse_move_event = on_mouse_move_event

        self._active_viewport: Optional["Viewport"] = None
        self._last_cursor: Optional[Tuple[float, float]] = None
        self._world_mode = "editor"  # "editor" or "game"

        # Double-click tracking
        self._last_click_time: float = 0.0
        self._double_click_threshold: float = 0.3

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

    @property
    def world_mode(self) -> str:
        """Текущий режим: 'editor' или 'game'."""
        return self._world_mode

    def set_world_mode(self, mode: str) -> None:
        """Устанавливает режим работы."""
        self._world_mode = mode

    def _dispatch_to_camera(self, viewport: "Viewport", event_name: str, event) -> None:
        """Диспатчит событие в InputComponent'ы камеры viewport'а."""
        from termin.visualization.core.component import InputComponent
        camera = viewport.camera
        if camera is None or camera.entity is None:
            return
        for comp in camera.entity.components:
            if isinstance(comp, InputComponent):
                handler = getattr(comp, event_name, None)
                if handler:
                    handler(event)

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
    # Picking support
    # ----------------------------------------------------------------

    def pick_color_at(
        self,
        x: float,
        y: float,
        viewport: Optional["Viewport"] = None,
        buffer_name: str = "color",
    ) -> Optional[Tuple[float, float, float, float]]:
        """
        Читает цвет пикселя из FBO.

        Параметры:
            x, y: координаты в пикселях окна (origin сверху-слева).
            viewport: viewport для которого читаем (или определяется автоматически).
            buffer_name: имя ресурса в fbo_pool.

        Возвращает:
            (r, g, b, a) в [0..1] или None.
        """
        if self._get_fbo_pool is None:
            return None

        fbo_pool = self._get_fbo_pool()
        if fbo_pool is None:
            return None

        if viewport is None:
            viewport = self._viewport_under_cursor(x, y)
            if viewport is None:
                return None

        win_w, win_h = self._backend_window.window_size()
        fb_w, fb_h = self._backend_window.framebuffer_size()

        if win_w <= 0 or win_h <= 0 or fb_w <= 0 or fb_h <= 0:
            return None

        px, py, pw, ph = self._viewport_rect_to_pixels(viewport)

        # Переводим координаты мыши из логических в физические
        sx = fb_w / float(win_w)
        sy = fb_h / float(win_h)
        x_phys = x * sx
        y_phys = y * sy

        # Локальные координаты внутри viewport'а
        vx = x_phys - px
        vy = y_phys - py

        if vx < 0 or vy < 0 or vx >= pw or vy >= ph:
            return None

        # Перевод в координаты FBO (origin снизу-слева)
        read_x = int(vx)
        read_y = int(ph - vy - 1)

        fb = fbo_pool.get(buffer_name)
        if fb is None:
            return None

        r, g, b, a = self._graphics.read_pixel(fb, read_x, read_y)
        # Возвращаем framebuffer обратно на окно
        window_fb = self._backend_window.get_window_framebuffer()
        self._graphics.bind_framebuffer(window_fb)
        return (r, g, b, a)

    def pick_entity_at(
        self,
        x: float,
        y: float,
        viewport: Optional["Viewport"] = None,
    ) -> Optional[Entity]:
        """
        Читает entity под пикселем из id-карты.

        Параметры:
            x, y: координаты в пикселях окна.
            viewport: viewport для которого читаем.

        Возвращает:
            Entity или None.
        """
        color = self.pick_color_at(x, y, viewport, buffer_name="id")
        if color is None:
            return None
        r, g, b, a = color
        pid = rgb_to_id(r, g, b)
        if pid == 0:
            return None
        return Entity.lookup_by_pick_id(pid)

    def pick_depth_at(
        self,
        x: float,
        y: float,
        viewport: Optional["Viewport"] = None,
        buffer_name: str = "id",
    ) -> Optional[float]:
        """
        Читает глубину под пикселем из указанного буфера.

        Параметры:
            x, y: координаты в пикселях окна.
            viewport: viewport для которого читаем.
            buffer_name: имя буфера в FBO pool (по умолчанию 'id').

        Возвращает:
            Глубину в диапазоне [0, 1] или None.
        """
        if self._get_fbo_pool is None:
            return None

        fbo_pool = self._get_fbo_pool()
        if fbo_pool is None:
            return None

        if viewport is None:
            viewport = self._viewport_under_cursor(x, y)
            if viewport is None:
                return None

        win_w, win_h = self._backend_window.window_size()
        fb_w, fb_h = self._backend_window.framebuffer_size()

        if win_w <= 0 or win_h <= 0 or fb_w <= 0 or fb_h <= 0:
            return None

        px, py, pw, ph = self._viewport_rect_to_pixels(viewport)

        # Переводим координаты мыши из логических в физические
        sx = fb_w / float(win_w)
        sy = fb_h / float(win_h)
        x_phys = x * sx
        y_phys = y * sy

        # Локальные координаты внутри viewport'а
        vx = x_phys - px
        vy = y_phys - py

        if vx < 0 or vy < 0 or vx >= pw or vy >= ph:
            return None

        # Перевод в координаты FBO (origin снизу-слева)
        read_x = int(vx)
        read_y = int(ph - vy - 1)

        fb = fbo_pool.get(buffer_name)
        if fb is None:
            return None

        depth = self._graphics.read_depth_pixel(fb, read_x, read_y)
        # Возвращаем framebuffer обратно на окно
        window_fb = self._backend_window.get_window_framebuffer()
        self._graphics.bind_framebuffer(window_fb)
        return depth

    # ----------------------------------------------------------------
    # Event handlers
    # ----------------------------------------------------------------

    def _handle_mouse_button(self, window, button: MouseButton, action: Action, mods: int) -> None:
        """Обработчик нажатия кнопки мыши."""
        if self._world_mode == "game":
            self._handle_mouse_button_game_mode(button, action, mods)
        else:
            self._handle_mouse_button_editor_mode(button, action, mods)

    def _handle_mouse_button_game_mode(self, button: MouseButton, action: Action, mods: int) -> None:
        """Обработка клика в игровом режиме."""
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

        # Track active viewport
        if action == Action.PRESS:
            self._active_viewport = viewport
        if action == Action.RELEASE:
            self._last_cursor = None
            if viewport is None:
                viewport = self._active_viewport
            self._active_viewport = None

        # Dispatch to camera
        if viewport is not None:
            event = MouseButtonEvent(
                viewport=viewport, x=x, y=y,
                button=button, action=action, mods=mods
            )
            self._dispatch_to_camera(viewport, "on_mouse_button", event)

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

        # Editor callbacks for picking/gizmo (allow editing in game mode)
        if self._on_mouse_button_event is not None:
            self._on_mouse_button_event(button, action, x, y, viewport)

        self._request_update()

    def _handle_mouse_button_editor_mode(self, button: MouseButton, action: Action, mods: int) -> None:
        """Обработка клика в редакторском режиме."""
        x, y = self._backend_window.get_cursor_pos()
        viewport = self._viewport_under_cursor(x, y)

        # Double-click detection
        is_double_click = False
        if action == Action.PRESS and button == MouseButton.LEFT:
            current_time = time.time()
            if current_time - self._last_click_time < self._double_click_threshold:
                is_double_click = True
            self._last_click_time = current_time

        # Track active viewport
        if action == Action.PRESS:
            self._active_viewport = viewport
        if action == Action.RELEASE:
            self._last_cursor = None
            if viewport is None:
                viewport = self._active_viewport
            self._active_viewport = None

        # Dispatch to camera (в editor mode события идут только в камеру)
        if viewport is not None:
            event = MouseButtonEvent(
                viewport=viewport, x=x, y=y,
                button=button, action=action, mods=mods
            )
            self._dispatch_to_camera(viewport, "on_mouse_button", event)

        # Double-click: center camera on clicked entity
        if is_double_click and viewport is not None:
            self._handle_double_click(x, y, viewport)

        # Внешний колбэк для редактора (picking, гизмо, etc.)
        if self._on_mouse_button_event is not None:
            self._on_mouse_button_event(button, action, x, y, viewport)

        self._request_update()

    def _handle_double_click(self, x: float, y: float, viewport: "Viewport") -> None:
        """Обработка двойного клика — центрирование камеры на объекте."""
        entity = self.pick_entity_at(x, y, viewport)
        if entity is None:
            return

        # Получаем позицию entity
        target_position = entity.transform.global_pose().lin

        # Находим контроллер камеры
        camera = viewport.camera
        if camera is None or camera.entity is None:
            return

        controller = camera.entity.get_component(CameraController)
        if controller is not None:
            controller.center_on(target_position)

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

        # Dispatch to camera
        if viewport is not None:
            event = MouseMoveEvent(viewport=viewport, x=x, y=y, dx=dx, dy=dy)
            self._dispatch_to_camera(viewport, "on_mouse_move", event)

        # Внешний колбэк
        if self._on_mouse_move_event is not None:
            self._on_mouse_move_event(x, y, viewport)

        self._request_update()

    def _handle_scroll(self, window, xoffset: float, yoffset: float) -> None:
        """Обработчик скролла."""
        x, y = self._backend_window.get_cursor_pos()
        viewport = self._viewport_under_cursor(x, y) or self._active_viewport

        if viewport is not None:
            event = ScrollEvent(viewport=viewport, x=x, y=y, xoffset=xoffset, yoffset=yoffset)
            self._dispatch_to_camera(viewport, "on_scroll", event)

        self._request_update()

    def _handle_key(self, window, key: Key, scancode: int, action: Action, mods: int) -> None:
        """Обработчик нажатия клавиши."""
        # ESC в игровом режиме закрывает окно
        if self._world_mode == "game" and key == Key.ESCAPE and action == Action.PRESS:
            self._backend_window.set_should_close(True)

        viewport = self._active_viewport or (
            self._display.viewports[0] if self._display.viewports else None
        )

        if viewport is not None:
            event = KeyEvent(
                viewport=viewport,
                key=key, scancode=scancode, action=action, mods=mods
            )
            self._dispatch_to_camera(viewport, "on_key", event)

        self._request_update()
