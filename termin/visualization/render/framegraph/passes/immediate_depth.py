"""
ImmediateDepthPass — renders depth-tested immediate geometry.

This pass renders lines and triangles that were added to ImmediateRenderer
with depth_test=True. It should be placed before UnifiedGizmoPass which
clears the depth buffer.
"""

from __future__ import annotations

from typing import List, Set, Tuple, TYPE_CHECKING

from termin.visualization.render.framegraph.passes.base import RenderFramePass
from termin.visualization.render.immediate import ImmediateRenderer
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import GraphicsBackend
    from termin.visualization.render.framebuffer import FramebufferHandle
    from termin.visualization.render.framegraph.execute_context import ExecuteContext


class ImmediateDepthPass(RenderFramePass):
    """
    Framegraph pass that renders depth-tested immediate geometry.

    Uses the same ImmediateRenderer singleton but flushes only the
    depth-tested buffers with depth test enabled.
    """

    category = "Debug"

    node_inputs = [("input_res", "fbo")]
    node_outputs = [("output_res", "fbo")]
    node_inplace_pairs = [("input_res", "output_res")]

    inspect_fields = {
        "input_res": InspectField(path="input_res", label="Input Resource", kind="string"),
        "output_res": InspectField(path="output_res", label="Output Resource", kind="string"),
    }

    def __init__(
        self,
        input_res: str = "color",
        output_res: str = "color",
        pass_name: str = "ImmediateDepthPass",
    ):
        super().__init__(pass_name=pass_name)
        self.input_res = input_res
        self.output_res = output_res

    def compute_reads(self) -> Set[str]:
        return {self.input_res}

    def compute_writes(self) -> Set[str]:
        return {self.output_res}

    def get_inplace_aliases(self) -> List[Tuple[str, str]]:
        return [(self.input_res, self.output_res)]

    def execute(self, ctx: "ExecuteContext") -> None:
        from termin._native import log

        renderer = ImmediateRenderer.instance()
        if renderer is None:
            return

        line_count = renderer.line_count_depth
        tri_count = renderer.triangle_count_depth

        # Check if there's anything to render
        if line_count == 0 and tri_count == 0:
            log.debug(f"[ImmediateDepthPass] No depth geometry to render, skipping")
            return

        log.debug(f"[ImmediateDepthPass] Rendering {line_count} lines, {tri_count} triangles")

        px, py, pw, ph = ctx.rect

        fb = ctx.writes_fbos.get(self.output_res)
        if fb is None:
            log.warn(f"[ImmediateDepthPass] output '{self.output_res}' is None")
            return

        # Check type - must be FramebufferHandle
        from termin.graphics import FramebufferHandle
        if not isinstance(fb, FramebufferHandle):
            log.warn(f"[ImmediateDepthPass] output '{self.output_res}' is {type(fb).__name__}, not FramebufferHandle")
            return

        log.debug(f"[ImmediateDepthPass] Binding FBO for '{self.output_res}', size={fb.get_size()}")

        ctx.graphics.bind_framebuffer(fb)
        ctx.graphics.set_viewport(0, 0, pw, ph)

        view = ctx.camera.get_view_matrix()
        proj = ctx.camera.get_projection_matrix()

        # Flush depth-tested geometry with depth test enabled
        renderer.flush_depth(
            graphics=ctx.graphics,
            view_matrix=view,
            proj_matrix=proj,
            blend=True,
        )
        log.debug(f"[ImmediateDepthPass] Done")
