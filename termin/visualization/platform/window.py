"""Window abstraction delegating platform details to a backend."""

from __future__ import annotations

from typing import Callable, List, Optional, Tuple, TYPE_CHECKING

from termin.visualization.core.camera import CameraComponent
from termin.visualization.core.scene import Scene
from termin.visualization.platform.backends.base import (
    Action,
    GraphicsBackend,
    Key,
    MouseButton,
    WindowBackend,
    BackendWindow,
)
from termin.visualization.core.viewport import Viewport
from termin.visualization.core.entity import Entity
from termin.visualization.ui.canvas import Canvas
from termin.visualization.core.picking import rgb_to_id
from termin.visualization.render.surface import RenderSurface

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import FramebufferHandle


class WindowRenderSurface(RenderSurface):
    """
    RenderSurface для окна.
    
    Лёгкий объект, предоставляющий доступ к framebuffer окна
    через интерфейс RenderSurface. Не владеет окном.
    """

    def __init__(self, window: "Window"):
        self._window = window

    def get_framebuffer(self) -> "FramebufferHandle":
        return self._window.handle.get_window_framebuffer()

    def get_size(self) -> Tuple[int, int]:
        return self._window.handle.framebuffer_size()

    def make_current(self) -> None:
        self._window.make_current()

    def present(self) -> None:
        if self._window.handle is not None:
            self._window.handle.swap_buffers()

    def context_key(self) -> int:
        return id(self._window)


