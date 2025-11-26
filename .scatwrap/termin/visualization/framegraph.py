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
    &quot;&quot;&quot;<br>
    Логический проход кадра.<br>
<br>
    reads  – какие ресурсы этот проход читает (по именам).<br>
    writes – какие ресурсы он пишет.<br>
    inplace – модифицирующий ли это проход (in-place по смыслу).<br>
    &quot;&quot;&quot;<br>
    pass_name: str<br>
    reads: Set[str] = field(default_factory=set)<br>
    writes: Set[str] = field(default_factory=set)<br>
    inplace: bool = False<br>
<br>
    def __repr__(self) -&gt; str:<br>
        return f&quot;FramePass({self.pass_name!r})&quot;<br>
<br>
<br>
class FrameGraphError(Exception):<br>
    &quot;&quot;&quot;Базовая ошибка графа кадра.&quot;&quot;&quot;<br>
<br>
<br>
class FrameGraphMultiWriterError(FrameGraphError):<br>
    &quot;&quot;&quot;Один и тот же ресурс пишут несколько пассов.&quot;&quot;&quot;<br>
<br>
<br>
class FrameGraphCycleError(FrameGraphError):<br>
    &quot;&quot;&quot;В графе зависимостей обнаружен цикл.&quot;&quot;&quot;<br>
<br>
<br>
class FrameGraph:<br>
    &quot;&quot;&quot;<br>
    Простейший frame graph: на вход – набор FramePass,<br>
    на выход – топологически отсортированный список пассов.<br>
    &quot;&quot;&quot;<br>
<br>
    def __init__(self, passes: Iterable[FramePass]):<br>
        self._passes: List[FramePass] = list(passes)<br>
        # карта &quot;ресурс -&gt; каноническое имя&quot; (на будущее — для дебага / инспекции)<br>
        self._canonical_resources: Dict[str, str] = {}<br>
<br>
    # ------------------------------------------------------------------ #<br>
    # ВНУТРЕННЕЕ ПРЕДСТАВЛЕНИЕ ГРАФА ЗАВИСИМОСТЕЙ<br>
    # ------------------------------------------------------------------ #<br>
    # Всё строим на ИНДЕКСАХ пассов (0..N-1), а не на самих объектах,<br>
    # чтобы вообще не зависеть от их hash/eq.<br>
    # ------------------------------------------------------------------ #<br>
<br>
    def _build_dependency_graph(self):<br>
        &quot;&quot;&quot;<br>
        Строит граф зависимостей между пассами.<br>
<br>
        Возвращает:<br>
            adjacency: dict[int, list[int]]<br>
                для каждого индекса пасса – список индексов пассов,<br>
                которые зависят от него (есть ребро writer -&gt; reader).<br>
            in_degree: dict[int, int]<br>
                количество входящих рёбер для каждого пасса.<br>
        &quot;&quot;&quot;<br>
        writer_for: Dict[str, int] = {}          # ресурс -&gt; индекс писателя<br>
        readers_for: Dict[str, List[int]] = {}   # ресурс -&gt; список индексов читателей<br>
<br>
        # для in-place логики<br>
        modified_inputs: Set[str] = set()        # какие имена уже были входом inplace-пасса<br>
        canonical: Dict[str, str] = {}           # локальная карта канонических имён<br>
<br>
        n = len(self._passes)<br>
<br>
        # 1) собираем writer-ов, reader-ов и валидируем inplace-пассы<br>
        for idx, p in enumerate(self._passes):<br>
            # --- валидация inplace-пассов ---<br>
            if p.inplace:<br>
                if len(p.reads) != 1 or len(p.writes) != 1:<br>
                    raise FrameGraphError(<br>
                        f&quot;Inplace pass {p.pass_name!r} must have exactly 1 read and 1 write, &quot;<br>
                        f&quot;got reads={p.reads}, writes={p.writes}&quot;<br>
                    )<br>
                (src,) = p.reads<br>
                if src in modified_inputs:<br>
                    # этот ресурс уже модифицировался другим inplace-пассом<br>
                    raise FrameGraphError(<br>
                        f&quot;Resource {src!r} is already modified by another inplace pass&quot;<br>
                    )<br>
                modified_inputs.add(src)<br>
<br>
            # --- writer-ы ---<br>
            for res in p.writes:<br>
                if res in writer_for:<br>
                    other_idx = writer_for[res]<br>
                    other = self._passes[other_idx]<br>
                    raise FrameGraphMultiWriterError(<br>
                        f&quot;Resource {res!r} is written by multiple passes: &quot;<br>
                        f&quot;{other.pass_name!r} and {p.pass_name!r}&quot;<br>
                    )<br>
                writer_for[res] = idx<br>
<br>
                # каноническое имя: первое появление ресурса как writer<br>
                canonical.setdefault(res, res)<br>
