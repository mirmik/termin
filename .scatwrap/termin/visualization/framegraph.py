<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/framegraph.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
# termin/visualization/framegraph.py<br>
<br>
from __future__ import annotations<br>
<br>
from dataclasses import dataclass, field<br>
from typing import Dict, Iterable, List, Set, Any, Optional, Tuple<br>
from collections import deque<br>
from termin.visualization.shader import ShaderProgram<br>
from .picking import rgb_to_id<br>
from .components import MeshRenderer<br>
<br>
<br>
@dataclass<br>
class FramePass:<br>
&#9;&quot;&quot;&quot;<br>
&#9;Логический проход кадра.<br>
<br>
&#9;reads  – какие ресурсы этот проход читает (по именам).<br>
&#9;writes – какие ресурсы он пишет.<br>
&#9;inplace – модифицирующий ли это проход (in-place по смыслу).<br>
&#9;&quot;&quot;&quot;<br>
&#9;pass_name: str<br>
&#9;reads: Set[str] = field(default_factory=set)<br>
&#9;writes: Set[str] = field(default_factory=set)<br>
&#9;inplace: bool = False<br>
<br>
&#9;def __repr__(self) -&gt; str:<br>
&#9;&#9;return f&quot;FramePass({self.pass_name!r})&quot;<br>
<br>
<br>
class FrameGraphError(Exception):<br>
&#9;&quot;&quot;&quot;Базовая ошибка графа кадра.&quot;&quot;&quot;<br>
<br>
<br>
class FrameGraphMultiWriterError(FrameGraphError):<br>
&#9;&quot;&quot;&quot;Один и тот же ресурс пишут несколько пассов.&quot;&quot;&quot;<br>
<br>
<br>
class FrameGraphCycleError(FrameGraphError):<br>
&#9;&quot;&quot;&quot;В графе зависимостей обнаружен цикл.&quot;&quot;&quot;<br>
<br>
<br>
class FrameGraph:<br>
&#9;&quot;&quot;&quot;<br>
&#9;Простейший frame graph: на вход – набор FramePass,<br>
&#9;на выход – топологически отсортированный список пассов.<br>
&#9;&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self, passes: Iterable[FramePass]):<br>
&#9;&#9;self._passes: List[FramePass] = list(passes)<br>
&#9;&#9;# карта &quot;ресурс -&gt; каноническое имя&quot; (на будущее — для дебага / инспекции)<br>
&#9;&#9;self._canonical_resources: Dict[str, str] = {}<br>
<br>
&#9;# ------------------------------------------------------------------ #<br>
&#9;# ВНУТРЕННЕЕ ПРЕДСТАВЛЕНИЕ ГРАФА ЗАВИСИМОСТЕЙ<br>
&#9;# ------------------------------------------------------------------ #<br>
&#9;# Всё строим на ИНДЕКСАХ пассов (0..N-1), а не на самих объектах,<br>
&#9;# чтобы вообще не зависеть от их hash/eq.<br>
&#9;# ------------------------------------------------------------------ #<br>
<br>
&#9;def _build_dependency_graph(self):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Строит граф зависимостей между пассами.<br>
<br>
&#9;&#9;Возвращает:<br>
&#9;&#9;&#9;adjacency: dict[int, list[int]]<br>
&#9;&#9;&#9;&#9;для каждого индекса пасса – список индексов пассов,<br>
&#9;&#9;&#9;&#9;которые зависят от него (есть ребро writer -&gt; reader).<br>
&#9;&#9;&#9;in_degree: dict[int, int]<br>
&#9;&#9;&#9;&#9;количество входящих рёбер для каждого пасса.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;writer_for: Dict[str, int] = {}          # ресурс -&gt; индекс писателя<br>
&#9;&#9;readers_for: Dict[str, List[int]] = {}   # ресурс -&gt; список индексов читателей<br>
<br>
&#9;&#9;# для in-place логики<br>
&#9;&#9;modified_inputs: Set[str] = set()        # какие имена уже были входом inplace-пасса<br>
&#9;&#9;canonical: Dict[str, str] = {}           # локальная карта канонических имён<br>
<br>
&#9;&#9;n = len(self._passes)<br>
<br>
&#9;&#9;# 1) собираем writer-ов, reader-ов и валидируем inplace-пассы<br>
&#9;&#9;for idx, p in enumerate(self._passes):<br>
&#9;&#9;&#9;# --- валидация inplace-пассов ---<br>
&#9;&#9;&#9;if p.inplace:<br>
&#9;&#9;&#9;&#9;if len(p.reads) != 1 or len(p.writes) != 1:<br>
&#9;&#9;&#9;&#9;&#9;raise FrameGraphError(<br>
&#9;&#9;&#9;&#9;&#9;&#9;f&quot;Inplace pass {p.pass_name!r} must have exactly 1 read and 1 write, &quot;<br>
&#9;&#9;&#9;&#9;&#9;&#9;f&quot;got reads={p.reads}, writes={p.writes}&quot;<br>
&#9;&#9;&#9;&#9;&#9;)<br>
&#9;&#9;&#9;&#9;(src,) = p.reads<br>
&#9;&#9;&#9;&#9;if src in modified_inputs:<br>
&#9;&#9;&#9;&#9;&#9;# этот ресурс уже модифицировался другим inplace-пассом<br>
&#9;&#9;&#9;&#9;&#9;raise FrameGraphError(<br>
&#9;&#9;&#9;&#9;&#9;&#9;f&quot;Resource {src!r} is already modified by another inplace pass&quot;<br>
&#9;&#9;&#9;&#9;&#9;)<br>
&#9;&#9;&#9;&#9;modified_inputs.add(src)<br>
<br>
&#9;&#9;&#9;# --- writer-ы ---<br>
&#9;&#9;&#9;for res in p.writes:<br>
&#9;&#9;&#9;&#9;if res in writer_for:<br>
&#9;&#9;&#9;&#9;&#9;other_idx = writer_for[res]<br>
&#9;&#9;&#9;&#9;&#9;other = self._passes[other_idx]<br>
&#9;&#9;&#9;&#9;&#9;raise FrameGraphMultiWriterError(<br>
&#9;&#9;&#9;&#9;&#9;&#9;f&quot;Resource {res!r} is written by multiple passes: &quot;<br>
&#9;&#9;&#9;&#9;&#9;&#9;f&quot;{other.pass_name!r} and {p.pass_name!r}&quot;<br>
&#9;&#9;&#9;&#9;&#9;)<br>
&#9;&#9;&#9;&#9;writer_for[res] = idx<br>
<br>
&#9;&#9;&#9;&#9;# каноническое имя: первое появление ресурса как writer<br>
&#9;&#9;&#9;&#9;canonical.setdefault(res, res)<br>
<br>
&#9;&#9;&#9;# --- reader-ы ---<br>
&#9;&#9;&#9;for res in p.reads:<br>
&#9;&#9;&#9;&#9;lst = readers_for.setdefault(res, [])<br>
&#9;&#9;&#9;&#9;if idx not in lst:<br>
&#9;&#9;&#9;&#9;&#9;lst.append(idx)<br>
&#9;&#9;&#9;&#9;# если ресурс нигде не писали, но читают — считаем внешним входом<br>
&#9;&#9;&#9;&#9;canonical.setdefault(res, res)<br>
<br>
&#9;&#9;# 2) обработка алиасов для inplace-пассов<br>
&#9;&#9;# (это чисто справочная штука, на граф зависимостей не влияет)<br>
&#9;&#9;for p in self._passes:<br>
&#9;&#9;&#9;if not p.inplace:<br>
&#9;&#9;&#9;&#9;continue<br>
&#9;&#9;&#9;(src,) = p.reads<br>
&#9;&#9;&#9;(dst,) = p.writes<br>
<br>
&#9;&#9;&#9;src_canon = canonical.get(src, src)<br>
&#9;&#9;&#9;# выходу назначаем каноническое имя входа:<br>
&#9;&#9;&#9;# даже если у dst уже было &quot;своё&quot;, переопределяем —<br>
&#9;&#9;&#9;# мы сознательно объявляем их синонимами.<br>
&#9;&#9;&#9;canonical[dst] = src_canon<br>
<br>
&#9;&#9;# сохраним карту канонических имён (вдруг пригодится снаружи)<br>
&#9;&#9;self._canonical_resources = canonical<br>
<br>
&#9;&#9;# 3) adjacency и in_degree по индексам<br>
&#9;&#9;adjacency: Dict[int, List[int]] = {i: [] for i in range(n)}<br>
&#9;&#9;in_degree: Dict[int, int] = {i: 0 for i in range(n)}<br>
<br>
&#9;&#9;# Для каждого ресурса: writer -&gt; все его reader-ы<br>
&#9;&#9;for res, w_idx in writer_for.items():<br>
&#9;&#9;&#9;for r_idx in readers_for.get(res, ()):<br>
&#9;&#9;&#9;&#9;if r_idx == w_idx:<br>
&#9;&#9;&#9;&#9;&#9;continue  # на всякий случай, не создаём петли writer-&gt;writer<br>
&#9;&#9;&#9;&#9;if r_idx not in adjacency[w_idx]:<br>
&#9;&#9;&#9;&#9;&#9;adjacency[w_idx].append(r_idx)<br>
&#9;&#9;&#9;&#9;&#9;in_degree[r_idx] += 1<br>
<br>
&#9;&#9;return adjacency, in_degree<br>
<br>
&#9;# ------------------------------------------------------------------ #<br>
&#9;# ТОПОЛОГИЧЕСКАЯ СОРТИРОВКА (Kahn с приоритетом обычных пассов)<br>
&#9;# ------------------------------------------------------------------ #<br>
<br>
&#9;def build_schedule(self) -&gt; List[FramePass]:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Возвращает список пассов в порядке выполнения,<br>
&#9;&#9;учитывая зависимости read-after-write.<br>
<br>
&#9;&#9;Бросает:<br>
&#9;&#9;&#9;- FrameGraphMultiWriterError, если один ресурс пишут несколько пассов.<br>
&#9;&#9;&#9;- FrameGraphCycleError, если обнаружен цикл.<br>
&#9;&#9;&#9;- FrameGraphError, если нарушены правила inplace-пассов.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;adjacency, in_degree = self._build_dependency_graph()<br>
&#9;&#9;n = len(self._passes)<br>
<br>
&#9;&#9;is_inplace = [p.inplace for p in self._passes]<br>
<br>
&#9;&#9;# две очереди:<br>
&#9;&#9;#   обычные пассы — в ready_normal<br>
&#9;&#9;#   inplace-пассы — в ready_inplace<br>
&#9;&#9;ready_normal: deque[int] = deque()<br>
&#9;&#9;ready_inplace: deque[int] = deque()<br>
<br>
&#9;&#9;for i in range(n):<br>
&#9;&#9;&#9;if in_degree[i] == 0:<br>
&#9;&#9;&#9;&#9;if is_inplace[i]:<br>
&#9;&#9;&#9;&#9;&#9;ready_inplace.append(i)<br>
&#9;&#9;&#9;&#9;else:<br>
&#9;&#9;&#9;&#9;&#9;ready_normal.append(i)<br>
<br>
&#9;&#9;schedule_indices: List[int] = []<br>
<br>
&#9;&#9;while ready_normal or ready_inplace:<br>
&#9;&#9;&#9;# приоритет обычных пассов<br>
&#9;&#9;&#9;if ready_normal:<br>
&#9;&#9;&#9;&#9;idx = ready_normal.popleft()<br>
&#9;&#9;&#9;else:<br>
&#9;&#9;&#9;&#9;idx = ready_inplace.popleft()<br>
<br>
&#9;&#9;&#9;schedule_indices.append(idx)<br>
<br>
&#9;&#9;&#9;for dep in adjacency[idx]:<br>
&#9;&#9;&#9;&#9;in_degree[dep] -= 1<br>
&#9;&#9;&#9;&#9;if in_degree[dep] == 0:<br>
&#9;&#9;&#9;&#9;&#9;if is_inplace[dep]:<br>
&#9;&#9;&#9;&#9;&#9;&#9;ready_inplace.append(dep)<br>
&#9;&#9;&#9;&#9;&#9;else:<br>
&#9;&#9;&#9;&#9;&#9;&#9;ready_normal.append(dep)<br>
<br>
&#9;&#9;if len(schedule_indices) != n:<br>
&#9;&#9;&#9;# Остались вершины с in_degree &gt; 0 → цикл<br>
&#9;&#9;&#9;problematic = [self._passes[i].pass_name for i, deg in in_degree.items() if deg &gt; 0]<br>
&#9;&#9;&#9;raise FrameGraphCycleError(<br>
&#9;&#9;&#9;&#9;&quot;Frame graph contains a dependency cycle involving passes: &quot;<br>
&#9;&#9;&#9;&#9;+ &quot;, &quot;.join(problematic)<br>
&#9;&#9;&#9;)<br>
<br>
&#9;&#9;# Конвертируем индексы обратно в реальные пассы<br>
&#9;&#9;return [self._passes[i] for i in schedule_indices]<br>
<br>
&#9;# опционально — геттер канонического имени ресурса (на будущее)<br>
&#9;def canonical_resource(self, name: str) -&gt; str:<br>
&#9;&#9;return self._canonical_resources.get(name, name)<br>
<br>
@dataclass<br>
class FrameExecutionContext:<br>
&#9;graphics: GraphicsBackend<br>
&#9;window: &quot;Window&quot;<br>
&#9;viewport: &quot;Viewport&quot;<br>
&#9;rect: Tuple[int, int, int, int]  # (px, py, pw, ph)<br>
&#9;context_key: int<br>
<br>
&#9;# карта ресурс -&gt; FBO (или None, если это swapchain/экран)<br>
&#9;fbos: Dict[str, FramebufferHandle | None]<br>
<br>
class RenderFramePass(FramePass):<br>
&#9;def execute(self, ctx: FrameExecutionContext):<br>
&#9;&#9;raise NotImplementedError<br>
<br>
<br>
class ColorPass(RenderFramePass):<br>
&#9;def __init__(<br>
&#9;&#9;self,<br>
&#9;&#9;input_res: str = &quot;empty&quot;,<br>
&#9;&#9;output_res: str = &quot;color&quot;,<br>
&#9;&#9;pass_name: str = &quot;Color&quot;,<br>
&#9;):<br>
&#9;&#9;super().__init__(<br>
&#9;&#9;&#9;pass_name=pass_name,<br>
&#9;&#9;&#9;reads={input_res},<br>
&#9;&#9;&#9;writes={output_res},<br>
&#9;&#9;&#9;inplace=True,  # логически — модификатор состояния ресурса<br>
&#9;&#9;)<br>
&#9;&#9;self.input_res = input_res<br>
&#9;&#9;self.output_res = output_res<br>
<br>
&#9;def execute(self, ctx: FrameContext):<br>
&#9;&#9;gfx      = ctx.graphics<br>
&#9;&#9;window   = ctx.window<br>
&#9;&#9;viewport = ctx.viewport<br>
&#9;&#9;scene    = viewport.scene<br>
&#9;&#9;camera   = viewport.camera<br>
&#9;&#9;px, py, pw, ph = ctx.rect<br>
&#9;&#9;key      = ctx.context_key<br>
<br>
&#9;&#9;fb = window.get_viewport_fbo(viewport, self.output_res, (pw, ph))<br>
&#9;&#9;ctx.fbos[self.output_res] = fb<br>
<br>
&#9;&#9;gfx.bind_framebuffer(fb)<br>
&#9;&#9;gfx.set_viewport(0, 0, pw, ph)<br>
&#9;&#9;gfx.clear_color_depth(scene.background_color)<br>
<br>
&#9;&#9;window.renderer.render_viewport(<br>
&#9;&#9;&#9;scene,<br>
&#9;&#9;&#9;camera,<br>
&#9;&#9;&#9;(0, 0, pw, ph),<br>
&#9;&#9;&#9;key,<br>
&#9;&#9;)<br>
<br>
<br>
<br>
def blit_fbo_to_fbo(<br>
&#9;gfx: &quot;GraphicsBackend&quot;,<br>
&#9;src_fb,<br>
&#9;dst_fb,<br>
&#9;size: tuple[int, int],<br>
&#9;context_key: int,<br>
):<br>
&#9;w, h = size<br>
<br>
&#9;# целевой FBO<br>
&#9;gfx.bind_framebuffer(dst_fb)<br>
&#9;gfx.set_viewport(0, 0, w, h)<br>
<br>
&#9;# глубина нам не нужна<br>
&#9;gfx.set_depth_test(False)<br>
&#9;gfx.set_depth_mask(False)<br>
<br>
&#9;# берём ту же фуллскрин-квад-программу, что и PresentToScreenPass<br>
&#9;shader = PresentToScreenPass._get_shader()<br>
&#9;shader.ensure_ready(gfx)<br>
&#9;shader.use()<br>
&#9;shader.set_uniform_int(&quot;u_tex&quot;, 0)<br>
<br>
&#9;tex = src_fb.color_texture()<br>
&#9;tex.bind(0)<br>
<br>
&#9;gfx.draw_ui_textured_quad(context_key)<br>
<br>
&#9;gfx.set_depth_test(True)<br>
&#9;gfx.set_depth_mask(True)<br>
<br>
<br>
<br>
<br>
<br>
FSQ_VERT = &quot;&quot;&quot;<br>
#version 330 core<br>
layout(location = 0) in vec2 a_pos;<br>
layout(location = 1) in vec2 a_uv;<br>
<br>
out vec2 v_uv;<br>
<br>
void main() {<br>
&#9;v_uv = a_uv;<br>
&#9;gl_Position = vec4(a_pos, 0.0, 1.0);<br>
}<br>
&quot;&quot;&quot;<br>
<br>
FSQ_FRAG = &quot;&quot;&quot;<br>
#version 330 core<br>
in vec2 v_uv;<br>
out vec4 FragColor;<br>
<br>
uniform sampler2D u_tex;<br>
<br>
void main() {<br>
&#9;FragColor = texture(u_tex, v_uv);<br>
}<br>
&quot;&quot;&quot;<br>
<br>
<br>
class PresentToScreenPass(RenderFramePass):<br>
&#9;&quot;&quot;&quot;<br>
&#9;Берёт текстуру из ресурса input_res и выводит её на экран<br>
&#9;фуллскрин-квадом.<br>
&#9;&quot;&quot;&quot;<br>
&#9;_shader: ShaderProgram | None = None<br>
<br>
&#9;def __init__(self, input_res: str, pass_name: str = &quot;PresentToScreen&quot;):<br>
&#9;&#9;super().__init__(<br>
&#9;&#9;&#9;pass_name=pass_name,<br>
&#9;&#9;&#9;reads={input_res},<br>
&#9;&#9;&#9;writes=set(),  # экран считаем внешним<br>
&#9;&#9;&#9;inplace=False,<br>
&#9;&#9;)<br>
&#9;&#9;self.input_res = input_res<br>
<br>
&#9;@classmethod<br>
&#9;def _get_shader(cls) -&gt; ShaderProgram:<br>
&#9;&#9;if cls._shader is None:<br>
&#9;&#9;&#9;cls._shader = ShaderProgram(FSQ_VERT, FSQ_FRAG)<br>
&#9;&#9;return cls._shader<br>
<br>
&#9;def execute(self, ctx: FrameContext):<br>
&#9;&#9;gfx = ctx.graphics<br>
&#9;&#9;window = ctx.window<br>
&#9;&#9;px, py, pw, ph = ctx.rect<br>
&#9;&#9;key = ctx.context_key<br>
<br>
&#9;&#9;fb_in = ctx.fbos.get(self.input_res)<br>
&#9;&#9;if fb_in is None:<br>
&#9;&#9;&#9;return<br>
<br>
&#9;&#9;tex_in = fb_in.color_texture()<br>
<br>
&#9;&#9;window.handle.bind_window_framebuffer()<br>
&#9;&#9;gfx.set_viewport(px, py, pw, ph)<br>
<br>
&#9;&#9;gfx.set_depth_test(False)<br>
&#9;&#9;gfx.set_depth_mask(False)<br>
<br>
&#9;&#9;shader = self._get_shader()<br>
&#9;&#9;shader.ensure_ready(gfx)<br>
&#9;&#9;shader.use()<br>
&#9;&#9;shader.set_uniform_int(&quot;u_tex&quot;, 0)<br>
<br>
&#9;&#9;tex_in.bind(0)<br>
<br>
&#9;&#9;gfx.draw_ui_textured_quad(key)<br>
<br>
&#9;&#9;gfx.set_depth_test(True)<br>
&#9;&#9;gfx.set_depth_mask(True)<br>
<br>
<br>
class CanvasPass(RenderFramePass):<br>
&#9;def __init__(<br>
&#9;&#9;self,<br>
&#9;&#9;src: str = &quot;screen&quot;,<br>
&#9;&#9;dst: str = &quot;screen+ui&quot;,<br>
&#9;&#9;pass_name: str = &quot;Canvas&quot;,<br>
&#9;):<br>
&#9;&#9;super().__init__(<br>
&#9;&#9;&#9;pass_name=pass_name,<br>
&#9;&#9;&#9;reads={src},<br>
&#9;&#9;&#9;writes={dst},<br>
&#9;&#9;&#9;inplace=True,  # &lt;- ключевое: модифицирующий пасс<br>
&#9;&#9;)<br>
&#9;&#9;self.src = src<br>
&#9;&#9;self.dst = dst<br>
<br>
&#9;def execute(self, ctx: FrameContext):<br>
&#9;&#9;gfx = ctx.graphics<br>
&#9;&#9;window = ctx.window<br>
&#9;&#9;viewport = ctx.viewport<br>
&#9;&#9;px, py, pw, ph = ctx.rect<br>
&#9;&#9;key = ctx.context_key<br>
<br>
&#9;&#9;# Пытаемся взять FBO исходного ресурса<br>
&#9;&#9;fb_in = ctx.fbos.get(self.src)<br>
<br>
&#9;&#9;if fb_in is not None:<br>
&#9;&#9;&#9;# inplace по сути: переиспользуем тот же FBO<br>
&#9;&#9;&#9;fb_out = fb_in<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;# src – внешний ресурс / никем не создан:<br>
&#9;&#9;&#9;# делаем новый FBO под dst<br>
&#9;&#9;&#9;fb_out = window.get_viewport_fbo(viewport, self.dst, (pw, ph))<br>
<br>
&#9;&#9;# публикуем его под именем dst<br>
&#9;&#9;ctx.fbos[self.dst] = fb_out<br>
<br>
&#9;&#9;gfx.bind_framebuffer(fb_out)<br>
&#9;&#9;gfx.set_viewport(0, 0, pw, ph)<br>
<br>
&#9;&#9;# Ничего не чистим, не копируем: если там уже есть картинка —<br>
&#9;&#9;# рисуем UI поверх неё.<br>
&#9;&#9;if viewport.canvas:<br>
&#9;&#9;&#9;viewport.canvas.render(gfx, key, (0, 0, pw, ph))<br>
<br>
<br>
<br>
<br>
from .components import MeshRenderer<br>
from .picking import id_to_rgb<br>
<br>
class IdPass(RenderFramePass):<br>
&#9;def __init__(<br>
&#9;&#9;self,<br>
&#9;&#9;input_res: str = &quot;empty&quot;,<br>
&#9;&#9;output_res: str = &quot;id&quot;,<br>
&#9;&#9;pass_name: str = &quot;IdPass&quot;,<br>
&#9;):<br>
&#9;&#9;super().__init__(<br>
&#9;&#9;&#9;pass_name=pass_name,<br>
&#9;&#9;&#9;reads={input_res},<br>
&#9;&#9;&#9;writes={output_res},<br>
&#9;&#9;&#9;inplace=True,<br>
&#9;&#9;)<br>
&#9;&#9;self.input_res = input_res<br>
&#9;&#9;self.output_res = output_res<br>
<br>
&#9;def execute(self, ctx: FrameContext):<br>
&#9;&#9;gfx      = ctx.graphics<br>
&#9;&#9;window   = ctx.window<br>
&#9;&#9;viewport = ctx.viewport<br>
&#9;&#9;scene    = viewport.scene<br>
&#9;&#9;camera   = viewport.camera<br>
&#9;&#9;px, py, pw, ph = ctx.rect<br>
&#9;&#9;key      = ctx.context_key<br>
<br>
&#9;&#9;fb = window.get_viewport_fbo(viewport, self.output_res, (pw, ph))<br>
&#9;&#9;ctx.fbos[self.output_res] = fb<br>
<br>
&#9;&#9;gfx.bind_framebuffer(fb)<br>
&#9;&#9;gfx.set_viewport(0, 0, pw, ph)<br>
&#9;&#9;gfx.clear_color_depth((0.0, 0.0, 0.0, 0.0))<br>
<br>
&#9;&#9;pick_ids = {}<br>
&#9;&#9;for ent in scene.entities:<br>
&#9;&#9;&#9;if not ent.is_pickable():<br>
&#9;&#9;&#9;&#9;continue<br>
<br>
&#9;&#9;&#9;mr = ent.get_component(MeshRenderer)<br>
&#9;&#9;&#9;if mr is None:<br>
&#9;&#9;&#9;&#9;continue<br>
<br>
&#9;&#9;&#9;pid = window._get_pick_id_for_entity(ent)<br>
&#9;&#9;&#9;pick_ids[ent] = pid<br>
<br>
&#9;&#9;window.renderer.render_viewport_pick(<br>
&#9;&#9;&#9;scene,<br>
&#9;&#9;&#9;camera,<br>
&#9;&#9;&#9;(0, 0, pw, ph),<br>
&#9;&#9;&#9;key,<br>
&#9;&#9;&#9;pick_ids,<br>
&#9;&#9;)<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
@dataclass<br>
class FrameContext:<br>
&#9;window: &quot;Window&quot;<br>
&#9;viewport: &quot;Viewport&quot;<br>
&#9;rect: Tuple[int, int, int, int]<br>
&#9;size: Tuple[int, int]<br>
&#9;context_key: int<br>
&#9;graphics: &quot;GraphicsBackend&quot;<br>
&#9;fbos: Dict[str, Any] = field(default_factory=dict)<br>
<!-- END SCAT CODE -->
</body>
</html>
