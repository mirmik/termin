<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/window.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;Window abstraction delegating platform details to a backend.&quot;&quot;&quot;<br>
<br>
from __future__ import annotations<br>
<br>
from dataclasses import dataclass<br>
from typing import List, Optional, Tuple<br>
<br>
from .camera import CameraComponent<br>
from .renderer import Renderer<br>
from .scene import Scene<br>
from .backends.base import (<br>
    Action,<br>
    GraphicsBackend,<br>
    Key,<br>
    MouseButton,<br>
    WindowBackend,<br>
    BackendWindow,<br>
)<br>
from .viewport import Viewport<br>
from .ui.canvas import Canvas<br>
from .picking import rgb_to_id<br>
from .components import MeshRenderer<br>
from .framegraph import FrameGraph, FrameContext, RenderFramePass, IdPass<br>
from .postprocess import PostProcessPass<br>
from .posteffects.highlight import HighlightEffect<br>
from .posteffects.gray import GrayscaleEffect<br>
<br>
class Window:<br>
    &quot;&quot;&quot;Manages a platform window and a set of viewports.&quot;&quot;&quot;<br>
<br>
    def __init__(self, width: int, height: int, title: str, renderer: Renderer, graphics: GraphicsBackend, window_backend: WindowBackend, share=None, **backend_kwargs):<br>
        self.renderer = renderer<br>
        self.graphics = graphics<br>
        self.generate_default_pipeline = True<br>
        share_handle = None<br>
        if isinstance(share, Window):<br>
            share_handle = share.handle<br>
        elif isinstance(share, BackendWindow):<br>
            share_handle = share<br>
<br>
        self.window_backend = window_backend<br>
        self.handle: BackendWindow = self.window_backend.create_window(width, height, title, share=share_handle, **backend_kwargs)<br>
<br>
        self.viewports: List[Viewport] = []<br>
        self._active_viewport: Optional[Viewport] = None<br>
        self._last_cursor: Optional[Tuple[float, float]] = None<br>
<br>
        self.handle.set_user_pointer(self)<br>
        self.handle.set_framebuffer_size_callback(self._handle_framebuffer_resize)<br>
        self.handle.set_cursor_pos_callback(self._handle_cursor_pos)<br>
        self.handle.set_scroll_callback(self._handle_scroll)<br>
        self.handle.set_mouse_button_callback(self._handle_mouse_button)<br>
        self.handle.set_key_callback(self._handle_key)<br>
<br>
        self.on_mouse_button_event : Optional[callable(MouseButton, MouseAction, x, y, Viewport)] = None<br>
        self.on_mouse_move_event = None  # callable(x: float, y: float, viewport: Optional[Viewport])<br>
        self.after_render_handler = None  # type: Optional[Callable[[&quot;Window&quot;], None]]<br>
<br>
        self._world_mode = &quot;game&quot;  # or &quot;editor&quot;<br>
 <br>
        # picking support<br>
        self.selection_handler = None    # редактор подпишется сюда<br>
        self._pick_requests = {}         # viewport -&gt; (mouse_x, mouse_y)<br>
        self._pick_id_counter = 1<br>
        self._pick_entity_by_id = {}<br>
        self._pick_id_by_entity = {}<br>
<br>
    def set_selection_handler(self, handler):<br>
        self.selection_handler = handler<br>
<br>
    def set_world_mode(self, mode: str):<br>
        self._world_mode = mode<br>
<br>
    def _get_pick_id_for_entity(self, entity):<br>
        pid = self._pick_id_by_entity.get(entity)<br>
        if pid is not None:<br>
            return pid<br>
        pid = self._pick_id_counter<br>
        self._pick_id_counter += 1<br>
        self._pick_id_by_entity[entity] = pid<br>
        self._pick_entity_by_id[pid] = entity<br>
        return pid     <br>
<br>
    def close(self):<br>
        if self.handle:<br>
            self.handle.close()<br>
            self.handle = None<br>
<br>
    @property<br>
    def should_close(self) -&gt; bool:<br>
        return self.handle is None or self.handle.should_close()<br>
<br>
    def make_current(self):<br>
        if self.handle is not None:<br>
            self.handle.make_current()<br>
<br>
    def add_viewport(self, scene: Scene, camera: CameraComponent, rect: Tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0), canvas: Optional[Canvas] = None) -&gt; Viewport:<br>
        if not self.handle.drives_render():<br>
            self.make_current()<br>
        scene.ensure_ready(self.graphics)<br>
        viewport = Viewport(scene=scene, camera=camera, rect=rect, canvas=canvas, window=self)<br>
        camera.viewport = viewport<br>
        self.viewports.append(viewport)<br>