<br>
            # --- reader-ы ---<br>
            for res in p.reads:<br>
                lst = readers_for.setdefault(res, [])<br>
                if idx not in lst:<br>
                    lst.append(idx)<br>
                # если ресурс нигде не писали, но читают — считаем внешним входом<br>
                canonical.setdefault(res, res)<br>
<br>
        # 2) обработка алиасов для inplace-пассов<br>
        # (это чисто справочная штука, на граф зависимостей не влияет)<br>
        for p in self._passes:<br>
            if not p.inplace:<br>
                continue<br>
            (src,) = p.reads<br>
            (dst,) = p.writes<br>
<br>
            src_canon = canonical.get(src, src)<br>
            # выходу назначаем каноническое имя входа:<br>
            # даже если у dst уже было &quot;своё&quot;, переопределяем —<br>
            # мы сознательно объявляем их синонимами.<br>
            canonical[dst] = src_canon<br>
<br>
        # сохраним карту канонических имён (вдруг пригодится снаружи)<br>
        self._canonical_resources = canonical<br>
<br>
        # 3) adjacency и in_degree по индексам<br>
        adjacency: Dict[int, List[int]] = {i: [] for i in range(n)}<br>
        in_degree: Dict[int, int] = {i: 0 for i in range(n)}<br>
<br>
        # Для каждого ресурса: writer -&gt; все его reader-ы<br>
        for res, w_idx in writer_for.items():<br>
            for r_idx in readers_for.get(res, ()):<br>
                if r_idx == w_idx:<br>
                    continue  # на всякий случай, не создаём петли writer-&gt;writer<br>
                if r_idx not in adjacency[w_idx]:<br>
                    adjacency[w_idx].append(r_idx)<br>
                    in_degree[r_idx] += 1<br>
<br>
        return adjacency, in_degree<br>
<br>
    # ------------------------------------------------------------------ #<br>
    # ТОПОЛОГИЧЕСКАЯ СОРТИРОВКА (Kahn с приоритетом обычных пассов)<br>
    # ------------------------------------------------------------------ #<br>
<br>
    def build_schedule(self) -&gt; List[FramePass]:<br>
        &quot;&quot;&quot;<br>
        Возвращает список пассов в порядке выполнения,<br>
        учитывая зависимости read-after-write.<br>
<br>
        Бросает:<br>
            - FrameGraphMultiWriterError, если один ресурс пишут несколько пассов.<br>
            - FrameGraphCycleError, если обнаружен цикл.<br>
            - FrameGraphError, если нарушены правила inplace-пассов.<br>
        &quot;&quot;&quot;<br>
        adjacency, in_degree = self._build_dependency_graph()<br>
        n = len(self._passes)<br>
<br>
        is_inplace = [p.inplace for p in self._passes]<br>
<br>
        # две очереди:<br>
        #   обычные пассы — в ready_normal<br>
        #   inplace-пассы — в ready_inplace<br>
        ready_normal: deque[int] = deque()<br>
        ready_inplace: deque[int] = deque()<br>
<br>
        for i in range(n):<br>
            if in_degree[i] == 0:<br>
                if is_inplace[i]:<br>
                    ready_inplace.append(i)<br>
                else:<br>
                    ready_normal.append(i)<br>
<br>
        schedule_indices: List[int] = []<br>
<br>
        while ready_normal or ready_inplace:<br>
            # приоритет обычных пассов<br>
            if ready_normal:<br>
                idx = ready_normal.popleft()<br>
            else:<br>
                idx = ready_inplace.popleft()<br>
<br>
            schedule_indices.append(idx)<br>
<br>
            for dep in adjacency[idx]:<br>
                in_degree[dep] -= 1<br>
                if in_degree[dep] == 0:<br>
                    if is_inplace[dep]:<br>
                        ready_inplace.append(dep)<br>
                    else:<br>
                        ready_normal.append(dep)<br>
<br>
        if len(schedule_indices) != n:<br>
            # Остались вершины с in_degree &gt; 0 → цикл<br>
            problematic = [self._passes[i].pass_name for i, deg in in_degree.items() if deg &gt; 0]<br>
            raise FrameGraphCycleError(<br>
                &quot;Frame graph contains a dependency cycle involving passes: &quot;<br>
                + &quot;, &quot;.join(problematic)<br>
            )<br>
<br>
        # Конвертируем индексы обратно в реальные пассы<br>
        return [self._passes[i] for i in schedule_indices]<br>
<br>
    # опционально — геттер канонического имени ресурса (на будущее)<br>
    def canonical_resource(self, name: str) -&gt; str:<br>
        return self._canonical_resources.get(name, name)<br>
