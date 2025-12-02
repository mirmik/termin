"""Window abstraction delegating platform details to a backend."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

from termin.visualization.core.camera import CameraComponent
from termin.visualization.render.renderer import Renderer
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
from termin.visualization.render.components import MeshRenderer
from termin.visualization.render.framegraph import FrameGraph, RenderFramePass, IdPass, RenderPipeline
from termin.visualization.render.postprocess import PostProcessPass
from termin.visualization.render.posteffects.highlight import HighlightEffect
from termin.visualization.render.posteffects.gray import GrayscaleEffect

class Window:
    """Manages a platform window and a set of viewports."""

    def __init__(self, width: int, height: int, title: str, renderer: Renderer, graphics: GraphicsBackend, window_backend: WindowBackend, share=None, **backend_kwargs):
        self.renderer = renderer
        self.graphics = graphics
        self.generate_default_pipeline = True
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

        self.on_mouse_button_event : Optional[
            Callable[[MouseButton, Action, float, float, Optional[Viewport]], None]
        ] = None
        self.on_mouse_move_event = None  # callable(x: float, y: float, viewport: Optional[Viewport])
        self.after_render_handler = None  # type: Optional[Callable[["Window"], None]]

        self._world_mode = "game"  # or "editor"
 
        # picking support
        self.selection_handler = None    # редактор подпишется сюда
        self._pick_requests = {}         # viewport -> (mouse_x, mouse_y)

    def set_selection_handler(self, handler):
        self.selection_handler = handler

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

    def add_viewport(self, scene: Scene, camera: CameraComponent, rect: Tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0), canvas: Optional[Canvas] = None) -> Viewport:
        if not self.handle.drives_render():
            self.make_current()
        scene.ensure_ready(self.graphics)
        viewport = Viewport(scene=scene, camera=camera, rect=rect, canvas=canvas, window=self)
        camera.viewport = viewport
        self.viewports.append(viewport)

        if self.generate_default_pipeline:
            # собираем дефолтный пайплайн
            pipeline = viewport.make_default_pipeline()
            viewport.set_render_pipeline(pipeline)

        # if viewport.frame_passes == []:
        #     # Если никто не добавил пассы, добавим дефолтный main-pass + present
        #     from .framegraph import ColorPass, PresentToScreenPass, CanvasPass

            # viewport.frame_passes.append(ColorPass(input_res="empty",    output_res="color", pass_name="Color"))
            # viewport.frame_passes.append(IdPass   (input_res="empty_id", output_res="id",    pass_name="Id"))
            # # viewport.frame_passes.append(PostProcessPass(
            # #     effects=[HighlightEffect(lambda: editor.selected_entity_id)],
            # #     input_res="color",
            # #     output_res="color_pp",
            # #     pass_name="PostFX",
            # # ))
            # viewport.frame_passes.append(PostProcessPass(
            #     effects=[GrayscaleEffect()],
            #     input_res="color",
            #     output_res="color_pp",
            #     pass_name="PostFX",
            # ))
            
            # viewport.frame_passes.append(CanvasPass(src="color_pp", dst="color+ui", pass_name="Canvas"))
            # viewport.frame_passes.append(PresentToScreenPass(input_res="color+ui", pass_name="Present"))

            # viewport.frame_passes.append(PresentToScreenPass(input_res="id", pass_name="Present"))
            # viewport.frame_passes.append(IdPass(input_res="empty_id", output_res="id", pass_name="IdPass"))

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


    from typing import Optional
    from termin.visualization.core.entity import Entity

    def pick_color_at(self, x: float, y: float, viewport: Viewport = None, buffer_name="color") -> Optional[Tuple[int, int, int, int]]:
        """
        Вернёт (r,g,b,a) в [0,1] под пикселем (x, y) в координатах виджета (origin сверху-слева),
        используя цветовую карту, нарисованную ColorPass в FBO с ключом 'color'.
        """
        if self.handle is None:
            raise RuntimeError("Window handle is not available")

        # Определяем вьюпорт, если не передали явно
        if viewport is None:
            viewport = self._viewport_under_cursor(x, y)
            if viewport is None:
                raise RuntimeError("No viewport under cursor for picking")

        win_w, win_h = self.handle.window_size()       # логические пиксели
        fb_w, fb_h = self.handle.framebuffer_size()    # физические пиксели (GL)

        if win_w <= 0 or win_h <= 0 or fb_w <= 0 or fb_h <= 0:
            raise RuntimeError("Invalid window or framebuffer size")

        # --- 1) координаты viewport'а в физических пикселях (как при рендере) ---
        px, py, pw, ph = self.viewport_rect_to_pixels(viewport)
        # viewport_rect_to_pixels уже использует framebuffer_size()


        # --- 2) переводим координаты мыши из логических в физические ---
        sx = fb_w / float(win_w)
        sy = fb_h / float(win_h)

        x_phys = x * sx
        y_phys = y * sy

        # --- 3) локальные координаты внутри viewport'а ---
        vx = x_phys - px
        vy = y_phys - py


        if vx < 0 or vy < 0 or vx >= pw or vy >= ph:
            return None

        # --- 4) перевод в координаты FBO (origin снизу-слева) ---
        read_x = int(vx)
        read_y = int(ph - vy - 1)   # инверсия Y, как в старом _do_pick_pass

        # Берём FBO с цветовой картой
        fbo_pool = viewport.fbos

        fb_color = fbo_pool.get(buffer_name)
        if fb_color is None:
            raise KeyError(f"No FBO with key {buffer_name!r} found in fbo_pool")


        r, g, b, a = self.graphics.read_pixel(fb_color, read_x, read_y)
        self.graphics.bind_framebuffer(self.handle.get_window_framebuffer())
        return (r, g, b, a)

    def pick_entity_at(self, x: float, y: float, viewport: Viewport = None) -> Optional[Entity]:
        """
        Вернёт entity под пикселем (x, y) в координатах виджета (origin сверху-слева),
        используя id-карту, нарисованную IdPass в FBO с ключом 'id'.
        """
        if self.handle is None:
            return None

        color = self.pick_color_at(x, y, viewport=viewport, buffer_name="id")
        if color is None:
            return None
        r, g, b, a = color
        
        pid = rgb_to_id(r, g, b)

        if pid == 0:
            return None

        entity = Entity.lookup_by_pick_id(pid)

        return entity


    def _handle_mouse_button_game_mode(self, window, button: MouseButton, action: Action, mods):
        if self.handle is None:
            return
        x, y = self.handle.get_cursor_pos()
        viewport = self._viewport_under_cursor(x, y)

        # ---- UI click handling ----
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
                    if hit is not None:
                        # Диспатчим on_click в компоненты
                        entity = hit.entity
                        for comp in entity.components:
                            if hasattr(comp, "on_click"):  # или isinstance(comp, Clickable)
                                comp.on_click(hit, button)

        self._request_update()

    def _handle_mouse_button_editor_mode(self, window, button: MouseButton, action: Action, mods):
        if self.handle is None:
            return
        x, y = self.handle.get_cursor_pos()
        viewport = self._viewport_under_cursor(x, y)

        if viewport is not None:
            if action == Action.PRESS and button == MouseButton.LEFT:
                # запоминаем, где кликнули, для этого viewport
                self._pick_requests[id(viewport)] = (x, y)   

        # Обработка 3D сцены
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
            return

        elif self._world_mode == "editor":
            self._handle_mouse_button_editor_mode(window, button, action, mods)
            return

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

        # пробрасываем инфу наверх (редактору), без знания про idmap и hover
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

    def get_viewport_fbo(self, viewport, key, size):
        fb = viewport.fbos.get(key)
        if fb is None:
            fb = self.graphics.create_framebuffer(size)
            viewport.fbos[key] = fb
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

            # Обновляем аспект камеры
            viewport.camera.set_aspect(pw / float(max(1, ph)))

            # Берём pipeline, который кто-то заранее повесил на viewport
            pipeline = viewport.pipeline
            if pipeline is None:
                continue

            frame_passes = pipeline.passes
            if not frame_passes:
                continue

            # Динамические пассы (например, BlitPass) могут обновлять reads перед построением графа
            for p in frame_passes:
                if isinstance(p, RenderFramePass):
                    p.required_resources()

            # Строим граф и получаем порядок
            graph = FrameGraph(frame_passes)
            schedule = graph.build_schedule()

            # --- 1) Предварительно создаём FBO по группам алиасов ---
            alias_groups = graph.fbo_alias_groups()

            # общий пул FBO у вьюпорта, чтобы pick и прочее видели те же объекты
            fbos = viewport.fbos
            #if display_fbo is not None:
            #    fbos["DISPLAY"] = display_fbo
            display_fbo = self.handle.get_window_framebuffer()
            fbos["DISPLAY"] = display_fbo

            # если решение графа поменялось, fbo обновятся
            for canon, names in alias_groups.items():
                if canon == "DISPLAY":
                    for name in names:
                        fbos[name] = display_fbo
                    continue

                fb = self.get_viewport_fbo(viewport, canon, (pw, ph))
                for name in names:
                    fbos[name] = fb

            # --- 2) Очистка ресурсов перед рендерингом ---
            for clear_spec in pipeline.clear_specs:
                fb = fbos.get(clear_spec.resource)
                if fb is None:
                    continue
                self.graphics.bind_framebuffer(fb)
                self.graphics.set_viewport(0, 0, pw, ph)
                if clear_spec.color is not None and clear_spec.depth is not None:
                    self.graphics.clear_color_depth(clear_spec.color)
                elif clear_spec.color is not None:
                    self.graphics.clear_color(clear_spec.color)
                elif clear_spec.depth is not None:
                    self.graphics.clear_depth(clear_spec.depth)

            # --- 3) Выполняем пассы с явными зависимостями ---
            scene = viewport.scene
            lights = scene.build_lights()
            for p in schedule:
                pass_reads = {name: fbos.get(name) for name in p.reads}
                pass_writes = {name: fbos.get(name) for name in p.writes}

                p.execute(
                    self.graphics,
                    reads_fbos=pass_reads,
                    writes_fbos=pass_writes,
                    rect=(px, py, pw, ph),
                    scene=scene,
                    camera=viewport.camera,
                    renderer=self.renderer,
                    context_key=context_key,
                    lights=lights,
                    canvas=viewport.canvas,
                )

        if self.after_render_handler is not None:
            self.after_render_handler(self)

        if not from_backend:
            self.handle.swap_buffers()

    def _request_update(self):
        if self.handle is not None:
            self.handle.request_update()


# Backwards compatibility
GLWindow = Window
