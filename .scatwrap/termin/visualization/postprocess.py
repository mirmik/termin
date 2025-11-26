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
&#9;&quot;&quot;&quot;<br>
&#9;Базовый интерфейс пост-эффекта.<br>
<br>
&#9;По умолчанию:<br>
&#9;- не требует дополнительных ресурсов (кроме основного color);<br>
&#9;- получает текущую color-текстуру и словарь extra_textures.<br>
&#9;&quot;&quot;&quot;<br>
<br>
&#9;name: str = &quot;unnamed_post_effect&quot;<br>
<br>
&#9;def required_resources(self) -&gt; set[str]:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Какие ресурсы (по именам FrameGraph) нужны этому эффекту,<br>
&#9;&#9;помимо основного input_res (обычно color).<br>
<br>
&#9;&#9;Например:<br>
&#9;&#9;&#9;{&quot;id&quot;}<br>
&#9;&#9;&#9;{&quot;id&quot;, &quot;depth&quot;}<br>
&#9;&#9;и т.п.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;return set()<br>
<br>
&#9;def draw(<br>
&#9;&#9;self,<br>
&#9;&#9;gfx: &quot;GraphicsBackend&quot;,<br>
&#9;&#9;context_key: int,<br>
&#9;&#9;color_tex: &quot;TextureHandle&quot;,<br>
&#9;&#9;extra_textures: dict[str, &quot;TextureHandle&quot;],<br>
&#9;&#9;size: tuple[int, int],<br>
&#9;):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;color_tex      – текущая цветовая текстура (что пришло с предыдущего шага).<br>
&#9;&#9;extra_textures – карта имя_ресурса -&gt; TextureHandle (id, depth, normals...).<br>
&#9;&#9;size           – (width, height) целевого буфера.<br>
<br>
&#9;&#9;Эффект внутри сам:<br>
&#9;&#9;- биндит нужные текстуры по юнитам;<br>
&#9;&#9;- включает свой шейдер;<br>
&#9;&#9;- рисует фуллскрин-квад.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;raise NotImplementedError<br>
<br>
<br>
<br>
class PostProcessPass(RenderFramePass):<br>
&#9;def __init__(<br>
&#9;&#9;self,<br>
&#9;&#9;effects,<br>
&#9;&#9;input_res: str,<br>
&#9;&#9;output_res: str,<br>
&#9;&#9;pass_name: str = &quot;PostProcess&quot;,<br>
&#9;):<br>
&#9;&#9;# нормализуем список эффектов<br>
&#9;&#9;if not isinstance(effects, (list, tuple)):<br>
&#9;&#9;&#9;effects = [effects]<br>
&#9;&#9;self.effects = list(effects)<br>
<br>
&#9;&#9;self.input_res = input_res<br>
&#9;&#9;self.output_res = output_res<br>
<br>
&#9;&#9;# --- динамически собираем reads на основе эффектов ---<br>
&#9;&#9;reads: set[str] = {input_res}<br>
&#9;&#9;for eff in self.effects:<br>
&#9;&#9;&#9;# даём шанс и &quot;старым&quot; объектам, если вдруг не наследуются от PostEffect<br>
&#9;&#9;&#9;reads |= set(eff.required_resources())<br>
<br>
&#9;&#9;super().__init__(<br>
&#9;&#9;&#9;pass_name=pass_name,<br>
&#9;&#9;&#9;reads=reads,<br>
&#9;&#9;&#9;writes={output_res},<br>
&#9;&#9;&#9;inplace=False,<br>
&#9;&#9;)<br>
<br>
&#9;&#9;self._temp_fbos: list[&quot;FramebufferHandle&quot;] = []<br>
<br>
&#9;def _get_temp_fbo(self, ctx: &quot;FrameContext&quot;, index: int, size: tuple[int, int]):<br>
&#9;&#9;gfx = ctx.graphics<br>
&#9;&#9;while len(self._temp_fbos) &lt;= index:<br>
&#9;&#9;&#9;self._temp_fbos.append(gfx.create_framebuffer(size))<br>
&#9;&#9;fb = self._temp_fbos[index]<br>
&#9;&#9;fb.resize(size)<br>
&#9;&#9;return fb<br>
<br>
&#9;def rebuild_reads(self):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Вызывать, если ты поменял self.effects после создания пасса.<br>
&#9;&#9;Обновляет список ресурсов, которые пасс читает,<br>
&#9;&#9;чтобы FrameGraph учёл новые зависимости.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;reads: set[str] = {self.input_res}<br>
&#9;&#9;for eff in self.effects:<br>
&#9;&#9;&#9;reads |= set(eff.required_resources())<br>
&#9;&#9;self.reads = reads<br>
<br>
&#9;def add_effect(self, effect: PostEffect):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Добавляет эффект в конец цепочки.<br>
&#9;&#9;После вызова нужно вызвать rebuild_reads().<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;self.effects.append(effect)<br>
&#9;&#9;self.rebuild_reads()<br>
<br>
&#9;def execute(self, ctx: &quot;FrameContext&quot;):<br>
&#9;&#9;gfx      = ctx.graphics<br>
&#9;&#9;window   = ctx.window<br>
&#9;&#9;viewport = ctx.viewport<br>
&#9;&#9;px, py, pw, ph = ctx.rect<br>
&#9;&#9;key      = ctx.context_key<br>
<br>
&#9;&#9;size = (pw, ph)<br>
<br>
&#9;&#9;fb_in = ctx.fbos.get(self.input_res)<br>
&#9;&#9;if fb_in is None:<br>
&#9;&#9;&#9;return<br>
<br>
&#9;&#9;color_tex = fb_in.color_texture()<br>
<br>
&#9;&#9;# --- extra textures ---<br>
&#9;&#9;required_resources: set[str] = set()<br>
&#9;&#9;for eff in self.effects:<br>
&#9;&#9;&#9;req = getattr(eff, &quot;required_resources&quot;, None)<br>
&#9;&#9;&#9;if callable(req):<br>
&#9;&#9;&#9;&#9;required_resources |= set(req())<br>
<br>
&#9;&#9;extra_textures: dict[str, &quot;TextureHandle&quot;] = {}<br>
&#9;&#9;for res_name in required_resources:<br>
&#9;&#9;&#9;fb = ctx.fbos.get(res_name)<br>
&#9;&#9;&#9;if fb is None:<br>
&#9;&#9;&#9;&#9;continue<br>
&#9;&#9;&#9;extra_textures[res_name] = fb.color_texture()<br>
<br>
&#9;&#9;fb_out_final = window.get_viewport_fbo(viewport, self.output_res, size)<br>
&#9;&#9;ctx.fbos[self.output_res] = fb_out_final<br>
<br>
&#9;&#9;# --- нет эффектов -&gt; блит и выходим ---<br>
&#9;&#9;if not self.effects:<br>
&#9;&#9;&#9;blit_fbo_to_fbo(gfx, fb_in, fb_out_final, size, key)<br>
&#9;&#9;&#9;return<br>
<br>
&#9;&#9;current_tex = color_tex<br>
<br>
&#9;&#9;# &lt;&lt;&lt; ВАЖНО: постпроцесс — чисто экранная штука, отключаем глубину &gt;&gt;&gt;<br>
&#9;&#9;gfx.set_depth_test(False)<br>
&#9;&#9;gfx.set_depth_mask(False)<br>
<br>
<br>
&#9;&#9;try:<br>
&#9;&#9;&#9;if len(self.effects) == 1:<br>
&#9;&#9;&#9;&#9;effect = self.effects[0]<br>
&#9;&#9;&#9;&#9;gfx.bind_framebuffer(fb_out_final)<br>
&#9;&#9;&#9;&#9;gfx.set_viewport(0, 0, pw, ph)<br>
&#9;&#9;&#9;&#9;effect.draw(gfx, key, current_tex, extra_textures, size)<br>
&#9;&#9;&#9;&#9;return<br>
<br>
&#9;&#9;&#9;# несколько эффектов — пинг-понг<br>
&#9;&#9;&#9;for i, effect in enumerate(self.effects):<br>
&#9;&#9;&#9;&#9;is_last = (i == len(self.effects) - 1)<br>
<br>
&#9;&#9;&#9;&#9;if is_last:<br>
&#9;&#9;&#9;&#9;&#9;fb_target = fb_out_final<br>
&#9;&#9;&#9;&#9;else:<br>
&#9;&#9;&#9;&#9;&#9;fb_target = self._get_temp_fbo(ctx, i % 2, size)<br>
<br>
&#9;&#9;&#9;&#9;gfx.bind_framebuffer(fb_target)<br>
&#9;&#9;&#9;&#9;gfx.set_viewport(0, 0, pw, ph)<br>
<br>
&#9;&#9;&#9;&#9;effect.draw(gfx, key, current_tex, extra_textures, size)<br>
<br>
&#9;&#9;&#9;&#9;current_tex = fb_target.color_texture()<br>
&#9;&#9;finally:<br>
&#9;&#9;&#9;# восстанавливаем &quot;нормальное&quot; состояние для последующих пассов<br>
&#9;&#9;&#9;gfx.set_depth_test(True)<br>
&#9;&#9;&#9;gfx.set_depth_mask(True)<br>
<br>
<!-- END SCAT CODE -->
</body>
</html>
