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
&#9;Action,<br>
&#9;GraphicsBackend,<br>
&#9;Key,<br>
&#9;MouseButton,<br>
&#9;WindowBackend,<br>
&#9;BackendWindow,<br>
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
&#9;&quot;&quot;&quot;Manages a platform window and a set of viewports.&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self, width: int, height: int, title: str, renderer: Renderer, graphics: GraphicsBackend, window_backend: WindowBackend, share=None, **backend_kwargs):<br>
&#9;&#9;self.renderer = renderer<br>
&#9;&#9;self.graphics = graphics<br>
&#9;&#9;self.generate_default_pipeline = True<br>
&#9;&#9;share_handle = None<br>
&#9;&#9;if isinstance(share, Window):<br>
&#9;&#9;&#9;share_handle = share.handle<br>
&#9;&#9;elif isinstance(share, BackendWindow):<br>
&#9;&#9;&#9;share_handle = share<br>
<br>
&#9;&#9;self.window_backend = window_backend<br>
&#9;&#9;self.handle: BackendWindow = self.window_backend.create_window(width, height, title, share=share_handle, **backend_kwargs)<br>
<br>
&#9;&#9;self.viewports: List[Viewport] = []<br>
&#9;&#9;self._active_viewport: Optional[Viewport] = None<br>
&#9;&#9;self._last_cursor: Optional[Tuple[float, float]] = None<br>
<br>
&#9;&#9;self.handle.set_user_pointer(self)<br>
&#9;&#9;self.handle.set_framebuffer_size_callback(self._handle_framebuffer_resize)<br>
&#9;&#9;self.handle.set_cursor_pos_callback(self._handle_cursor_pos)<br>
&#9;&#9;self.handle.set_scroll_callback(self._handle_scroll)<br>
&#9;&#9;self.handle.set_mouse_button_callback(self._handle_mouse_button)<br>
&#9;&#9;self.handle.set_key_callback(self._handle_key)<br>
<br>
&#9;&#9;self.on_mouse_button_event : Optional[callable(MouseButton, MouseAction, x, y, Viewport)] = None<br>
&#9;&#9;self.on_mouse_move_event = None  # callable(x: float, y: float, viewport: Optional[Viewport])<br>
&#9;&#9;self.after_render_handler = None  # type: Optional[Callable[[&quot;Window&quot;], None]]<br>
<br>
&#9;&#9;self._world_mode = &quot;game&quot;  # or &quot;editor&quot;<br>
<br>
&#9;&#9;# picking support<br>
&#9;&#9;self.selection_handler = None    # редактор подпишется сюда<br>
&#9;&#9;self._pick_requests = {}         # viewport -&gt; (mouse_x, mouse_y)<br>
&#9;&#9;self._pick_id_counter = 1<br>
&#9;&#9;self._pick_entity_by_id = {}<br>
&#9;&#9;self._pick_id_by_entity = {}<br>
<br>
&#9;def set_selection_handler(self, handler):<br>
&#9;&#9;self.selection_handler = handler<br>
<br>
&#9;def set_world_mode(self, mode: str):<br>
&#9;&#9;self._world_mode = mode<br>
<br>
&#9;def _get_pick_id_for_entity(self, entity):<br>
&#9;&#9;pid = self._pick_id_by_entity.get(entity)<br>
&#9;&#9;if pid is not None:<br>
&#9;&#9;&#9;return pid<br>
&#9;&#9;pid = self._pick_id_counter<br>
&#9;&#9;self._pick_id_counter += 1<br>
&#9;&#9;self._pick_id_by_entity[entity] = pid<br>
&#9;&#9;self._pick_entity_by_id[pid] = entity<br>
&#9;&#9;return pid     <br>
<br>
&#9;def close(self):<br>
&#9;&#9;if self.handle:<br>
&#9;&#9;&#9;self.handle.close()<br>
&#9;&#9;&#9;self.handle = None<br>
<br>
&#9;@property<br>
&#9;def should_close(self) -&gt; bool:<br>
&#9;&#9;return self.handle is None or self.handle.should_close()<br>
<br>
&#9;def make_current(self):<br>
&#9;&#9;if self.handle is not None:<br>
&#9;&#9;&#9;self.handle.make_current()<br>
<br>
&#9;def add_viewport(self, scene: Scene, camera: CameraComponent, rect: Tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0), canvas: Optional[Canvas] = None) -&gt; Viewport:<br>
&#9;&#9;if not self.handle.drives_render():<br>
&#9;&#9;&#9;self.make_current()<br>
&#9;&#9;scene.ensure_ready(self.graphics)<br>
&#9;&#9;viewport = Viewport(scene=scene, camera=camera, rect=rect, canvas=canvas, window=self)<br>
&#9;&#9;camera.viewport = viewport<br>
&#9;&#9;self.viewports.append(viewport)<br>
<br>
&#9;&#9;if self.generate_default_pipeline:<br>
&#9;&#9;&#9;# собираем дефолтный пайплайн<br>
&#9;&#9;&#9;pipeline = viewport.make_default_pipeline()<br>
&#9;&#9;&#9;viewport.set_render_pipeline(pipeline)<br>
<br>
&#9;&#9;# if viewport.frame_passes == []:<br>
&#9;&#9;#     # Если никто не добавил пассы, добавим дефолтный main-pass + present<br>
&#9;&#9;#     from .framegraph import ColorPass, PresentToScreenPass, CanvasPass<br>
<br>
&#9;&#9;&#9;# viewport.frame_passes.append(ColorPass(input_res=&quot;empty&quot;,    output_res=&quot;color&quot;, pass_name=&quot;Color&quot;))<br>
&#9;&#9;&#9;# viewport.frame_passes.append(IdPass   (input_res=&quot;empty_id&quot;, output_res=&quot;id&quot;,    pass_name=&quot;Id&quot;))<br>
&#9;&#9;&#9;# # viewport.frame_passes.append(PostProcessPass(<br>
&#9;&#9;&#9;# #     effects=[HighlightEffect(lambda: editor.selected_entity_id)],<br>
&#9;&#9;&#9;# #     input_res=&quot;color&quot;,<br>
&#9;&#9;&#9;# #     output_res=&quot;color_pp&quot;,<br>
&#9;&#9;&#9;# #     pass_name=&quot;PostFX&quot;,<br>
&#9;&#9;&#9;# # ))<br>
&#9;&#9;&#9;# viewport.frame_passes.append(PostProcessPass(<br>
&#9;&#9;&#9;#     effects=[GrayscaleEffect()],<br>
&#9;&#9;&#9;#     input_res=&quot;color&quot;,<br>
&#9;&#9;&#9;#     output_res=&quot;color_pp&quot;,<br>
&#9;&#9;&#9;#     pass_name=&quot;PostFX&quot;,<br>
&#9;&#9;&#9;# ))<br>
&#9;&#9;&#9;<br>
&#9;&#9;&#9;# viewport.frame_passes.append(CanvasPass(src=&quot;color_pp&quot;, dst=&quot;color+ui&quot;, pass_name=&quot;Canvas&quot;))<br>
&#9;&#9;&#9;# viewport.frame_passes.append(PresentToScreenPass(input_res=&quot;color+ui&quot;, pass_name=&quot;Present&quot;))<br>
<br>
&#9;&#9;&#9;# viewport.frame_passes.append(PresentToScreenPass(input_res=&quot;id&quot;, pass_name=&quot;Present&quot;))<br>
&#9;&#9;&#9;# viewport.frame_passes.append(IdPass(input_res=&quot;empty_id&quot;, output_res=&quot;id&quot;, pass_name=&quot;IdPass&quot;))<br>
<br>
&#9;&#9;return viewport<br>
<br>
&#9;def update(self, dt: float):<br>
&#9;&#9;# Reserved for future per-window updates.<br>
&#9;&#9;return<br>
<br>
&#9;def render(self):<br>
&#9;&#9;self._render_core(from_backend=False)<br>
<br>
&#9;def viewport_rect_to_pixels(self, viewport: Viewport) -&gt; Tuple[int, int, int, int]:<br>
&#9;&#9;if self.handle is None:<br>
&#9;&#9;&#9;return (0, 0, 0, 0)<br>
&#9;&#9;width, height = self.handle.framebuffer_size()<br>
&#9;&#9;vx, vy, vw, vh = viewport.rect<br>
&#9;&#9;px = vx * width<br>
&#9;&#9;py = vy * height<br>
&#9;&#9;pw = vw * width<br>
&#9;&#9;ph = vh * height<br>
&#9;&#9;return px, py, pw, ph<br>
&#9;&#9;<br>
<br>
&#9;# Event handlers -----------------------------------------------------<br>
<br>
&#9;def _handle_framebuffer_resize(self, window, width, height):<br>
&#9;&#9;return<br>
<br>
<br>
&#9;from typing import Optional<br>
&#9;from termin.visualization.entity import Entity<br>
<br>
&#9;def pick_entity_at(self, x: float, y: float, viewport: Viewport = None) -&gt; Optional[Entity]:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Вернёт entity под пикселем (x, y) в координатах виджета (origin сверху-слева),<br>
&#9;&#9;используя id-карту, нарисованную IdPass в FBO с ключом 'id'.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;if self.handle is None:<br>
&#9;&#9;&#9;return None<br>
<br>
&#9;&#9;# Определяем вьюпорт, если не передали явно<br>
&#9;&#9;if viewport is None:<br>
&#9;&#9;&#9;viewport = self._viewport_under_cursor(x, y)<br>
&#9;&#9;&#9;if viewport is None:<br>
&#9;&#9;&#9;&#9;return None<br>
<br>
&#9;&#9;win_w, win_h = self.handle.window_size()       # логические пиксели<br>
&#9;&#9;fb_w, fb_h = self.handle.framebuffer_size()    # физические пиксели (GL)<br>
<br>
&#9;&#9;if win_w &lt;= 0 or win_h &lt;= 0 or fb_w &lt;= 0 or fb_h &lt;= 0:<br>
&#9;&#9;&#9;return None<br>
<br>
&#9;&#9;# --- 1) координаты viewport'а в физических пикселях (как при рендере) ---<br>
&#9;&#9;px, py, pw, ph = self.viewport_rect_to_pixels(viewport)<br>
&#9;&#9;# viewport_rect_to_pixels уже использует framebuffer_size()<br>
<br>
<br>
&#9;&#9;# --- 2) переводим координаты мыши из логических в физические ---<br>
&#9;&#9;sx = fb_w / float(win_w)<br>
&#9;&#9;sy = fb_h / float(win_h)<br>
<br>
&#9;&#9;x_phys = x * sx<br>
&#9;&#9;y_phys = y * sy<br>
<br>
&#9;&#9;# --- 3) локальные координаты внутри viewport'а ---<br>
&#9;&#9;vx = x_phys - px<br>
&#9;&#9;vy = y_phys - py<br>
<br>
<br>
&#9;&#9;if vx &lt; 0 or vy &lt; 0 or vx &gt;= pw or vy &gt;= ph:<br>
&#9;&#9;&#9;return None<br>
<br>
&#9;&#9;# --- 4) перевод в координаты FBO (origin снизу-слева) ---<br>
&#9;&#9;read_x = int(vx)<br>
&#9;&#9;read_y = int(ph - vy - 1)   # инверсия Y, как в старом _do_pick_pass<br>
<br>
&#9;&#9;# Берём FBO с id-картой<br>
&#9;&#9;fbo_pool = getattr(viewport, &quot;_fbo_pool&quot;, None)<br>
&#9;&#9;if not fbo_pool:<br>
&#9;&#9;&#9;return None<br>
<br>
&#9;&#9;fb_id = fbo_pool.get(&quot;id&quot;)<br>
&#9;&#9;if fb_id is None:<br>
&#9;&#9;&#9;return None<br>
<br>
<br>
&#9;&#9;r, g, b, a = self.graphics.read_pixel(fb_id, read_x, read_y)<br>
&#9;&#9;self.handle.bind_window_framebuffer()<br>
<br>
&#9;&#9;pid = rgb_to_id(r, g, b)<br>
<br>
&#9;&#9;if pid == 0:<br>
&#9;&#9;&#9;return None<br>
<br>
&#9;&#9;entity = self._pick_entity_by_id.get(pid)<br>
<br>
&#9;&#9;return entity<br>
<br>
<br>
&#9;def _handle_mouse_button_game_mode(self, window, button: MouseButton, action: Action, mods):<br>
&#9;&#9;if self.handle is None:<br>
&#9;&#9;&#9;return<br>
&#9;&#9;x, y = self.handle.get_cursor_pos()<br>
&#9;&#9;viewport = self._viewport_under_cursor(x, y)<br>
<br>
&#9;&#9;# ---- UI click handling ----<br>
&#9;&#9;if viewport and viewport.canvas:<br>
&#9;&#9;&#9;if action == Action.PRESS:<br>
&#9;&#9;&#9;&#9;interrupt = viewport.canvas.mouse_down(x, y, self.viewport_rect_to_pixels(viewport))<br>
&#9;&#9;&#9;&#9;if interrupt:<br>
&#9;&#9;&#9;&#9;&#9;return<br>
&#9;&#9;&#9;elif action == Action.RELEASE:<br>
&#9;&#9;&#9;&#9;interrupt = viewport.canvas.mouse_up(x, y, self.viewport_rect_to_pixels(viewport))<br>
&#9;&#9;&#9;&#9;if interrupt:<br>
&#9;&#9;&#9;&#9;&#9;return<br>
<br>
&#9;&#9;# Обработка 3D сцены (сперва глобальная)<br>
&#9;&#9;if action == Action.PRESS:<br>
&#9;&#9;&#9;self._active_viewport = viewport<br>
&#9;&#9;if action == Action.RELEASE:<br>
&#9;&#9;&#9;self._last_cursor = None<br>
&#9;&#9;&#9;if viewport is None:<br>
&#9;&#9;&#9;&#9;viewport = self._active_viewport<br>
&#9;&#9;&#9;self._active_viewport = None<br>
&#9;&#9;if viewport is not None:<br>
&#9;&#9;&#9;viewport.scene.dispatch_input(viewport, &quot;on_mouse_button&quot;, button=button, action=action, mods=mods)<br>
&#9;&#9;&#9;<br>
&#9;&#9;# Теперь обработка кликов по объектам сцены<br>
&#9;&#9;if viewport is not None:<br>
&#9;&#9;&#9;if action == Action.PRESS and button == MouseButton.LEFT:<br>
&#9;&#9;&#9;&#9;cam = viewport.camera<br>
&#9;&#9;&#9;&#9;if cam is not None:<br>
&#9;&#9;&#9;&#9;&#9;ray = cam.screen_point_to_ray(x, y, viewport_rect=self.viewport_rect_to_pixels(viewport))   # функция построения Ray3<br>
&#9;&#9;&#9;&#9;&#9;hit = viewport.scene.raycast(ray)<br>
&#9;&#9;&#9;&#9;&#9;print(&quot;Raycast hit:&quot;, hit)  # --- DEBUG ---<br>
&#9;&#9;&#9;&#9;&#9;if hit is not None:<br>
&#9;&#9;&#9;&#9;&#9;&#9;# Диспатчим on_click в компоненты<br>
&#9;&#9;&#9;&#9;&#9;&#9;entity = hit.entity<br>
&#9;&#9;&#9;&#9;&#9;&#9;for comp in entity.components:<br>
&#9;&#9;&#9;&#9;&#9;&#9;&#9;if hasattr(comp, &quot;on_click&quot;):  # или isinstance(comp, Clickable)<br>
&#9;&#9;&#9;&#9;&#9;&#9;&#9;&#9;comp.on_click(hit, button)<br>
<br>
&#9;&#9;self._request_update()<br>
<br>
&#9;def _handle_mouse_button_editor_mode(self, window, button: MouseButton, action: Action, mods):<br>
&#9;&#9;if self.handle is None:<br>
&#9;&#9;&#9;return<br>
&#9;&#9;x, y = self.handle.get_cursor_pos()<br>
&#9;&#9;viewport = self._viewport_under_cursor(x, y)<br>
<br>
&#9;&#9;if viewport is not None:<br>
&#9;&#9;&#9;if action == Action.PRESS and button == MouseButton.LEFT:<br>
&#9;&#9;&#9;&#9;# запоминаем, где кликнули, для этого viewport<br>
&#9;&#9;&#9;&#9;self._pick_requests[id(viewport)] = (x, y)   <br>
<br>
&#9;&#9;# Обработка 3D сцены<br>
&#9;&#9;if action == Action.PRESS:<br>
&#9;&#9;&#9;self._active_viewport = viewport<br>
&#9;&#9;if action == Action.RELEASE:<br>
&#9;&#9;&#9;self._last_cursor = None<br>
&#9;&#9;&#9;if viewport is None:<br>
&#9;&#9;&#9;&#9;viewport = self._active_viewport<br>
&#9;&#9;&#9;self._active_viewport = None<br>
&#9;&#9;if viewport is not None:<br>
&#9;&#9;&#9;#print(&quot;Dispatching mouse button to scene&quot;)  # --- DEBUG ---<br>
&#9;&#9;&#9;viewport.scene.dispatch_input(viewport, &quot;on_mouse_button&quot;, button=button, action=action, mods=mods)  <br>
<br>
&#9;&#9;if self.on_mouse_button_event:<br>
&#9;&#9;&#9;self.on_mouse_button_event(button, action, x, y, viewport)   <br>
<br>
&#9;&#9;self._request_update()<br>
<br>
&#9;def _handle_mouse_button(self, window, button: MouseButton, action: Action, mods):<br>
&#9;&#9;if self._world_mode == &quot;game&quot;:<br>
&#9;&#9;&#9;self._handle_mouse_button_game_mode(window, button, action, mods)<br>
&#9;&#9;&#9;return<br>
<br>
&#9;&#9;elif self._world_mode == &quot;editor&quot;:<br>
&#9;&#9;&#9;self._handle_mouse_button_editor_mode(window, button, action, mods)<br>
&#9;&#9;&#9;return<br>
<br>
&#9;def _handle_cursor_pos(self, window, x, y):<br>
&#9;&#9;if self.handle is None:<br>
&#9;&#9;&#9;return<br>
&#9;&#9;<br>
&#9;&#9;if self._last_cursor is None:<br>
&#9;&#9;&#9;dx = dy = 0.0<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;dx = x - self._last_cursor[0]<br>
&#9;&#9;&#9;dy = y - self._last_cursor[1]<br>
&#9;&#9;<br>
&#9;&#9;self._last_cursor = (x, y)<br>
&#9;&#9;viewport = self._active_viewport or self._viewport_under_cursor(x, y)<br>
<br>
&#9;&#9;if viewport and viewport.canvas:<br>
&#9;&#9;&#9;viewport.canvas.mouse_move(x, y, self.viewport_rect_to_pixels(viewport))<br>
<br>
&#9;&#9;if viewport is not None:<br>
&#9;&#9;&#9;viewport.scene.dispatch_input(viewport, &quot;on_mouse_move&quot;, x=x, y=y, dx=dx, dy=dy)<br>
<br>
&#9;&#9;# пробрасываем инфу наверх (редактору), без знания про idmap и hover<br>
&#9;&#9;if self.on_mouse_move_event is not None:<br>
&#9;&#9;&#9;self.on_mouse_move_event(x, y, viewport)<br>
<br>
&#9;&#9;self._request_update()<br>
<br>
&#9;def _handle_scroll(self, window, xoffset, yoffset):<br>
&#9;&#9;if self.handle is None:<br>
&#9;&#9;&#9;return<br>
&#9;&#9;x, y = self.handle.get_cursor_pos()<br>
&#9;&#9;viewport = self._viewport_under_cursor(x, y) or self._active_viewport<br>
&#9;&#9;if viewport is not None:<br>
&#9;&#9;&#9;viewport.scene.dispatch_input(viewport, &quot;on_scroll&quot;, xoffset=xoffset, yoffset=yoffset)<br>
<br>
&#9;&#9;self._request_update()<br>
<br>
&#9;def _handle_key(self, window, key: Key, scancode: int, action: Action, mods):<br>
&#9;&#9;if key == Key.ESCAPE and action == Action.PRESS and self.handle is not None:<br>
&#9;&#9;&#9;self.handle.set_should_close(True)<br>
&#9;&#9;viewport = self._active_viewport or (self.viewports[0] if self.viewports else None)<br>
&#9;&#9;if viewport is not None:<br>
&#9;&#9;&#9;viewport.scene.dispatch_input(viewport, &quot;on_key&quot;, key=key, scancode=scancode, action=action, mods=mods)<br>
<br>
&#9;&#9;self._request_update()<br>
<br>
&#9;def _viewport_under_cursor(self, x: float, y: float) -&gt; Optional[Viewport]:<br>
&#9;&#9;if self.handle is None or not self.viewports:<br>
&#9;&#9;&#9;return None<br>
&#9;&#9;win_w, win_h = self.handle.window_size()<br>
&#9;&#9;if win_w == 0 or win_h == 0:<br>
&#9;&#9;&#9;return None<br>
&#9;&#9;nx = x / win_w<br>
&#9;&#9;ny = 1.0 - (y / win_h)<br>
&#9;&#9;for viewport in self.viewports:<br>
&#9;&#9;&#9;vx, vy, vw, vh = viewport.rect<br>
&#9;&#9;&#9;if vx &lt;= nx &lt;= vx + vw and vy &lt;= ny &lt;= vy + vh:<br>
&#9;&#9;&#9;&#9;return viewport<br>
&#9;&#9;return None<br>
<br>
&#9;def get_viewport_fbo(self, viewport, key, size):<br>
&#9;&#9;d = viewport.__dict__.setdefault(&quot;_fbo_pool&quot;, {})<br>
&#9;&#9;fb = d.get(key)<br>
&#9;&#9;if fb is None:<br>
&#9;&#9;&#9;fb = self.graphics.create_framebuffer(size)<br>
&#9;&#9;&#9;d[key] = fb<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;fb.resize(size)<br>
&#9;&#9;return fb<br>
<br>
&#9;def _render_core(self, from_backend: bool):<br>
&#9;&#9;if self.handle is None:<br>
&#9;&#9;&#9;return<br>
<br>
&#9;&#9;self.graphics.ensure_ready()<br>
<br>
&#9;&#9;if not from_backend:<br>
&#9;&#9;&#9;self.make_current()<br>
<br>
&#9;&#9;context_key = id(self)<br>
&#9;&#9;width, height = self.handle.framebuffer_size()<br>
<br>
&#9;&#9;for viewport in self.viewports:<br>
&#9;&#9;&#9;vx, vy, vw, vh = viewport.rect<br>
&#9;&#9;&#9;px = int(vx * width)<br>
&#9;&#9;&#9;py = int(vy * height)<br>
&#9;&#9;&#9;pw = max(1, int(vw * width))<br>
&#9;&#9;&#9;ph = max(1, int(vh * height))<br>
<br>
&#9;&#9;&#9;# Обновляем аспект камеры<br>
&#9;&#9;&#9;viewport.camera.set_aspect(pw / float(max(1, ph)))<br>
<br>
&#9;&#9;&#9;# Берём список пассов, который кто-то заранее повесил на viewport<br>
&#9;&#9;&#9;frame_passes = viewport.frame_passes<br>
&#9;&#9;&#9;if not frame_passes:<br>
&#9;&#9;&#9;&#9;# Нечего рендерить — пропускаем<br>
&#9;&#9;&#9;&#9;continue<br>
<br>
&#9;&#9;&#9;# Контекст для пассов<br>
&#9;&#9;&#9;ctx = FrameContext(<br>
&#9;&#9;&#9;&#9;window=self,<br>
&#9;&#9;&#9;&#9;viewport=viewport,<br>
&#9;&#9;&#9;&#9;rect=(px, py, pw, ph),<br>
&#9;&#9;&#9;&#9;size=(pw, ph),<br>
&#9;&#9;&#9;&#9;context_key=context_key,<br>
&#9;&#9;&#9;&#9;graphics=self.graphics,<br>
&#9;&#9;&#9;)<br>
<br>
&#9;&#9;&#9;# Строим и исполняем граф<br>
&#9;&#9;&#9;graph = FrameGraph(frame_passes)<br>
&#9;&#9;&#9;schedule = graph.build_schedule()<br>
<br>
&#9;&#9;&#9;for p in schedule:<br>
&#9;&#9;&#9;&#9;p.execute(ctx)<br>
<br>
&#9;&#9;if self.after_render_handler is not None:<br>
&#9;&#9;&#9;self.after_render_handler(self)<br>
<br>
&#9;&#9;if not from_backend:<br>
&#9;&#9;&#9;self.handle.swap_buffers()<br>
<br>
&#9;def _request_update(self):<br>
&#9;&#9;if self.handle is not None:<br>
&#9;&#9;&#9;self.handle.request_update()<br>
<br>
&#9;# def _do_pick_pass(self, viewport, px, py, pw, ph, mouse_x, mouse_y, context_key):<br>
&#9;#     print(f&quot;Doing pick pass at mouse ({mouse_x}, {mouse_y}) in viewport rect px={px},py={py},pw={pw},ph={ph}&quot;)  # --- DEBUG ---<br>
<br>
&#9;#     # 1) FBO для picking<br>
&#9;#     fb_pick = self.get_viewport_fbo(viewport, &quot;PICK&quot;, (pw, ph))<br>
&#9;&#9;<br>
&#9;#     print(&quot;Picking FBO:&quot;, fb_pick._fbo)  # --- DEBUG ---<br>
&#9;#     self.graphics.bind_framebuffer(fb_pick)<br>
&#9;#     self.graphics.set_viewport(0, 0, pw, ph)<br>
&#9;#     self.graphics.clear_color_depth((0.0, 0.0, 0.0, 0.0))<br>
<br>
&#9;#     # 2) карта entity -&gt; id для этой сцены<br>
&#9;#     pick_ids = {}<br>
&#9;#     for ent in viewport.scene.entities:<br>
&#9;#         if not ent.is_pickable():<br>
&#9;#             continue<br>
<br>
&#9;#         mr = ent.get_component(MeshRenderer)<br>
&#9;#         if mr is None:<br>
&#9;#             continue<br>
<br>
&#9;#         # можешь фильтровать по наличию MeshRenderer<br>
&#9;#         pick_ids[ent] = self._get_pick_id_for_entity(ent)<br>
<br>
&#9;#     # 3) рендерим специальным пассом<br>
&#9;#     self.renderer.render_viewport_pick(<br>
&#9;#         viewport.scene,<br>
&#9;#         viewport.camera,<br>
&#9;#         (0, 0, pw, ph),<br>
&#9;#         context_key,<br>
&#9;#         pick_ids,<br>
&#9;#     )<br>
<br>
&#9;#     # 4) вычисляем координаты пикселя относительно FBO<br>
&#9;#     win_w, win_h = self.handle.window_size()<br>
&#9;#     if win_w == 0 or win_h == 0:<br>
&#9;#         return<br>
<br>
&#9;#     vx = mouse_x - px<br>
&#9;#     vy = mouse_y - py<br>
&#9;#     if vx &lt; 0 or vy &lt; 0 or vx &gt;= pw or vy &gt;= ph:<br>
&#9;#         return<br>
<br>
&#9;#     read_x = int(vx)<br>
&#9;#     read_y = ph - int(vy) - 1  # инверсия по Y<br>
<br>
&#9;#     print(&quot;Reading pixel at FBO coords:&quot;, read_x, read_y)  # --- DEBUG ---<br>
<br>
&#9;#     r, g, b, a = self.graphics.read_pixel(fb_pick, read_x, read_y)<br>
&#9;#     print(&quot;Picked color RGBA:&quot;, r, g, b, a)  # --- DEBUG ---<br>
&#9;#     pid = rgb_to_id(r, g, b)<br>
&#9;#     print(f&quot;Picked ID: {pid}&quot;)  # --- DEBUG ---<br>
&#9;#     if pid == 0:<br>
&#9;#         return<br>
<br>
&#9;#     entity = self._pick_entity_by_id.get(pid)<br>
&#9;#     if entity is not None and self.selection_handler is not None:<br>
&#9;#         self.selection_handler(entity)<br>
<br>
&#9;#     # вернёмся к обычному framebuffer'у<br>
&#9;#     self.graphics.bind_framebuffer(None)<br>
<br>
<br>
<br>
# Backwards compatibility<br>
GLWindow = Window<br>
<!-- END SCAT CODE -->
</body>
</html>
