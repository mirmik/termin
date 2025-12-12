from __future__ import annotations

from typing import List, Tuple

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
        )
        self.src = src
        self.dst = dst

    def _serialize_params(self) -> dict:
        """Сериализует параметры CanvasPass."""
        return {
            "src": self.src,
            "dst": self.dst,
        }

    @classmethod
    def _deserialize_instance(cls, data: dict, resource_manager=None) -> "CanvasPass":
        """Создаёт CanvasPass из сериализованных данных."""
        return cls(
            src=data.get("src", "screen"),
            dst=data.get("dst", "screen+ui"),
            pass_name=data.get("pass_name", "Canvas"),
        )

    def get_inplace_aliases(self) -> List[Tuple[str, str]]:
        """CanvasPass читает src и пишет dst inplace."""
        return [(self.src, self.dst)]

    def execute(
        self,
        graphics: "GraphicsBackend",
        reads_fbos: dict[str, "FramebufferHandle" | None],
        writes_fbos: dict[str, "FramebufferHandle" | None],
        rect: tuple[int, int, int, int],
        scene=None,
        camera=None,
        canvas=None,
        context_key: int = 0,
        lights=None,
    ):
        px, py, pw, ph = rect

        fb_out = writes_fbos.get(self.dst)
        graphics.bind_framebuffer(fb_out)
        graphics.set_viewport(0, 0, pw, ph)

        if canvas:
            canvas.render(graphics, context_key, (0, 0, pw, ph))