<br>
@dataclass<br>
class FrameExecutionContext:<br>
    graphics: GraphicsBackend<br>
    window: &quot;Window&quot;<br>
    viewport: &quot;Viewport&quot;<br>
    rect: Tuple[int, int, int, int]  # (px, py, pw, ph)<br>
    context_key: int<br>
<br>
    # карта ресурс -&gt; FBO (или None, если это swapchain/экран)<br>
    fbos: Dict[str, FramebufferHandle | None]<br>
<br>
class RenderFramePass(FramePass):<br>
    def execute(self, ctx: FrameExecutionContext):<br>
        raise NotImplementedError<br>
<br>
<br>
class ColorPass(RenderFramePass):<br>
    def __init__(<br>
        self,<br>
        input_res: str = &quot;empty&quot;,<br>
        output_res: str = &quot;color&quot;,<br>
        pass_name: str = &quot;Color&quot;,<br>
    ):<br>
        super().__init__(<br>
            pass_name=pass_name,<br>
            reads={input_res},<br>
            writes={output_res},<br>
            inplace=True,  # логически — модификатор состояния ресурса<br>
        )<br>
        self.input_res = input_res<br>
        self.output_res = output_res<br>
<br>
    def execute(self, ctx: FrameContext):<br>
        gfx      = ctx.graphics<br>
        window   = ctx.window<br>
        viewport = ctx.viewport<br>
        scene    = viewport.scene<br>
        camera   = viewport.camera<br>
        px, py, pw, ph = ctx.rect<br>
        key      = ctx.context_key<br>
<br>
        fb = window.get_viewport_fbo(viewport, self.output_res, (pw, ph))<br>
        ctx.fbos[self.output_res] = fb<br>
<br>
        gfx.bind_framebuffer(fb)<br>
        gfx.set_viewport(0, 0, pw, ph)<br>
        gfx.clear_color_depth(scene.background_color)<br>
<br>
        window.renderer.render_viewport(<br>
            scene,<br>
            camera,<br>
            (0, 0, pw, ph),<br>
            key,<br>
        )<br>
<br>
<br>
<br>
def blit_fbo_to_fbo(<br>
    gfx: &quot;GraphicsBackend&quot;,<br>
    src_fb,<br>
    dst_fb,<br>
    size: tuple[int, int],<br>
    context_key: int,<br>
):<br>
    w, h = size<br>
<br>
    # целевой FBO<br>
    gfx.bind_framebuffer(dst_fb)<br>
    gfx.set_viewport(0, 0, w, h)<br>
<br>
    # глубина нам не нужна<br>
    gfx.set_depth_test(False)<br>
    gfx.set_depth_mask(False)<br>
<br>
    # берём ту же фуллскрин-квад-программу, что и PresentToScreenPass<br>
    shader = PresentToScreenPass._get_shader()<br>
    shader.ensure_ready(gfx)<br>
    shader.use()<br>
    shader.set_uniform_int(&quot;u_tex&quot;, 0)<br>
<br>
    tex = src_fb.color_texture()<br>
    tex.bind(0)<br>
<br>
    gfx.draw_ui_textured_quad(context_key)<br>
<br>
    gfx.set_depth_test(True)<br>
    gfx.set_depth_mask(True)<br>
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
    v_uv = a_uv;<br>
    gl_Position = vec4(a_pos, 0.0, 1.0);<br>
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
    FragColor = texture(u_tex, v_uv);<br>
}<br>
&quot;&quot;&quot;<br>
<br>
<br>
class PresentToScreenPass(RenderFramePass):<br>
    &quot;&quot;&quot;<br>
    Берёт текстуру из ресурса input_res и выводит её на экран<br>
    фуллскрин-квадом.<br>
    &quot;&quot;&quot;<br>
    _shader: ShaderProgram | None = None<br>
<br>
    def __init__(self, input_res: str, pass_name: str = &quot;PresentToScreen&quot;):<br>
        super().__init__(<br>
            pass_name=pass_name,<br>
            reads={input_res},<br>
            writes=set(),  # экран считаем внешним<br>
            inplace=False,<br>
        )<br>
        self.input_res = input_res<br>
<br>
    @classmethod<br>
    def _get_shader(cls) -&gt; ShaderProgram:<br>
        if cls._shader is None:<br>
            cls._shader = ShaderProgram(FSQ_VERT, FSQ_FRAG)<br>
        return cls._shader<br>
<br>
    def execute(self, ctx: FrameContext):<br>
        gfx = ctx.graphics<br>
        window = ctx.window<br>
        px, py, pw, ph = ctx.rect<br>
        key = ctx.context_key<br>
<br>
        fb_in = ctx.fbos.get(self.input_res)<br>
        if fb_in is None:<br>
            return<br>
<br>
        tex_in = fb_in.color_texture()<br>
<br>
        window.handle.bind_window_framebuffer()<br>
        gfx.set_viewport(px, py, pw, ph)<br>
