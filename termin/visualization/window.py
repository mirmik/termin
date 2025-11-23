"""Window abstraction delegating platform details to a backend."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from .camera import CameraComponent
from .renderer import Renderer
from .scene import Scene
from .backends.base import (
    Action,
    GraphicsBackend,
    Key,
    MouseButton,
    WindowBackend,
    BackendWindow,
)
from .viewport import Viewport
from .ui.canvas import Canvas

class Window:
    """Manages a platform window and a set of viewports."""

    def __init__(self, width: int, height: int, title: str, renderer: Renderer, graphics: GraphicsBackend, window_backend: WindowBackend, share=None, **backend_kwargs):
        self.renderer = renderer
        self.graphics = graphics
        share_handle = None
        if isinstance(share, Window):
            share_handle = share.handle
        elif isinstance(share, BackendWindow):
            share_handle = share

        self.window_backend = window_backend
        self.handle: BackendWindow = self.window_backend.create_window(width, height, title, share=share_handle, **backend_kwargs)

        self.viewports: List[Viewport] = []
        self._active_viewport: Optional[Viewport] = None
        self._last_cursor: Optional[Tuple[float, float]] = None

        self.handle.set_user_pointer(self)
        self.handle.set_framebuffer_size_callback(self._handle_framebuffer_resize)
        self.handle.set_cursor_pos_callback(self._handle_cursor_pos)
        self.handle.set_scroll_callback(self._handle_scroll)
        self.handle.set_mouse_button_callback(self._handle_mouse_button)
        self.handle.set_key_callback(self._handle_key)

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

    def add_viewport(self, scene: Scene, camera: CameraComponent, rect: Tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0), canvas: Optional[Canvas] = None) -> Viewport:
        if not self.handle.drives_render():
            self.make_current()
        scene.ensure_ready(self.graphics)
        viewport = Viewport(scene=scene, camera=camera, rect=rect, canvas=canvas, window=self)
        camera.viewport = viewport
        self.viewports.append(viewport)
        return viewport

    def update(self, dt: float):
        # Reserved for future per-window updates.
        return

    def render(self):
        self._render_core(from_backend=False)

    def viewport_rect_to_pixels(self, viewport: Viewport) -> Tuple[int, int, int, int]:
        if self.handle is None:
            return (0, 0, 0, 0)
        width, height = self.handle.framebuffer_size()
        vx, vy, vw, vh = viewport.rect
        px = vx * width
        py = vy * height
        pw = vw * width
        ph = vh * height
        return px, py, pw, ph
        

    # Event handlers -----------------------------------------------------

    def _handle_framebuffer_resize(self, window, width, height):
        return

    def _handle_mouse_button(self, window, button: MouseButton, action: Action, mods):
        print(f"Mouse button event: button={button}, action={action}, mods={mods}")  # --- DEBUG ---
        if self.handle is None:
            return
        x, y = self.handle.get_cursor_pos()
        viewport = self._viewport_under_cursor(x, y)

        # ---- UI click handling ----
        # if viewport and viewport.canvas:
        #     ui_hit = viewport.canvas.hit_test(x, y, self.viewport_rect_to_pixels(viewport))
        #     print("UI hit test result:", ui_hit)
        #     if ui_hit:
        #         if action == Action.PRESS and hasattr(ui_hit, "on_click") and ui_hit.on_click:
        #             ui_hit.on_click()
        #         # UI перехватывает клик — дальше в 3D не лезем
        #         print("UI element clicked:", ui_hit)
        #         return

        # ---- UI click handling 2 ----
        if viewport and viewport.canvas:
            if action == Action.PRESS:
                interrupt = viewport.canvas.mouse_down(x, y, self.viewport_rect_to_pixels(viewport))
                if interrupt:
                    return
            elif action == Action.RELEASE:
                interrupt = viewport.canvas.mouse_up(x, y, self.viewport_rect_to_pixels(viewport))
                if interrupt:
                    return

        # Обработка 3D сцены (сперва глобальная)
        if action == Action.PRESS:
            self._active_viewport = viewport
        if action == Action.RELEASE:
            self._last_cursor = None
            if viewport is None:
                viewport = self._active_viewport
            self._active_viewport = None
        if viewport is not None:
            viewport.scene.dispatch_input(viewport, "on_mouse_button", button=button, action=action, mods=mods)
            
        # Теперь обработка кликов по объектам сцены
        if viewport is not None:
            if action == Action.PRESS and button == MouseButton.LEFT:
                cam = viewport.camera
                if cam is not None:
                    ray = cam.screen_point_to_ray(x, y, viewport_rect=self.viewport_rect_to_pixels(viewport))   # функция построения Ray3
                    hit = viewport.scene.raycast(ray)
                    print("Raycast hit:", hit)  # --- DEBUG ---
                    if hit is not None:
                        # Диспатчим on_click в компоненты
                        entity = hit.entity
                        for comp in entity.components:
                            if hasattr(comp, "on_click"):  # или isinstance(comp, Clickable)
                                comp.on_click(hit, button)

        self._request_update()


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

    def get_viewport_fbo(self, viewport, key, size):
        d = viewport.__dict__.setdefault("_fbo_pool", {})
        fb = d.get(key)
        if fb is None:
            fb = self.graphics.create_framebuffer(size)
            d[key] = fb
        else:
            fb.resize(size)
        return fb

    def _render_core(self, from_backend: bool):
        if self.handle is None:
            return

        self.graphics.ensure_ready()
        
        if not from_backend:
            self.make_current()

        context_key = id(self)
        width, height = self.handle.framebuffer_size()

        for viewport in self.viewports:
            vx, vy, vw, vh = viewport.rect
            px = int(vx * width)
            py = int(vy * height)
            pw = max(1, int(vw * width))
            ph = max(1, int(vh * height))

            viewport.camera.set_aspect(pw / float(max(1, ph)))
            effects = viewport.postprocess  # список эффектов, может быть пустой

            # --- вариант без постпроцесса ---
            if not effects:
                # рендерим прямо в экран
                self.graphics.enable_scissor(px, py, pw, ph)
                self.graphics.set_viewport(px, py, pw, ph)

                self.graphics.clear_color_depth(viewport.scene.background_color)
                self.graphics.disable_scissor()

                self.renderer.render_viewport(
                    viewport.scene, viewport.camera,
                    (px, py, pw, ph),
                    context_key
                )

                if viewport.canvas:
                    viewport.canvas.render(self.graphics, context_key, (px, py, pw, ph))

                continue

            # --- есть постпроцесс ---
            # 1) рендерим сцену в FBO_A
            fb_a = self.get_viewport_fbo(viewport, "A", (pw, ph))
            self.graphics.bind_framebuffer(fb_a)
            self.graphics.set_viewport(0, 0, pw, ph)
            self.graphics.clear_color_depth(viewport.scene.background_color)

            self.renderer.render_viewport(
                viewport.scene, viewport.camera,
                (0, 0, pw, ph),
                context_key
            )

            # 2) цепочка эффектов
            fb_in = fb_a
            fb_out = self.get_viewport_fbo(viewport, "B", (pw, ph))

            # все эффекты кроме последнего пишут в ping-pong
            for effect in effects[:-1]:
                self.graphics.bind_framebuffer(fb_out)
                self.graphics.set_viewport(0, 0, pw, ph)

                effect.draw(self.graphics, context_key, fb_in.color_texture(), (pw, ph))

                fb_in, fb_out = fb_out, fb_in

            # 3) последний эффект пишет прямо в экран
            last = effects[-1]
            self.graphics.bind_framebuffer(None)
            self.graphics.set_viewport(px, py, pw, ph)

            last.draw(self.graphics, context_key, fb_in.color_texture(), (pw, ph))

            # 4) UI поверх
            if viewport.canvas:
                viewport.canvas.render(self.graphics, context_key, (px, py, pw, ph))

        # Для окон, которые не рендерятся из бэкенда, свапаем буферы здесь
        if not from_backend:
            self.handle.swap_buffers()

    def _request_update(self):
        if self.handle is not None:
            self.handle.request_update()




# Backwards compatibility
GLWindow = Window
