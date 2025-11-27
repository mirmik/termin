from __future__ import annotations

from termin.visualization.framegraph.context import FrameContext
from termin.visualization.framegraph.passes.base import RenderFramePass


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
        gfx = ctx.graphics
        window = ctx.window
        viewport = ctx.viewport
        scene = viewport.scene
        camera = viewport.camera
        px, py, pw, ph = ctx.rect
        key = ctx.context_key

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