<br>
        gfx.set_depth_test(False)<br>
        gfx.set_depth_mask(False)<br>
<br>
        shader = self._get_shader()<br>
        shader.ensure_ready(gfx)<br>
        shader.use()<br>
        shader.set_uniform_int(&quot;u_tex&quot;, 0)<br>
<br>
        tex_in.bind(0)<br>
<br>
        gfx.draw_ui_textured_quad(key)<br>
<br>
        gfx.set_depth_test(True)<br>
        gfx.set_depth_mask(True)<br>
<br>
<br>
class CanvasPass(RenderFramePass):<br>
    def __init__(<br>
        self,<br>
        src: str = &quot;screen&quot;,<br>
        dst: str = &quot;screen+ui&quot;,<br>
        pass_name: str = &quot;Canvas&quot;,<br>
    ):<br>
        super().__init__(<br>
            pass_name=pass_name,<br>
            reads={src},<br>
            writes={dst},<br>
            inplace=True,  # &lt;- ключевое: модифицирующий пасс<br>
        )<br>
        self.src = src<br>
        self.dst = dst<br>
<br>
    def execute(self, ctx: FrameContext):<br>
        gfx = ctx.graphics<br>
        window = ctx.window<br>
        viewport = ctx.viewport<br>
        px, py, pw, ph = ctx.rect<br>
        key = ctx.context_key<br>
<br>
        # Пытаемся взять FBO исходного ресурса<br>
        fb_in = ctx.fbos.get(self.src)<br>
<br>
        if fb_in is not None:<br>
            # inplace по сути: переиспользуем тот же FBO<br>
            fb_out = fb_in<br>
        else:<br>
            # src – внешний ресурс / никем не создан:<br>
            # делаем новый FBO под dst<br>
            fb_out = window.get_viewport_fbo(viewport, self.dst, (pw, ph))<br>
<br>
        # публикуем его под именем dst<br>
        ctx.fbos[self.dst] = fb_out<br>
<br>
        gfx.bind_framebuffer(fb_out)<br>
        gfx.set_viewport(0, 0, pw, ph)<br>
<br>
        # Ничего не чистим, не копируем: если там уже есть картинка —<br>
        # рисуем UI поверх неё.<br>
        if viewport.canvas:<br>
            viewport.canvas.render(gfx, key, (0, 0, pw, ph))<br>
<br>
<br>
<br>
<br>
from .components import MeshRenderer<br>
from .picking import id_to_rgb<br>
<br>
class IdPass(RenderFramePass):<br>
    def __init__(<br>
        self,<br>
        input_res: str = &quot;empty&quot;,<br>
        output_res: str = &quot;id&quot;,<br>
        pass_name: str = &quot;IdPass&quot;,<br>
    ):<br>
        super().__init__(<br>
            pass_name=pass_name,<br>
            reads={input_res},<br>
            writes={output_res},<br>
            inplace=True,<br>
        )<br>
        self.input_res = input_res<br>
        self.output_res = output_res<br>
<br>
    def execute(self, ctx: FrameContext):<br>
        gfx      = ctx.graphics<br>
        window   = ctx.window<br>
        viewport = ctx.viewport<br>
        scene    = viewport.scene<br>
        camera   = viewport.camera<br>
        px, py, pw, ph = ctx.rect<br>
        key      = ctx.context_key<br>
<br>
        fb = window.get_viewport_fbo(viewport, self.output_res, (pw, ph))<br>
        ctx.fbos[self.output_res] = fb<br>
<br>
        gfx.bind_framebuffer(fb)<br>
        gfx.set_viewport(0, 0, pw, ph)<br>
        gfx.clear_color_depth((0.0, 0.0, 0.0, 0.0))<br>
<br>
        pick_ids = {}<br>
        for ent in scene.entities:<br>
            if not ent.is_pickable():<br>
                continue<br>
<br>
            mr = ent.get_component(MeshRenderer)<br>
            if mr is None:<br>
                continue<br>
<br>
            pid = window._get_pick_id_for_entity(ent)<br>
            pick_ids[ent] = pid<br>
<br>
        window.renderer.render_viewport_pick(<br>
            scene,<br>
            camera,<br>
            (0, 0, pw, ph),<br>
            key,<br>
            pick_ids,<br>
        )<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
@dataclass<br>
class FrameContext:<br>
    window: &quot;Window&quot;<br>
    viewport: &quot;Viewport&quot;<br>
    rect: Tuple[int, int, int, int]<br>
    size: Tuple[int, int]<br>
    context_key: int<br>
    graphics: &quot;GraphicsBackend&quot;<br>
    fbos: Dict[str, Any] = field(default_factory=dict)<br>
<!-- END SCAT CODE -->
</body>
</html>
