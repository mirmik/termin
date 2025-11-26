<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/window.py</title>
</head>
<body>
<pre><code>
&quot;&quot;&quot;Window abstraction delegating platform details to a backend.&quot;&quot;&quot;

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
from .picking import rgb_to_id
from .components import MeshRenderer
from .framegraph import FrameGraph, FrameContext, RenderFramePass, IdPass
from .postprocess import PostProcessPass
from .posteffects.highlight import HighlightEffect
from .posteffects.gray import GrayscaleEffect

class Window:
    &quot;&quot;&quot;Manages a platform window and a set of viewports.&quot;&quot;&quot;

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

        self.on_mouse_button_event : Optional[callable(MouseButton, MouseAction, x, y, Viewport)] = None
        self.on_mouse_move_event = None  # callable(x: float, y: float, viewport: Optional[Viewport])
        self.after_render_handler = None  # type: Optional[Callable[[&quot;Window&quot;], None]]

        self._world_mode = &quot;game&quot;  # or &quot;editor&quot;
 
        # picking support
        self.selection_handler = None    # редактор подпишется сюда
        self._pick_requests = {}         # viewport -&gt; (mouse_x, mouse_y)
        self._pick_id_counter = 1
        self._pick_entity_by_id = {}
        self._pick_id_by_entity = {}

    def set_selection_handler(self, handler):
        self.selection_handler = handler

    def set_world_mode(self, mode: str):
        self._world_mode = mode

    def _get_pick_id_for_entity(self, entity):
        pid = self._pick_id_by_entity.get(entity)
        if pid is not None:
            return pid
        pid = self._pick_id_counter
        self._pick_id_counter += 1
        self._pick_id_by_entity[entity] = pid
        self._pick_entity_by_id[pid] = entity
        return pid     

    def close(self):
        if self.handle:
            self.handle.close()
            self.handle = None

    @property
    def should_close(self) -&gt; bool:
        return self.handle is None or self.handle.should_close()

    def make_current(self):
        if self.handle is not None:
            self.handle.make_current()

    def add_viewport(self, scene: Scene, camera: CameraComponent, rect: Tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0), canvas: Optional[Canvas] = None) -&gt; Viewport:
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

            # viewport.frame_passes.append(ColorPass(input_res=&quot;empty&quot;,    output_res=&quot;color&quot;, pass_name=&quot;Color&quot;))
            # viewport.frame_passes.append(IdPass   (input_res=&quot;empty_id&quot;, output_res=&quot;id&quot;,    pass_name=&quot;Id&quot;))
            # # viewport.frame_passes.append(PostProcessPass(
            # #     effects=[HighlightEffect(lambda: editor.selected_entity_id)],
            # #     input_res=&quot;color&quot;,
            # #     output_res=&quot;color_pp&quot;,
            # #     pass_name=&quot;PostFX&quot;,
            # # ))
            # viewport.frame_passes.append(PostProcessPass(
            #     effects=[GrayscaleEffect()],
            #     input_res=&quot;color&quot;,
            #     output_res=&quot;color_pp&quot;,
            #     pass_name=&quot;PostFX&quot;,
            # ))
            
            # viewport.frame_passes.append(CanvasPass(src=&quot;color_pp&quot;, dst=&quot;color+ui&quot;, pass_name=&quot;Canvas&quot;))
            # viewport.frame_passes.append(PresentToScreenPass(input_res=&quot;color+ui&quot;, pass_name=&quot;Present&quot;))

            # viewport.frame_passes.append(PresentToScreenPass(input_res=&quot;id&quot;, pass_name=&quot;Present&quot;))
            # viewport.frame_passes.append(IdPass(input_res=&quot;empty_id&quot;, output_res=&quot;id&quot;, pass_name=&quot;IdPass&quot;))

        return viewport

    def update(self, dt: float):
        # Reserved for future per-window updates.
        return

    def render(self):
        self._render_core(from_backend=False)

    def viewport_rect_to_pixels(self, viewport: Viewport) -&gt; Tuple[int, int, int, int]:
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
    from termin.visualization.entity import Entity

    def pick_entity_at(self, x: float, y: float, viewport: Viewport = None) -&gt; Optional[Entity]:
        &quot;&quot;&quot;
        Вернёт entity под пикселем (x, y) в координатах виджета (origin сверху-слева),
        используя id-карту, нарисованную IdPass в FBO с ключом 'id'.
        &quot;&quot;&quot;
        if self.handle is None:
            return None

        # Определяем вьюпорт, если не передали явно
        if viewport is None:
            viewport = self._viewport_under_cursor(x, y)
            if viewport is None:
                return None

        win_w, win_h = self.handle.window_size()       # логические пиксели
        fb_w, fb_h = self.handle.framebuffer_size()    # физические пиксели (GL)

        if win_w &lt;= 0 or win_h &lt;= 0 or fb_w &lt;= 0 or fb_h &lt;= 0:
            return None

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


        if vx &lt; 0 or vy &lt; 0 or vx &gt;= pw or vy &gt;= ph:
            return None

        # --- 4) перевод в координаты FBO (origin снизу-слева) ---
        read_x = int(vx)
        read_y = int(ph - vy - 1)   # инверсия Y, как в старом _do_pick_pass

        # Берём FBO с id-картой
        fbo_pool = getattr(viewport, &quot;_fbo_pool&quot;, None)
        if not fbo_pool:
            return None

        fb_id = fbo_pool.get(&quot;id&quot;)
        if fb_id is None:
            return None


        r, g, b, a = self.graphics.read_pixel(fb_id, read_x, read_y)
        self.handle.bind_window_framebuffer()

        pid = rgb_to_id(r, g, b)

        if pid == 0:
            return None

        entity = self._pick_entity_by_id.get(pid)

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
            viewport.scene.dispatch_input(viewport, &quot;on_mouse_button&quot;, button=button, action=action, mods=mods)
            
        # Теперь обработка кликов по объектам сцены
        if viewport is not None:
            if action == Action.PRESS and button == MouseButton.LEFT:
                cam = viewport.camera
                if cam is not None:
                    ray = cam.screen_point_to_ray(x, y, viewport_rect=self.viewport_rect_to_pixels(viewport))   # функция построения Ray3
                    hit = viewport.scene.raycast(ray)
                    print(&quot;Raycast hit:&quot;, hit)  # --- DEBUG ---
                    if hit is not None:
                        # Диспатчим on_click в компоненты
                        entity = hit.entity
                        for comp in entity.components:
                            if hasattr(comp, &quot;on_click&quot;):  # или isinstance(comp, Clickable)
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
            #print(&quot;Dispatching mouse button to scene&quot;)  # --- DEBUG ---
            viewport.scene.dispatch_input(viewport, &quot;on_mouse_button&quot;, button=button, action=action, mods=mods)  

        if self.on_mouse_button_event:
            self.on_mouse_button_event(button, action, x, y, viewport)   

        self._request_update()

    def _handle_mouse_button(self, window, button: MouseButton, action: Action, mods):
        if self._world_mode == &quot;game&quot;:
            self._handle_mouse_button_game_mode(window, button, action, mods)
            return

        elif self._world_mode == &quot;editor&quot;:
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
            viewport.scene.dispatch_input(viewport, &quot;on_mouse_move&quot;, x=x, y=y, dx=dx, dy=dy)

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
            viewport.scene.dispatch_input(viewport, &quot;on_scroll&quot;, xoffset=xoffset, yoffset=yoffset)

        self._request_update()

    def _handle_key(self, window, key: Key, scancode: int, action: Action, mods):
        if key == Key.ESCAPE and action == Action.PRESS and self.handle is not None:
            self.handle.set_should_close(True)
        viewport = self._active_viewport or (self.viewports[0] if self.viewports else None)
        if viewport is not None:
            viewport.scene.dispatch_input(viewport, &quot;on_key&quot;, key=key, scancode=scancode, action=action, mods=mods)

        self._request_update()

    def _viewport_under_cursor(self, x: float, y: float) -&gt; Optional[Viewport]:
        if self.handle is None or not self.viewports:
            return None
        win_w, win_h = self.handle.window_size()
        if win_w == 0 or win_h == 0:
            return None
        nx = x / win_w
        ny = 1.0 - (y / win_h)
        for viewport in self.viewports:
            vx, vy, vw, vh = viewport.rect
            if vx &lt;= nx &lt;= vx + vw and vy &lt;= ny &lt;= vy + vh:
                return viewport
        return None

    def get_viewport_fbo(self, viewport, key, size):
        d = viewport.__dict__.setdefault(&quot;_fbo_pool&quot;, {})
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

            # Обновляем аспект камеры
            viewport.camera.set_aspect(pw / float(max(1, ph)))

            # Берём список пассов, который кто-то заранее повесил на viewport
            frame_passes = viewport.frame_passes
            if not frame_passes:
                # Нечего рендерить — пропускаем
                continue

            # Контекст для пассов
            ctx = FrameContext(
                window=self,
                viewport=viewport,
                rect=(px, py, pw, ph),
                size=(pw, ph),
                context_key=context_key,
                graphics=self.graphics,
            )

            # Строим и исполняем граф
            graph = FrameGraph(frame_passes)
            schedule = graph.build_schedule()

            for p in schedule:
                p.execute(ctx)

        if self.after_render_handler is not None:
            self.after_render_handler(self)

        if not from_backend:
            self.handle.swap_buffers()

    def _request_update(self):
        if self.handle is not None:
            self.handle.request_update()

    # def _do_pick_pass(self, viewport, px, py, pw, ph, mouse_x, mouse_y, context_key):
    #     print(f&quot;Doing pick pass at mouse ({mouse_x}, {mouse_y}) in viewport rect px={px},py={py},pw={pw},ph={ph}&quot;)  # --- DEBUG ---

    #     # 1) FBO для picking
    #     fb_pick = self.get_viewport_fbo(viewport, &quot;PICK&quot;, (pw, ph))
        
    #     print(&quot;Picking FBO:&quot;, fb_pick._fbo)  # --- DEBUG ---
    #     self.graphics.bind_framebuffer(fb_pick)
    #     self.graphics.set_viewport(0, 0, pw, ph)
    #     self.graphics.clear_color_depth((0.0, 0.0, 0.0, 0.0))

    #     # 2) карта entity -&gt; id для этой сцены
    #     pick_ids = {}
    #     for ent in viewport.scene.entities:
    #         if not ent.is_pickable():
    #             continue

    #         mr = ent.get_component(MeshRenderer)
    #         if mr is None:
    #             continue

    #         # можешь фильтровать по наличию MeshRenderer
    #         pick_ids[ent] = self._get_pick_id_for_entity(ent)

    #     # 3) рендерим специальным пассом
    #     self.renderer.render_viewport_pick(
    #         viewport.scene,
    #         viewport.camera,
    #         (0, 0, pw, ph),
    #         context_key,
    #         pick_ids,
    #     )

    #     # 4) вычисляем координаты пикселя относительно FBO
    #     win_w, win_h = self.handle.window_size()
    #     if win_w == 0 or win_h == 0:
    #         return

    #     vx = mouse_x - px
    #     vy = mouse_y - py
    #     if vx &lt; 0 or vy &lt; 0 or vx &gt;= pw or vy &gt;= ph:
    #         return

    #     read_x = int(vx)
    #     read_y = ph - int(vy) - 1  # инверсия по Y

    #     print(&quot;Reading pixel at FBO coords:&quot;, read_x, read_y)  # --- DEBUG ---

    #     r, g, b, a = self.graphics.read_pixel(fb_pick, read_x, read_y)
    #     print(&quot;Picked color RGBA:&quot;, r, g, b, a)  # --- DEBUG ---
    #     pid = rgb_to_id(r, g, b)
    #     print(f&quot;Picked ID: {pid}&quot;)  # --- DEBUG ---
    #     if pid == 0:
    #         return

    #     entity = self._pick_entity_by_id.get(pid)
    #     if entity is not None and self.selection_handler is not None:
    #         self.selection_handler(entity)

    #     # вернёмся к обычному framebuffer'у
    #     self.graphics.bind_framebuffer(None)



# Backwards compatibility
GLWindow = Window

</code></pre>
</body>
</html>
