from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Tuple

import numpy as np

from .shader import ShaderProgram
from .backends.base import GraphicsBackend, FramebufferHandle, TextureHandle
from .framegraph import FrameContext, RenderFramePass, blit_fbo_to_fbo


class PostEffect:
    """
    Базовый интерфейс пост-эффекта.

    По умолчанию:
    - не требует дополнительных ресурсов (кроме основного color);
    - получает текущую color-текстуру и словарь extra_textures.
    """

    name: str = "unnamed_post_effect"

    def required_resources(self) -> set[str]:
        """
        Какие ресурсы (по именам FrameGraph) нужны этому эффекту,
        помимо основного input_res (обычно color).

        Например:
            {"id"}
            {"id", "depth"}
        и т.п.
        """
        return set()

    def draw(
        self,
        gfx: "GraphicsBackend",
        context_key: int,
        color_tex: "TextureHandle",
        extra_textures: dict[str, "TextureHandle"],
        size: tuple[int, int],
    ):
        """
        color_tex      – текущая цветовая текстура (что пришло с предыдущего шага).
        extra_textures – карта имя_ресурса -> TextureHandle (id, depth, normals...).
        size           – (width, height) целевого буфера.

        Эффект внутри сам:
        - биндит нужные текстуры по юнитам;
        - включает свой шейдер;
        - рисует фуллскрин-квад.
        """
        raise NotImplementedError



class PostProcessPass(RenderFramePass):
    def __init__(
        self,
        effects,
        input_res: str,
        output_res: str,
        pass_name: str = "PostProcess",
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
            # даём шанс и "старым" объектам, если вдруг не наследуются от PostEffect
            req = getattr(eff, "required_resources", None)
            if callable(req):
                reads |= set(req())

        super().__init__(
            pass_name=pass_name,
            reads=reads,
            writes={output_res},
            inplace=False,
        )

        self._temp_fbos: list["FramebufferHandle"] = []

    def _get_temp_fbo(self, ctx: "FrameContext", index: int, size: tuple[int, int]):
        gfx = ctx.graphics
        while len(self._temp_fbos) <= index:
            self._temp_fbos.append(gfx.create_framebuffer(size))
        fb = self._temp_fbos[index]
        fb.resize(size)
        return fb

    def rebuild_reads(self):
        """
        Вызывать, если ты поменял self.effects после создания пасса.
        Обновляет список ресурсов, которые пасс читает,
        чтобы FrameGraph учёл новые зависимости.
        """
        reads: set[str] = {self.input_res}
        for eff in self.effects:
            req = getattr(eff, "required_resources", None)
            if callable(req):
                reads |= set(req())
        self.reads = reads

    def execute(self, ctx: "FrameContext"):
        gfx      = ctx.graphics
        window   = ctx.window
        viewport = ctx.viewport
        px, py, pw, ph = ctx.rect
        key      = ctx.context_key

        size = (pw, ph)

        # основной входной FBO (color)
        fb_in = ctx.fbos.get(self.input_res)
        if fb_in is None:
            # ничего не рендерили в input_res — просто выходим
            return

        color_tex = fb_in.color_texture()

        # --- собираем extra_textures по запросам эффектов ---
        required_resources: set[str] = set()
        for eff in self.effects:
            req = getattr(eff, "required_resources", None)
            if callable(req):
                required_resources |= set(req())

        extra_textures: dict[str, "TextureHandle"] = {}
        for res_name in required_resources:
            fb = ctx.fbos.get(res_name)
            if fb is None:
                continue
            extra_textures[res_name] = fb.color_texture()

        # финальный FBO для выходного ресурса
        fb_out_final = window.get_viewport_fbo(viewport, self.output_res, size)
        ctx.fbos[self.output_res] = fb_out_final

        # --- кейс "нет эффектов" — просто блит и выходим ---
        if not self.effects:
            blit_fbo_to_fbo(gfx, fb_in, fb_out_final, size, key)
            return

        current_tex = color_tex

        # --- один эффект без пинг-понга ---
        if len(self.effects) == 1:
            effect = self.effects[0]
            gfx.bind_framebuffer(fb_out_final)
            gfx.set_viewport(0, 0, pw, ph)
            effect.draw(gfx, key, current_tex, extra_textures, size)
            return

        # --- несколько эффектов — пинг-понг ---
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