class Window:
    """
    Manages a platform window and a set of viewports.
    
    Window отвечает за:
    - Создание и управление окном через backend
    - Хранение списка viewports
    - Обработку событий мыши/клавиатуры
    - Преобразование координат
    - Предоставление RenderSurface для рендеринга
    
    НЕ отвечает за:
    - Рендеринг (это делает RenderEngine снаружи)
    - Управление pipeline и FBO (это ViewportRenderState)
    
    Для рендеринга используйте window.render_surface с RenderEngine.
    """

    def __init__(
        self,
        width: int,
        height: int,
        title: str,
        graphics: GraphicsBackend,
        window_backend: WindowBackend,
        share=None,
        **backend_kwargs
    ):
        self.graphics = graphics
        share_handle = None
        if isinstance(share, Window):
            share_handle = share.handle
        elif isinstance(share, BackendWindow):
            share_handle = share

        self.window_backend = window_backend
        self.handle: BackendWindow = self.window_backend.create_window(
            width, height, title, share=share_handle, **backend_kwargs
        )

        # RenderSurface для этого окна
        self._render_surface = WindowRenderSurface(self)

        self.viewports: List[Viewport] = []
        self._active_viewport: Optional[Viewport] = None
        self._last_cursor: Optional[Tuple[float, float]] = None

        self.handle.set_user_pointer(self)
        self.handle.set_framebuffer_size_callback(self._handle_framebuffer_resize)
        self.handle.set_cursor_pos_callback(self._handle_cursor_pos)
        self.handle.set_scroll_callback(self._handle_scroll)
        self.handle.set_mouse_button_callback(self._handle_mouse_button)
        self.handle.set_key_callback(self._handle_key)

        # Обработчики событий для внешнего кода (например, editor)
        self.on_mouse_button_event: Optional[
            Callable[[MouseButton, Action, float, float, Optional[Viewport]], None]
        ] = None
        self.on_mouse_move_event: Optional[
            Callable[[float, float, Optional[Viewport]], None]
        ] = None
        self.after_render_handler: Optional[Callable[["Window"], None]] = None

        self._world_mode = "game"  # or "editor"

    @property
    def render_surface(self) -> RenderSurface:
        """
        Возвращает RenderSurface для рендеринга в это окно.
        
        Используйте с RenderEngine:
            engine.render_views(window.render_surface, views)
        """
        return self._render_surface

    def set_world_mode(self, mode: str):
        self._world_mode = mode

    def close(self):
        if self.handle:
            self.handle.close()
            self.handle = None

    @property
    def should_close(self) -> bool:
        return self.handle is None or self.handle.should_close()

    def make_current(self):
        if self.handle is not None:
            self.handle.make_current()

    def add_viewport(
        self,
        scene: Scene,
        camera: CameraComponent,
        rect: Tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0),
        canvas: Optional[Canvas] = None,
    ) -> Viewport:
        """
        Создаёт и добавляет новый viewport.
        
        Параметры:
            scene: Сцена для рендеринга.
            camera: Камера для рендеринга.
            rect: Нормализованный прямоугольник (x, y, w, h).
            canvas: Опциональная 2D канва.
        
        Возвращает:
            Созданный Viewport.
        """
        if not self.handle.drives_render():
            self.make_current()
        scene.ensure_ready(self.graphics)
        
        viewport = Viewport(
            scene=scene,
            camera=camera,
            rect=rect,
            canvas=canvas,
            window=self,
        )
        camera.viewport = viewport
        self.viewports.append(viewport)
        return viewport

    def update(self, dt: float):
        """Reserved for future per-window updates."""
        pass

    def viewport_rect_to_pixels(self, viewport: Viewport) -> Tuple[int, int, int, int]:
        """
        Преобразует нормализованный rect viewport'а в пиксели.
        
        Возвращает:
            (px, py, pw, ph) — позиция и размер в пикселях.
        """
        if self.handle is None:
            return (0, 0, 0, 0)
        width, height = self.handle.framebuffer_size()
        vx, vy, vw, vh = viewport.rect
        px = int(vx * width)
        py = int(vy * height)
        pw = int(vw * width)
        ph = int(vh * height)
        return (px, py, pw, ph)

    # ----------------------------------------------------------------
    # Picking support (требует FBO пул извне)
    # ----------------------------------------------------------------

    def pick_color_at(
        self,
        x: float,
        y: float,
        fbo_pool: dict,
        viewport: Optional[Viewport] = None,
        buffer_name: str = "color",
    ) -> Optional[Tuple[float, float, float, float]]:
        """
        Читает цвет пикселя из FBO.
        
        Параметры:
            x, y: координаты в пикселях окна (origin сверху-слева).
            fbo_pool: словарь {resource_name -> FramebufferHandle}.
            viewport: viewport для которого читаем (или определяется автоматически).
            buffer_name: имя ресурса в fbo_pool.
        
        Возвращает:
            (r, g, b, a) в [0..1] или None.
        """
        if self.handle is None:
            return None

        if viewport is None:
            viewport = self._viewport_under_cursor(x, y)
            if viewport is None:
                return None

        win_w, win_h = self.handle.window_size()
        fb_w, fb_h = self.handle.framebuffer_size()

        if win_w <= 0 or win_h <= 0 or fb_w <= 0 or fb_h <= 0:
            return None

        px, py, pw, ph = self.viewport_rect_to_pixels(viewport)

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

        r, g, b, a = self.graphics.read_pixel(fb, read_x, read_y)
        self.graphics.bind_framebuffer(self.handle.get_window_framebuffer())
        return (r, g, b, a)

    def pick_entity_at(
        self,
        x: float,
        y: float,
        fbo_pool: dict,
        viewport: Optional[Viewport] = None,
    ) -> Optional[Entity]:
        """
        Читает entity под пикселем из id-карты.
        
        Параметры:
            x, y: координаты в пикселях окна.
            fbo_pool: словарь {resource_name -> FramebufferHandle}.
            viewport: viewport для которого читаем.
        
        Возвращает:
            Entity или None.
        """
        color = self.pick_color_at(x, y, fbo_pool, viewport, buffer_name="id")
        if color is None:
            return None
        r, g, b, a = color
        pid = rgb_to_id(r, g, b)
        if pid == 0:
            return None
        return Entity.lookup_by_pick_id(pid)

    # ----------------------------------------------------------------
    # Event handlers
    # ----------------------------------------------------------------

    def _handle_framebuffer_resize(self, window, width, height):
        pass

    def _handle_mouse_button_game_mode(self, window, button: MouseButton, action: Action, mods):
        if self.handle is None:
            return
        x, y = self.handle.get_cursor_pos()
        viewport = self._viewport_under_cursor(x, y)

        # UI click handling
        if viewport and viewport.canvas:
            if action == Action.PRESS:
                interrupt = viewport.canvas.mouse_down(x, y, self.viewport_rect_to_pixels(viewport))
                if interrupt:
                    return
            elif action == Action.RELEASE:
                interrupt = viewport.canvas.mouse_up(x, y, self.viewport_rect_to_pixels(viewport))
                if interrupt:
                    return

        # 3D scene handling
        if action == Action.PRESS:
            self._active_viewport = viewport
        if action == Action.RELEASE:
            self._last_cursor = None
            if viewport is None:
                viewport = self._active_viewport
            self._active_viewport = None
        if viewport is not None:
            viewport.scene.dispatch_input(viewport, "on_mouse_button", button=button, action=action, mods=mods)

        # Object click handling
        if viewport is not None:
            if action == Action.PRESS and button == MouseButton.LEFT:
                cam = viewport.camera
                if cam is not None:
                    ray = cam.screen_point_to_ray(x, y, viewport_rect=self.viewport_rect_to_pixels(viewport))
                    hit = viewport.scene.raycast(ray)
                    if hit is not None:
                        entity = hit.entity
                        for comp in entity.components:
                            if hasattr(comp, "on_click"):
                                comp.on_click(hit, button)

        self._request_update()

    def _handle_mouse_button_editor_mode(self, window, button: MouseButton, action: Action, mods):
        if self.handle is None:
            return
        x, y = self.handle.get_cursor_pos()
        viewport = self._viewport_under_cursor(x, y)

        # 3D scene handling
        if action == Action.PRESS:
            self._active_viewport = viewport
        if action == Action.RELEASE:
            self._last_cursor = None
            if viewport is None:
                viewport = self._active_viewport
            self._active_viewport = None
        if viewport is not None:
            viewport.scene.dispatch_input(viewport, "on_mouse_button", button=button, action=action, mods=mods)

        if self.on_mouse_button_event:
            self.on_mouse_button_event(button, action, x, y, viewport)

        self._request_update()

    def _handle_mouse_button(self, window, button: MouseButton, action: Action, mods):
        if self._world_mode == "game":
            self._handle_mouse_button_game_mode(window, button, action, mods)
        elif self._world_mode == "editor":
            self._handle_mouse_button_editor_mode(window, button, action, mods)

    def _handle_cursor_pos(self, window, x, y):
        if self.handle is None:
            return

        if self._last_cursor is None:
            dx = dy = 0.0
        else:
            dx = x - self._last_cursor[0]
            dy = y - self._last_cursor[1]

        self._last_cursor = (x, y)
        viewport = self._active_viewport or self._viewport_under_cursor(x, y)

        if viewport and viewport.canvas:
            viewport.canvas.mouse_move(x, y, self.viewport_rect_to_pixels(viewport))

        if viewport is not None:
            viewport.scene.dispatch_input(viewport, "on_mouse_move", x=x, y=y, dx=dx, dy=dy)

        if self.on_mouse_move_event is not None:
            self.on_mouse_move_event(x, y, viewport)

        self._request_update()

    def _handle_scroll(self, window, xoffset, yoffset):
        if self.handle is None:
            return
        x, y = self.handle.get_cursor_pos()
        viewport = self._viewport_under_cursor(x, y) or self._active_viewport
        if viewport is not None:
            viewport.scene.dispatch_input(viewport, "on_scroll", xoffset=xoffset, yoffset=yoffset)

        self._request_update()

    def _handle_key(self, window, key: Key, scancode: int, action: Action, mods):
        if key == Key.ESCAPE and action == Action.PRESS and self.handle is not None:
            self.handle.set_should_close(True)
        viewport = self._active_viewport or (self.viewports[0] if self.viewports else None)
        if viewport is not None:
            viewport.scene.dispatch_input(viewport, "on_key", key=key, scancode=scancode, action=action, mods=mods)

        self._request_update()

    def _viewport_under_cursor(self, x: float, y: float) -> Optional[Viewport]:
        if self.handle is None or not self.viewports:
            return None
        win_w, win_h = self.handle.window_size()
        if win_w == 0 or win_h == 0:
            return None
        nx = x / win_w
        ny = 1.0 - (y / win_h)

        for viewport in self.viewports:
            vx, vy, vw, vh = viewport.rect
            if vx <= nx <= vx + vw and vy <= ny <= vy + vh:
                return viewport
        return None

    def _request_update(self):
        if self.handle is not None:
            self.handle.request_update()


# Backwards compatibility
GLWindow = Window
