<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/postprocess.py</title>
</head>
<body>
<pre><code>
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Tuple

import numpy as np

from .shader import ShaderProgram
from .backends.base import GraphicsBackend, FramebufferHandle, TextureHandle
from .framegraph import FrameContext, RenderFramePass, blit_fbo_to_fbo


class PostEffect:
    &quot;&quot;&quot;
    Базовый интерфейс пост-эффекта.

    По умолчанию:
    - не требует дополнительных ресурсов (кроме основного color);
    - получает текущую color-текстуру и словарь extra_textures.
    &quot;&quot;&quot;

    name: str = &quot;unnamed_post_effect&quot;

    def required_resources(self) -&gt; set[str]:
        &quot;&quot;&quot;
        Какие ресурсы (по именам FrameGraph) нужны этому эффекту,
        помимо основного input_res (обычно color).

        Например:
            {&quot;id&quot;}
            {&quot;id&quot;, &quot;depth&quot;}
        и т.п.
        &quot;&quot;&quot;
        return set()

    def draw(
        self,
        gfx: &quot;GraphicsBackend&quot;,
        context_key: int,
        color_tex: &quot;TextureHandle&quot;,
        extra_textures: dict[str, &quot;TextureHandle&quot;],
        size: tuple[int, int],
    ):
        &quot;&quot;&quot;
        color_tex      – текущая цветовая текстура (что пришло с предыдущего шага).
        extra_textures – карта имя_ресурса -&gt; TextureHandle (id, depth, normals...).
        size           – (width, height) целевого буфера.

        Эффект внутри сам:
        - биндит нужные текстуры по юнитам;
        - включает свой шейдер;
        - рисует фуллскрин-квад.
        &quot;&quot;&quot;
        raise NotImplementedError



class PostProcessPass(RenderFramePass):
    def __init__(
        self,
        effects,
        input_res: str,
        output_res: str,
        pass_name: str = &quot;PostProcess&quot;,
    ):
        # нормализуем список эффектов
        if not isinstance(effects, (list, tuple)):
            effects = [effects]
        self.effects = list(effects)

        self.input_res = input_res
        self.output_res = output_res

        # --- динамически собираем reads на основе эффектов ---
        reads: set[str] = {input_res}
        for eff in self.effects:
            # даём шанс и &quot;старым&quot; объектам, если вдруг не наследуются от PostEffect
            reads |= set(eff.required_resources())

        super().__init__(
            pass_name=pass_name,
            reads=reads,
            writes={output_res},
            inplace=False,
        )

        self._temp_fbos: list[&quot;FramebufferHandle&quot;] = []

    def _get_temp_fbo(self, ctx: &quot;FrameContext&quot;, index: int, size: tuple[int, int]):
        gfx = ctx.graphics
        while len(self._temp_fbos) &lt;= index:
            self._temp_fbos.append(gfx.create_framebuffer(size))
        fb = self._temp_fbos[index]
        fb.resize(size)
        return fb

    def rebuild_reads(self):
        &quot;&quot;&quot;
        Вызывать, если ты поменял self.effects после создания пасса.
        Обновляет список ресурсов, которые пасс читает,
        чтобы FrameGraph учёл новые зависимости.
        &quot;&quot;&quot;
        reads: set[str] = {self.input_res}
        for eff in self.effects:
            reads |= set(eff.required_resources())
        self.reads = reads

    def add_effect(self, effect: PostEffect):
        &quot;&quot;&quot;
        Добавляет эффект в конец цепочки.
        После вызова нужно вызвать rebuild_reads().
        &quot;&quot;&quot;
        self.effects.append(effect)
        self.rebuild_reads()

    def execute(self, ctx: &quot;FrameContext&quot;):
        gfx      = ctx.graphics
        window   = ctx.window
        viewport = ctx.viewport
        px, py, pw, ph = ctx.rect
        key      = ctx.context_key

        size = (pw, ph)

        fb_in = ctx.fbos.get(self.input_res)
        if fb_in is None:
            return

        color_tex = fb_in.color_texture()

        # --- extra textures ---
        required_resources: set[str] = set()
        for eff in self.effects:
            req = getattr(eff, &quot;required_resources&quot;, None)
            if callable(req):
                required_resources |= set(req())

        extra_textures: dict[str, &quot;TextureHandle&quot;] = {}
        for res_name in required_resources:
            fb = ctx.fbos.get(res_name)
            if fb is None:
                continue
            extra_textures[res_name] = fb.color_texture()

        fb_out_final = window.get_viewport_fbo(viewport, self.output_res, size)
        ctx.fbos[self.output_res] = fb_out_final

        # --- нет эффектов -&gt; блит и выходим ---
        if not self.effects:
            blit_fbo_to_fbo(gfx, fb_in, fb_out_final, size, key)
            return

        current_tex = color_tex

        # &lt;&lt;&lt; ВАЖНО: постпроцесс — чисто экранная штука, отключаем глубину &gt;&gt;&gt;
        gfx.set_depth_test(False)
        gfx.set_depth_mask(False)


        try:
            if len(self.effects) == 1:
                effect = self.effects[0]
                gfx.bind_framebuffer(fb_out_final)
                gfx.set_viewport(0, 0, pw, ph)
                effect.draw(gfx, key, current_tex, extra_textures, size)
                return

            # несколько эффектов — пинг-понг
            for i, effect in enumerate(self.effects):
                is_last = (i == len(self.effects) - 1)

                if is_last:
                    fb_target = fb_out_final
                else:
                    fb_target = self._get_temp_fbo(ctx, i % 2, size)

                gfx.bind_framebuffer(fb_target)
                gfx.set_viewport(0, 0, pw, ph)

                effect.draw(gfx, key, current_tex, extra_textures, size)

                current_tex = fb_target.color_texture()
        finally:
            # восстанавливаем &quot;нормальное&quot; состояние для последующих пассов
            gfx.set_depth_test(True)
            gfx.set_depth_mask(True)


</code></pre>
</body>
</html>
