from __future__ import annotations

from termin.visualization.framegraph.context import FrameContext
from termin.visualization.framegraph.passes.base import RenderFramePass


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

        fb_out = ctx.fbos.get(self.dst)
        gfx.bind_framebuffer(fb_out)
        gfx.set_viewport(0, 0, pw, ph)

        if viewport.canvas:
            viewport.canvas.render(gfx, key, (0, 0, pw, ph))
