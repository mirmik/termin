# termin/visualization/framegraph.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Set, Any, Optional, Tuple
from collections import deque
from termin.visualization.shader import ShaderProgram
from .picking import rgb_to_id
from .components import MeshRenderer


@dataclass
class FramePass:
    """
    Логический проход кадра.

    reads  – какие ресурсы этот проход читает (по именам).
    writes – какие ресурсы он пишет.
    inplace – модифицирующий ли это проход (in-place по смыслу).
    """
    pass_name: str
    reads: Set[str] = field(default_factory=set)
    writes: Set[str] = field(default_factory=set)
    inplace: bool = False

    def __repr__(self) -> str:
        return f"FramePass({self.pass_name!r})"


class FrameGraphError(Exception):
    """Базовая ошибка графа кадра."""


class FrameGraphMultiWriterError(FrameGraphError):
    """Один и тот же ресурс пишут несколько пассов."""


class FrameGraphCycleError(FrameGraphError):
    """В графе зависимостей обнаружен цикл."""


class FrameGraph:
    """
    Простейший frame graph: на вход – набор FramePass,
    на выход – топологически отсортированный список пассов.
    """

    def __init__(self, passes: Iterable[FramePass]):
        self._passes: List[FramePass] = list(passes)
        # карта "ресурс -> каноническое имя" (на будущее — для дебага / инспекции)
        self._canonical_resources: Dict[str, str] = {}

    # ------------------------------------------------------------------ #
    # ВНУТРЕННЕЕ ПРЕДСТАВЛЕНИЕ ГРАФА ЗАВИСИМОСТЕЙ
    # ------------------------------------------------------------------ #
    # Всё строим на ИНДЕКСАХ пассов (0..N-1), а не на самих объектах,
    # чтобы вообще не зависеть от их hash/eq.
    # ------------------------------------------------------------------ #

    def _build_dependency_graph(self):
        """
        Строит граф зависимостей между пассами.

        Возвращает:
            adjacency: dict[int, list[int]]
                для каждого индекса пасса – список индексов пассов,
                которые зависят от него (есть ребро writer -> reader).
            in_degree: dict[int, int]
                количество входящих рёбер для каждого пасса.
        """
        writer_for: Dict[str, int] = {}          # ресурс -> индекс писателя
        readers_for: Dict[str, List[int]] = {}   # ресурс -> список индексов читателей

        # для in-place логики
        modified_inputs: Set[str] = set()        # какие имена уже были входом inplace-пасса
        canonical: Dict[str, str] = {}           # локальная карта канонических имён

        n = len(self._passes)

        # 1) собираем writer-ов, reader-ов и валидируем inplace-пассы
        for idx, p in enumerate(self._passes):
            # --- валидация inplace-пассов ---
            if p.inplace:
                if len(p.reads) != 1 or len(p.writes) != 1:
                    raise FrameGraphError(
                        f"Inplace pass {p.pass_name!r} must have exactly 1 read and 1 write, "
                        f"got reads={p.reads}, writes={p.writes}"
                    )
                (src,) = p.reads
                if src in modified_inputs:
                    # этот ресурс уже модифицировался другим inplace-пассом
                    raise FrameGraphError(
                        f"Resource {src!r} is already modified by another inplace pass"
                    )
                modified_inputs.add(src)

            # --- writer-ы ---
            for res in p.writes:
                if res in writer_for:
                    other_idx = writer_for[res]
                    other = self._passes[other_idx]
                    raise FrameGraphMultiWriterError(
                        f"Resource {res!r} is written by multiple passes: "
                        f"{other.pass_name!r} and {p.pass_name!r}"
                    )
                writer_for[res] = idx

                # каноническое имя: первое появление ресурса как writer
                canonical.setdefault(res, res)

            # --- reader-ы ---
            for res in p.reads:
                lst = readers_for.setdefault(res, [])
                if idx not in lst:
                    lst.append(idx)
                # если ресурс нигде не писали, но читают — считаем внешним входом
                canonical.setdefault(res, res)

        # 2) обработка алиасов для inplace-пассов
        # (это чисто справочная штука, на граф зависимостей не влияет)
        for p in self._passes:
            if not p.inplace:
                continue
            (src,) = p.reads
            (dst,) = p.writes

            src_canon = canonical.get(src, src)
            # выходу назначаем каноническое имя входа:
            # даже если у dst уже было "своё", переопределяем —
            # мы сознательно объявляем их синонимами.
            canonical[dst] = src_canon

        # сохраним карту канонических имён (вдруг пригодится снаружи)
        self._canonical_resources = canonical

        # 3) adjacency и in_degree по индексам
        adjacency: Dict[int, List[int]] = {i: [] for i in range(n)}
        in_degree: Dict[int, int] = {i: 0 for i in range(n)}

        # Для каждого ресурса: writer -> все его reader-ы
        for res, w_idx in writer_for.items():
            for r_idx in readers_for.get(res, ()):
                if r_idx == w_idx:
                    continue  # на всякий случай, не создаём петли writer->writer
                if r_idx not in adjacency[w_idx]:
                    adjacency[w_idx].append(r_idx)
                    in_degree[r_idx] += 1

        return adjacency, in_degree

    # ------------------------------------------------------------------ #
    # ТОПОЛОГИЧЕСКАЯ СОРТИРОВКА (Kahn с приоритетом обычных пассов)
    # ------------------------------------------------------------------ #

    def build_schedule(self) -> List[FramePass]:
        """
        Возвращает список пассов в порядке выполнения,
        учитывая зависимости read-after-write.

        Бросает:
            - FrameGraphMultiWriterError, если один ресурс пишут несколько пассов.
            - FrameGraphCycleError, если обнаружен цикл.
            - FrameGraphError, если нарушены правила inplace-пассов.
        """
        adjacency, in_degree = self._build_dependency_graph()
        n = len(self._passes)

        is_inplace = [p.inplace for p in self._passes]

        # две очереди:
        #   обычные пассы — в ready_normal
        #   inplace-пассы — в ready_inplace
        ready_normal: deque[int] = deque()
        ready_inplace: deque[int] = deque()

        for i in range(n):
            if in_degree[i] == 0:
                if is_inplace[i]:
                    ready_inplace.append(i)
                else:
                    ready_normal.append(i)

        schedule_indices: List[int] = []

        while ready_normal or ready_inplace:
            # приоритет обычных пассов
            if ready_normal:
                idx = ready_normal.popleft()
            else:
                idx = ready_inplace.popleft()

            schedule_indices.append(idx)

            for dep in adjacency[idx]:
                in_degree[dep] -= 1
                if in_degree[dep] == 0:
                    if is_inplace[dep]:
                        ready_inplace.append(dep)
                    else:
                        ready_normal.append(dep)

        if len(schedule_indices) != n:
            # Остались вершины с in_degree > 0 → цикл
            problematic = [self._passes[i].pass_name for i, deg in in_degree.items() if deg > 0]
            raise FrameGraphCycleError(
                "Frame graph contains a dependency cycle involving passes: "
                + ", ".join(problematic)
            )

        # Конвертируем индексы обратно в реальные пассы
        return [self._passes[i] for i in schedule_indices]

    # опционально — геттер канонического имени ресурса (на будущее)
    def canonical_resource(self, name: str) -> str:
        return self._canonical_resources.get(name, name)

