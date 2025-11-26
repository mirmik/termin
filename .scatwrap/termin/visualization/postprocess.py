<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/postprocess.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
from __future__ import annotations<br>
<br>
from dataclasses import dataclass, field<br>
from typing import Dict, Tuple<br>
<br>
import numpy as np<br>
<br>
from .shader import ShaderProgram<br>
from .backends.base import GraphicsBackend, FramebufferHandle, TextureHandle<br>
from .framegraph import FrameContext, RenderFramePass, blit_fbo_to_fbo<br>
<br>
<br>
class PostEffect:<br>
    &quot;&quot;&quot;<br>
    Базовый интерфейс пост-эффекта.<br>
<br>
    По умолчанию:<br>
    - не требует дополнительных ресурсов (кроме основного color);<br>
    - получает текущую color-текстуру и словарь extra_textures.<br>
    &quot;&quot;&quot;<br>
<br>
    name: str = &quot;unnamed_post_effect&quot;<br>
<br>
    def required_resources(self) -&gt; set[str]:<br>
        &quot;&quot;&quot;<br>
        Какие ресурсы (по именам FrameGraph) нужны этому эффекту,<br>
        помимо основного input_res (обычно color).<br>
<br>
        Например:<br>
            {&quot;id&quot;}<br>
            {&quot;id&quot;, &quot;depth&quot;}<br>
        и т.п.<br>
        &quot;&quot;&quot;<br>
        return set()<br>
<br>
    def draw(<br>
        self,<br>
        gfx: &quot;GraphicsBackend&quot;,<br>
        context_key: int,<br>
        color_tex: &quot;TextureHandle&quot;,<br>
        extra_textures: dict[str, &quot;TextureHandle&quot;],<br>
        size: tuple[int, int],<br>
    ):<br>
        &quot;&quot;&quot;<br>
        color_tex      – текущая цветовая текстура (что пришло с предыдущего шага).<br>
        extra_textures – карта имя_ресурса -&gt; TextureHandle (id, depth, normals...).<br>
        size           – (width, height) целевого буфера.<br>
<br>
        Эффект внутри сам:<br>
        - биндит нужные текстуры по юнитам;<br>
        - включает свой шейдер;<br>
        - рисует фуллскрин-квад.<br>
        &quot;&quot;&quot;<br>
        raise NotImplementedError<br>
<br>
<br>
<br>
class PostProcessPass(RenderFramePass):<br>
    def __init__(<br>
        self,<br>
        effects,<br>
        input_res: str,<br>
        output_res: str,<br>
        pass_name: str = &quot;PostProcess&quot;,<br>
    ):<br>
        # нормализуем список эффектов<br>
        if not isinstance(effects, (list, tuple)):<br>
            effects = [effects]<br>
        self.effects = list(effects)<br>
<br>
        self.input_res = input_res<br>
        self.output_res = output_res<br>
<br>
        # --- динамически собираем reads на основе эффектов ---<br>
        reads: set[str] = {input_res}<br>
        for eff in self.effects:<br>
            # даём шанс и &quot;старым&quot; объектам, если вдруг не наследуются от PostEffect<br>
            reads |= set(eff.required_resources())<br>
<br>
        super().__init__(<br>
            pass_name=pass_name,<br>
            reads=reads,<br>
            writes={output_res},<br>
            inplace=False,<br>
        )<br>
<br>
        self._temp_fbos: list[&quot;FramebufferHandle&quot;] = []<br>
<br>
    def _get_temp_fbo(self, ctx: &quot;FrameContext&quot;, index: int, size: tuple[int, int]):<br>
        gfx = ctx.graphics<br>
        while len(self._temp_fbos) &lt;= index:<br>
            self._temp_fbos.append(gfx.create_framebuffer(size))<br>
        fb = self._temp_fbos[index]<br>
        fb.resize(size)<br>
        return fb<br>
<br>
    def rebuild_reads(self):<br>
        &quot;&quot;&quot;<br>
        Вызывать, если ты поменял self.effects после создания пасса.<br>
        Обновляет список ресурсов, которые пасс читает,<br>
        чтобы FrameGraph учёл новые зависимости.<br>
        &quot;&quot;&quot;<br>
        reads: set[str] = {self.input_res}<br>
        for eff in self.effects:<br>
            reads |= set(eff.required_resources())<br>
        self.reads = reads<br>
<br>
    def add_effect(self, effect: PostEffect):<br>
        &quot;&quot;&quot;<br>
        Добавляет эффект в конец цепочки.<br>
        После вызова нужно вызвать rebuild_reads().<br>
        &quot;&quot;&quot;<br>
        self.effects.append(effect)<br>
        self.rebuild_reads()<br>
<br>
    def execute(self, ctx: &quot;FrameContext&quot;):<br>
        gfx      = ctx.graphics<br>
        window   = ctx.window<br>
        viewport = ctx.viewport<br>
        px, py, pw, ph = ctx.rect<br>
        key      = ctx.context_key<br>
<br>
        size = (pw, ph)<br>
<br>
        fb_in = ctx.fbos.get(self.input_res)<br>
        if fb_in is None:<br>
            return<br>
<br>
        color_tex = fb_in.color_texture()<br>
<br>
        # --- extra textures ---<br>
        required_resources: set[str] = set()<br>
        for eff in self.effects:<br>
            req = getattr(eff, &quot;required_resources&quot;, None)<br>
            if callable(req):<br>
                required_resources |= set(req())<br>
<br>
        extra_textures: dict[str, &quot;TextureHandle&quot;] = {}<br>
        for res_name in required_resources:<br>
            fb = ctx.fbos.get(res_name)<br>
            if fb is None:<br>
                continue<br>
            extra_textures[res_name] = fb.color_texture()<br>
<br>
        fb_out_final = window.get_viewport_fbo(viewport, self.output_res, size)<br>
        ctx.fbos[self.output_res] = fb_out_final<br>
<br>
        # --- нет эффектов -&gt; блит и выходим ---<br>
        if not self.effects:<br>
            blit_fbo_to_fbo(gfx, fb_in, fb_out_final, size, key)<br>
            return<br>
<br>
        current_tex = color_tex<br>
<br>
        # &lt;&lt;&lt; ВАЖНО: постпроцесс — чисто экранная штука, отключаем глубину &gt;&gt;&gt;<br>
        gfx.set_depth_test(False)<br>
        gfx.set_depth_mask(False)<br>
<br>
<br>
        try:<br>
            if len(self.effects) == 1:<br>
                effect = self.effects[0]<br>
                gfx.bind_framebuffer(fb_out_final)<br>
                gfx.set_viewport(0, 0, pw, ph)<br>
                effect.draw(gfx, key, current_tex, extra_textures, size)<br>
                return<br>
<br>
            # несколько эффектов — пинг-понг<br>
            for i, effect in enumerate(self.effects):<br>
                is_last = (i == len(self.effects) - 1)<br>
<br>
                if is_last:<br>
                    fb_target = fb_out_final<br>
                else:<br>
                    fb_target = self._get_temp_fbo(ctx, i % 2, size)<br>
<br>
                gfx.bind_framebuffer(fb_target)<br>
                gfx.set_viewport(0, 0, pw, ph)<br>
<br>
                effect.draw(gfx, key, current_tex, extra_textures, size)<br>
<br>
                current_tex = fb_target.color_texture()<br>
        finally:<br>
            # восстанавливаем &quot;нормальное&quot; состояние для последующих пассов<br>
            gfx.set_depth_test(True)<br>
            gfx.set_depth_mask(True)<br>
<br>
<!-- END SCAT CODE -->
</body>
</html>
