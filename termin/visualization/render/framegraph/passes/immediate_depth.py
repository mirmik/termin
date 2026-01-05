"""
ImmediateDepthPass — renders depth-tested immediate geometry.

This pass renders lines and triangles that were added to ImmediateRenderer
with depth_test=True. It should be placed before UnifiedGizmoPass which
clears the depth buffer.
"""

from __future__ import annotations

from typing import List, Tuple, TYPE_CHECKING

from termin.visualization.render.framegraph.passes.base import RenderFramePass
from termin.visualization.render.immediate import ImmediateRenderer

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import GraphicsBackend
    from termin.visualization.render.framebuffer import FramebufferHandle


class ImmediateDepthPass(RenderFramePass):
    """
    Framegraph pass that renders depth-tested immediate geometry.

    Uses the same ImmediateRenderer singleton but flushes only the
    depth-tested buffers with depth test enabled.
    """

    def __init__(
        self,
        input_res: str = "color",
        output_res: str = "color",
        pass_name: str = "ImmediateDepthPass",
    ):
        super().__init__(
            pass_name=pass_name,
            reads={input_res},
            writes={output_res},
        )
        self.input_res = input_res
        self.output_res = output_res

    def get_inplace_aliases(self) -> List[Tuple[str, str]]:
        return [(self.input_res, self.output_res)]

    def execute(
        self,
        graphics: "GraphicsBackend",
        reads_fbos: dict[str, "FramebufferHandle | None"],
        writes_fbos: dict[str, "FramebufferHandle | None"],
        rect: tuple[int, int, int, int],
        scene,
        camera,
        context_key: int,
        lights=None,
        canvas=None,
    ):
        renderer = ImmediateRenderer.instance()
        if renderer is None:
            return

        # Check if there's anything to render
        if renderer.line_count_depth == 0 and renderer.triangle_count_depth == 0:
            return

        px, py, pw, ph = rect

        fb = writes_fbos.get(self.output_res)
        graphics.bind_framebuffer(fb)
        graphics.set_viewport(0, 0, pw, ph)

        view = camera.get_view_matrix()
        proj = camera.get_projection_matrix()

        # Flush depth-tested geometry with depth test enabled
        renderer.flush_depth(
            graphics=graphics,
            view_matrix=view,
            proj_matrix=proj,
            blend=True,
        )