<br>
        if self.generate_default_pipeline:<br>
            # собираем дефолтный пайплайн<br>
            pipeline = viewport.make_default_pipeline()<br>
            viewport.set_render_pipeline(pipeline)<br>
<br>
        # if viewport.frame_passes == []:<br>
        #     # Если никто не добавил пассы, добавим дефолтный main-pass + present<br>
        #     from .framegraph import ColorPass, PresentToScreenPass, CanvasPass<br>
<br>
            # viewport.frame_passes.append(ColorPass(input_res=&quot;empty&quot;,    output_res=&quot;color&quot;, pass_name=&quot;Color&quot;))<br>
            # viewport.frame_passes.append(IdPass   (input_res=&quot;empty_id&quot;, output_res=&quot;id&quot;,    pass_name=&quot;Id&quot;))<br>
            # # viewport.frame_passes.append(PostProcessPass(<br>
            # #     effects=[HighlightEffect(lambda: editor.selected_entity_id)],<br>
            # #     input_res=&quot;color&quot;,<br>
            # #     output_res=&quot;color_pp&quot;,<br>
            # #     pass_name=&quot;PostFX&quot;,<br>
            # # ))<br>
            # viewport.frame_passes.append(PostProcessPass(<br>
            #     effects=[GrayscaleEffect()],<br>
            #     input_res=&quot;color&quot;,<br>
            #     output_res=&quot;color_pp&quot;,<br>
            #     pass_name=&quot;PostFX&quot;,<br>
            # ))<br>
            <br>
            # viewport.frame_passes.append(CanvasPass(src=&quot;color_pp&quot;, dst=&quot;color+ui&quot;, pass_name=&quot;Canvas&quot;))<br>
            # viewport.frame_passes.append(PresentToScreenPass(input_res=&quot;color+ui&quot;, pass_name=&quot;Present&quot;))<br>
<br>
            # viewport.frame_passes.append(PresentToScreenPass(input_res=&quot;id&quot;, pass_name=&quot;Present&quot;))<br>
            # viewport.frame_passes.append(IdPass(input_res=&quot;empty_id&quot;, output_res=&quot;id&quot;, pass_name=&quot;IdPass&quot;))<br>
<br>
        return viewport<br>
<br>
    def update(self, dt: float):<br>
        # Reserved for future per-window updates.<br>
        return<br>
<br>
    def render(self):<br>
        self._render_core(from_backend=False)<br>
<br>
    def viewport_rect_to_pixels(self, viewport: Viewport) -&gt; Tuple[int, int, int, int]:<br>
        if self.handle is None:<br>
            return (0, 0, 0, 0)<br>
        width, height = self.handle.framebuffer_size()<br>
        vx, vy, vw, vh = viewport.rect<br>
        px = vx * width<br>
        py = vy * height<br>
        pw = vw * width<br>
        ph = vh * height<br>
        return px, py, pw, ph<br>
        <br>
<br>
    # Event handlers -----------------------------------------------------<br>
<br>
    def _handle_framebuffer_resize(self, window, width, height):<br>
        return<br>
<br>
<br>
    from typing import Optional<br>
    from termin.visualization.entity import Entity<br>
<br>
    def pick_entity_at(self, x: float, y: float, viewport: Viewport = None) -&gt; Optional[Entity]:<br>
        &quot;&quot;&quot;<br>
        Вернёт entity под пикселем (x, y) в координатах виджета (origin сверху-слева),<br>
        используя id-карту, нарисованную IdPass в FBO с ключом 'id'.<br>
        &quot;&quot;&quot;<br>
        if self.handle is None:<br>
            return None<br>
<br>
        # Определяем вьюпорт, если не передали явно<br>
        if viewport is None:<br>
            viewport = self._viewport_under_cursor(x, y)<br>
            if viewport is None:<br>
                return None<br>
<br>
        win_w, win_h = self.handle.window_size()       # логические пиксели<br>
        fb_w, fb_h = self.handle.framebuffer_size()    # физические пиксели (GL)<br>
<br>
        if win_w &lt;= 0 or win_h &lt;= 0 or fb_w &lt;= 0 or fb_h &lt;= 0:<br>
            return None<br>
<br>
        # --- 1) координаты viewport'а в физических пикселях (как при рендере) ---<br>
        px, py, pw, ph = self.viewport_rect_to_pixels(viewport)<br>
        # viewport_rect_to_pixels уже использует framebuffer_size()<br>