@dataclass
class FrameExecutionContext:
    graphics: GraphicsBackend
    window: "Window"
    viewport: "Viewport"
    rect: Tuple[int, int, int, int]  # (px, py, pw, ph)
    context_key: int

    # карта ресурс -> FBO (или None, если это swapchain/экран)
    fbos: Dict[str, FramebufferHandle | None]

class RenderFramePass(FramePass):
    def execute(self, ctx: FrameExecutionContext):
        raise NotImplementedError


class ColorPass(RenderFramePass):
    def __init__(
        self,
        input_res: str = "empty",
        output_res: str = "color",
        pass_name: str = "Color",
    ):
        super().__init__(
            pass_name=pass_name,
            reads={input_res},
            writes={output_res},
            inplace=True,  # логически — модификатор состояния ресурса
        )
        self.input_res = input_res
        self.output_res = output_res

    def execute(self, ctx: FrameContext):
        gfx      = ctx.graphics
        window   = ctx.window
        viewport = ctx.viewport
        scene    = viewport.scene
        camera   = viewport.camera
        px, py, pw, ph = ctx.rect
        key      = ctx.context_key

        fb = window.get_viewport_fbo(viewport, self.output_res, (pw, ph))
        ctx.fbos[self.output_res] = fb

        gfx.bind_framebuffer(fb)
        gfx.set_viewport(0, 0, pw, ph)
        gfx.clear_color_depth(scene.background_color)

        window.renderer.render_viewport(
            scene,
            camera,
            (0, 0, pw, ph),
            key,
        )



def blit_fbo_to_fbo(
    gfx: "GraphicsBackend",
    src_fb,
    dst_fb,
    size: tuple[int, int],
    context_key: int,
):
    w, h = size

    # целевой FBO
    gfx.bind_framebuffer(dst_fb)
    gfx.set_viewport(0, 0, w, h)

    # глубина нам не нужна
    gfx.set_depth_test(False)
    gfx.set_depth_mask(False)

    # берём ту же фуллскрин-квад-программу, что и PresentToScreenPass
    shader = PresentToScreenPass._get_shader()
    shader.ensure_ready(gfx)
    shader.use()
    shader.set_uniform_int("u_tex", 0)

    tex = src_fb.color_texture()
    tex.bind(0)

    gfx.draw_ui_textured_quad(context_key)

    gfx.set_depth_test(True)
    gfx.set_depth_mask(True)





