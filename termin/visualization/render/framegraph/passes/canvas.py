from __future__ import annotations

from termin.visualization.render.framegraph.passes.base import RenderFramePass


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

    def execute(
        self,
        graphics: "GraphicsBackend",
        *,
        fbos: dict[str, "FramebufferHandle" | None],
        rect: tuple[int, int, int, int],
        canvas=None,
        context_key: int,
        **_,
    ):
        px, py, pw, ph = rect

        fb_out = fbos.get(self.dst)
        graphics.bind_framebuffer(fb_out)
        graphics.set_viewport(0, 0, pw, ph)

        if canvas:
            canvas.render(graphics, context_key, (0, 0, pw, ph))