<br>
<br>
        # --- 2) переводим координаты мыши из логических в физические ---<br>
        sx = fb_w / float(win_w)<br>
        sy = fb_h / float(win_h)<br>
<br>
        x_phys = x * sx<br>
        y_phys = y * sy<br>
<br>
        # --- 3) локальные координаты внутри viewport'а ---<br>
        vx = x_phys - px<br>
        vy = y_phys - py<br>
<br>
<br>
        if vx &lt; 0 or vy &lt; 0 or vx &gt;= pw or vy &gt;= ph:<br>
            return None<br>
<br>
        # --- 4) перевод в координаты FBO (origin снизу-слева) ---<br>
        read_x = int(vx)<br>
        read_y = int(ph - vy - 1)   # инверсия Y, как в старом _do_pick_pass<br>
<br>
        # Берём FBO с id-картой<br>
        fbo_pool = getattr(viewport, &quot;_fbo_pool&quot;, None)<br>
        if not fbo_pool:<br>
            return None<br>
<br>
        fb_id = fbo_pool.get(&quot;id&quot;)<br>
        if fb_id is None:<br>
            return None<br>
<br>
<br>
        r, g, b, a = self.graphics.read_pixel(fb_id, read_x, read_y)<br>
        self.handle.bind_window_framebuffer()<br>
<br>
        pid = rgb_to_id(r, g, b)<br>
<br>
        if pid == 0:<br>
            return None<br>
<br>
        entity = self._pick_entity_by_id.get(pid)<br>
<br>
        return entity<br>
<br>
<br>
    def _handle_mouse_button_game_mode(self, window, button: MouseButton, action: Action, mods):<br>
        if self.handle is None:<br>
            return<br>
        x, y = self.handle.get_cursor_pos()<br>
        viewport = self._viewport_under_cursor(x, y)<br>
<br>
        # ---- UI click handling ----<br>
        if viewport and viewport.canvas:<br>
            if action == Action.PRESS:<br>
                interrupt = viewport.canvas.mouse_down(x, y, self.viewport_rect_to_pixels(viewport))<br>
                if interrupt:<br>
                    return<br>
            elif action == Action.RELEASE:<br>
                interrupt = viewport.canvas.mouse_up(x, y, self.viewport_rect_to_pixels(viewport))<br>
                if interrupt:<br>
                    return<br>
<br>
        # Обработка 3D сцены (сперва глобальная)<br>
        if action == Action.PRESS:<br>
            self._active_viewport = viewport<br>
        if action == Action.RELEASE:<br>
            self._last_cursor = None<br>
            if viewport is None:<br>
                viewport = self._active_viewport<br>
            self._active_viewport = None<br>
        if viewport is not None:<br>
            viewport.scene.dispatch_input(viewport, &quot;on_mouse_button&quot;, button=button, action=action, mods=mods)<br>
            <br>
        # Теперь обработка кликов по объектам сцены<br>
        if viewport is not None:<br>
            if action == Action.PRESS and button == MouseButton.LEFT:<br>
                cam = viewport.camera<br>
                if cam is not None:<br>
                    ray = cam.screen_point_to_ray(x, y, viewport_rect=self.viewport_rect_to_pixels(viewport))   # функция построения Ray3<br>
                    hit = viewport.scene.raycast(ray)<br>
                    print(&quot;Raycast hit:&quot;, hit)  # --- DEBUG ---<br>
                    if hit is not None:<br>
                        # Диспатчим on_click в компоненты<br>
                        entity = hit.entity<br>
                        for comp in entity.components:<br>
                            if hasattr(comp, &quot;on_click&quot;):  # или isinstance(comp, Clickable)<br>
                                comp.on_click(hit, button)<br>
<br>
        self._request_update()<br>
<br>
    def _handle_mouse_button_editor_mode(self, window, button: MouseButton, action: Action, mods):<br>
        if self.handle is None:<br>
            return<br>
        x, y = self.handle.get_cursor_pos()<br>
        viewport = self._viewport_under_cursor(x, y)<br>
<br>
        if viewport is not None:<br>
            if action == Action.PRESS and button == MouseButton.LEFT:<br>
                # запоминаем, где кликнули, для этого viewport<br>
                self._pick_requests[id(viewport)] = (x, y)   <br>
<br>
        # Обработка 3D сцены<br>
        if action == Action.PRESS:<br>
            self._active_viewport = viewport<br>
        if action == Action.RELEASE:<br>
            self._last_cursor = None<br>
            if viewport is None:<br>
                viewport = self._active_viewport<br>
            self._active_viewport = None<br>
        if viewport is not None:<br>
            #print(&quot;Dispatching mouse button to scene&quot;)  # --- DEBUG ---<br>
            viewport.scene.dispatch_input(viewport, &quot;on_mouse_button&quot;, button=button, action=action, mods=mods)  <br>