FSQ_VERT = """
#version 330 core
layout(location = 0) in vec2 a_pos;
layout(location = 1) in vec2 a_uv;

out vec2 v_uv;

void main() {
    v_uv = a_uv;
    gl_Position = vec4(a_pos, 0.0, 1.0);
}
"""

FSQ_FRAG = """
#version 330 core
in vec2 v_uv;
out vec4 FragColor;

uniform sampler2D u_tex;

void main() {
    FragColor = texture(u_tex, v_uv);
}
"""


class PresentToScreenPass(RenderFramePass):
    """
    Берёт текстуру из ресурса input_res и выводит её на экран
    фуллскрин-квадом.
    """
    _shader: ShaderProgram | None = None

    def __init__(self, input_res: str, pass_name: str = "PresentToScreen"):
        super().__init__(
            pass_name=pass_name,
            reads={input_res},
            writes=set(),  # экран считаем внешним
            inplace=False,
        )
        self.input_res = input_res

    @classmethod
    def _get_shader(cls) -> ShaderProgram:
        if cls._shader is None:
            cls._shader = ShaderProgram(FSQ_VERT, FSQ_FRAG)
        return cls._shader

    def execute(self, ctx: FrameContext):
        gfx = ctx.graphics
        window = ctx.window
        px, py, pw, ph = ctx.rect
        key = ctx.context_key

        fb_in = ctx.fbos.get(self.input_res)
        if fb_in is None:
            return

        tex_in = fb_in.color_texture()

        window.handle.bind_window_framebuffer()
        gfx.set_viewport(px, py, pw, ph)

        gfx.set_depth_test(False)
        gfx.set_depth_mask(False)

        shader = self._get_shader()
        shader.ensure_ready(gfx)
        shader.use()
        shader.set_uniform_int("u_tex", 0)

        tex_in.bind(0)

        gfx.draw_ui_textured_quad(key)

        gfx.set_depth_test(True)
        gfx.set_depth_mask(True)


class CanvasPass(RenderFramePass):
    def __init__(
        self,
        src: str = "screen",
        dst: str = "screen+ui",
        pass_name: str = "Canvas",
    ):
        super().__init__(
            pass_name=pass_name,
            reads={src},
            writes={dst},
            inplace=True,  # <- ключевое: модифицирующий пасс
        )
        self.src = src
        self.dst = dst

    def execute(self, ctx: FrameContext):
        gfx = ctx.graphics
        window = ctx.window
        viewport = ctx.viewport
        px, py, pw, ph = ctx.rect
        key = ctx.context_key

        # Пытаемся взять FBO исходного ресурса
        fb_in = ctx.fbos.get(self.src)

        if fb_in is not None:
            # inplace по сути: переиспользуем тот же FBO
            fb_out = fb_in
        else:
            # src – внешний ресурс / никем не создан:
            # делаем новый FBO под dst
            fb_out = window.get_viewport_fbo(viewport, self.dst, (pw, ph))

        # публикуем его под именем dst
        ctx.fbos[self.dst] = fb_out

        gfx.bind_framebuffer(fb_out)
        gfx.set_viewport(0, 0, pw, ph)

        # Ничего не чистим, не копируем: если там уже есть картинка —
        # рисуем UI поверх неё.
        if viewport.canvas:
            viewport.canvas.render(gfx, key, (0, 0, pw, ph))




from .components import MeshRenderer
from .picking import id_to_rgb

class IdPass(RenderFramePass):
    def __init__(
        self,
        input_res: str = "empty",
        output_res: str = "id",
        pass_name: str = "IdPass",
    ):
        super().__init__(
            pass_name=pass_name,
            reads={input_res},
            writes={output_res},
            inplace=True,
        )
        self.input_res = input_res
        self.output_res = output_res

    def execute(self, ctx: FrameContext):
        gfx      = ctx.graphics
        window   = ctx.window
        viewport = ctx.viewport
        scene    = viewport.scene
        camera   = viewport.camera
        px, py, pw, ph = ctx.rect
        key      = ctx.context_key

        fb = window.get_viewport_fbo(viewport, self.output_res, (pw, ph))
        ctx.fbos[self.output_res] = fb

        gfx.bind_framebuffer(fb)
        gfx.set_viewport(0, 0, pw, ph)
        gfx.clear_color_depth((0.0, 0.0, 0.0, 0.0))

        pick_ids = {}
        for ent in scene.entities:
            if not ent.is_pickable():
                continue

            mr = ent.get_component(MeshRenderer)
            if mr is None:
                continue

            pid = window._get_pick_id_for_entity(ent)
            pick_ids[ent] = pid

        window.renderer.render_viewport_pick(
            scene,
            camera,
            (0, 0, pw, ph),
            key,
            pick_ids,
        )







@dataclass
class FrameContext:
    window: "Window"
    viewport: "Viewport"
    rect: Tuple[int, int, int, int]
    size: Tuple[int, int]
    context_key: int
    graphics: "GraphicsBackend"
    fbos: Dict[str, Any] = field(default_factory=dict)