<br>
        if self.on_mouse_button_event:<br>
            self.on_mouse_button_event(button, action, x, y, viewport)   <br>
<br>
        self._request_update()<br>
<br>
    def _handle_mouse_button(self, window, button: MouseButton, action: Action, mods):<br>
        if self._world_mode == &quot;game&quot;:<br>
            self._handle_mouse_button_game_mode(window, button, action, mods)<br>
            return<br>
<br>
        elif self._world_mode == &quot;editor&quot;:<br>
            self._handle_mouse_button_editor_mode(window, button, action, mods)<br>
            return<br>
<br>
    def _handle_cursor_pos(self, window, x, y):<br>
        if self.handle is None:<br>
            return<br>
        <br>
        if self._last_cursor is None:<br>
            dx = dy = 0.0<br>
        else:<br>
            dx = x - self._last_cursor[0]<br>
            dy = y - self._last_cursor[1]<br>
        <br>
        self._last_cursor = (x, y)<br>
        viewport = self._active_viewport or self._viewport_under_cursor(x, y)<br>
<br>
        if viewport and viewport.canvas:<br>
            viewport.canvas.mouse_move(x, y, self.viewport_rect_to_pixels(viewport))<br>
<br>
        if viewport is not None:<br>
            viewport.scene.dispatch_input(viewport, &quot;on_mouse_move&quot;, x=x, y=y, dx=dx, dy=dy)<br>
<br>
        # пробрасываем инфу наверх (редактору), без знания про idmap и hover<br>
        if self.on_mouse_move_event is not None:<br>
            self.on_mouse_move_event(x, y, viewport)<br>
<br>
        self._request_update()<br>
<br>
    def _handle_scroll(self, window, xoffset, yoffset):<br>
        if self.handle is None:<br>
            return<br>
        x, y = self.handle.get_cursor_pos()<br>
        viewport = self._viewport_under_cursor(x, y) or self._active_viewport<br>
        if viewport is not None:<br>
            viewport.scene.dispatch_input(viewport, &quot;on_scroll&quot;, xoffset=xoffset, yoffset=yoffset)<br>
<br>
        self._request_update()<br>
<br>
    def _handle_key(self, window, key: Key, scancode: int, action: Action, mods):<br>
        if key == Key.ESCAPE and action == Action.PRESS and self.handle is not None:<br>
            self.handle.set_should_close(True)<br>
        viewport = self._active_viewport or (self.viewports[0] if self.viewports else None)<br>
        if viewport is not None:<br>
            viewport.scene.dispatch_input(viewport, &quot;on_key&quot;, key=key, scancode=scancode, action=action, mods=mods)<br>
<br>
        self._request_update()<br>
<br>
    def _viewport_under_cursor(self, x: float, y: float) -&gt; Optional[Viewport]:<br>
        if self.handle is None or not self.viewports:<br>
            return None<br>
        win_w, win_h = self.handle.window_size()<br>
        if win_w == 0 or win_h == 0:<br>
            return None<br>
        nx = x / win_w<br>
        ny = 1.0 - (y / win_h)<br>
        for viewport in self.viewports:<br>
            vx, vy, vw, vh = viewport.rect<br>
            if vx &lt;= nx &lt;= vx + vw and vy &lt;= ny &lt;= vy + vh:<br>
                return viewport<br>
        return None<br>
<br>
    def get_viewport_fbo(self, viewport, key, size):<br>
        d = viewport.__dict__.setdefault(&quot;_fbo_pool&quot;, {})<br>
        fb = d.get(key)<br>
        if fb is None:<br>
            fb = self.graphics.create_framebuffer(size)<br>
            d[key] = fb<br>
        else:<br>
            fb.resize(size)<br>
        return fb<br>
<br>
    def _render_core(self, from_backend: bool):<br>
        if self.handle is None:<br>
            return<br>
<br>
        self.graphics.ensure_ready()<br>
<br>
        if not from_backend:<br>
            self.make_current()<br>
<br>
        context_key = id(self)<br>
        width, height = self.handle.framebuffer_size()<br>
<br>
        for viewport in self.viewports:<br>
            vx, vy, vw, vh = viewport.rect<br>
            px = int(vx * width)<br>
            py = int(vy * height)<br>
            pw = max(1, int(vw * width))<br>
            ph = max(1, int(vh * height))<br>
<br>
            # Обновляем аспект камеры<br>
            viewport.camera.set_aspect(pw / float(max(1, ph)))<br>
<br>
            # Берём список пассов, который кто-то заранее повесил на viewport<br>
            frame_passes = viewport.frame_passes<br>
            if not frame_passes:<br>
                # Нечего рендерить — пропускаем<br>
                continue<br>
<br>
            # Контекст для пассов<br>
            ctx = FrameContext(<br>
                window=self,<br>
                viewport=viewport,<br>
                rect=(px, py, pw, ph),<br>
                size=(pw, ph),<br>
                context_key=context_key,<br>
                graphics=self.graphics,<br>
            )<br>
<br>
            # Строим и исполняем граф<br>
            graph = FrameGraph(frame_passes)<br>
            schedule = graph.build_schedule()<br>
<br>
            for p in schedule:<br>
                p.execute(ctx)<br>
<br>
        if self.after_render_handler is not None:<br>
            self.after_render_handler(self)<br>
<br>
        if not from_backend:<br>
            self.handle.swap_buffers()<br>
<br>
    def _request_update(self):<br>
        if self.handle is not None:<br>
            self.handle.request_update()<br>
<br>
    # def _do_pick_pass(self, viewport, px, py, pw, ph, mouse_x, mouse_y, context_key):<br>
    #     print(f&quot;Doing pick pass at mouse ({mouse_x}, {mouse_y}) in viewport rect px={px},py={py},pw={pw},ph={ph}&quot;)  # --- DEBUG ---<br>
<br>
    #     # 1) FBO для picking<br>
    #     fb_pick = self.get_viewport_fbo(viewport, &quot;PICK&quot;, (pw, ph))<br>
        <br>
    #     print(&quot;Picking FBO:&quot;, fb_pick._fbo)  # --- DEBUG ---<br>
    #     self.graphics.bind_framebuffer(fb_pick)<br>
    #     self.graphics.set_viewport(0, 0, pw, ph)<br>
    #     self.graphics.clear_color_depth((0.0, 0.0, 0.0, 0.0))<br>
<br>
    #     # 2) карта entity -&gt; id для этой сцены<br>
    #     pick_ids = {}<br>
    #     for ent in viewport.scene.entities:<br>
    #         if not ent.is_pickable():<br>
    #             continue<br>
<br>
    #         mr = ent.get_component(MeshRenderer)<br>
    #         if mr is None:<br>
    #             continue<br>
<br>
    #         # можешь фильтровать по наличию MeshRenderer<br>
    #         pick_ids[ent] = self._get_pick_id_for_entity(ent)<br>
<br>
    #     # 3) рендерим специальным пассом<br>
    #     self.renderer.render_viewport_pick(<br>
    #         viewport.scene,<br>
    #         viewport.camera,<br>
    #         (0, 0, pw, ph),<br>
    #         context_key,<br>
    #         pick_ids,<br>
    #     )<br>
<br>
    #     # 4) вычисляем координаты пикселя относительно FBO<br>
    #     win_w, win_h = self.handle.window_size()<br>
    #     if win_w == 0 or win_h == 0:<br>
    #         return<br>
<br>
    #     vx = mouse_x - px<br>
    #     vy = mouse_y - py<br>
    #     if vx &lt; 0 or vy &lt; 0 or vx &gt;= pw or vy &gt;= ph:<br>
    #         return<br>
<br>
    #     read_x = int(vx)<br>
    #     read_y = ph - int(vy) - 1  # инверсия по Y<br>
<br>
    #     print(&quot;Reading pixel at FBO coords:&quot;, read_x, read_y)  # --- DEBUG ---<br>
<br>
    #     r, g, b, a = self.graphics.read_pixel(fb_pick, read_x, read_y)<br>
    #     print(&quot;Picked color RGBA:&quot;, r, g, b, a)  # --- DEBUG ---<br>
    #     pid = rgb_to_id(r, g, b)<br>
    #     print(f&quot;Picked ID: {pid}&quot;)  # --- DEBUG ---<br>
    #     if pid == 0:<br>
    #         return<br>
<br>
    #     entity = self._pick_entity_by_id.get(pid)<br>
    #     if entity is not None and self.selection_handler is not None:<br>
    #         self.selection_handler(entity)<br>
<br>
    #     # вернёмся к обычному framebuffer'у<br>
    #     self.graphics.bind_framebuffer(None)<br>
<br>
<br>
<br>
# Backwards compatibility<br>
GLWindow = Window<br>
<!-- END SCAT CODE -->
</body>
</html>
