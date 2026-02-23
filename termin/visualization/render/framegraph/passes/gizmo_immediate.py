"""
ImmediateGizmoPass - Renders transform gizmo using immediate mode rendering.

This pass renders the gizmo on top of the scene (no depth test) using
ImmediateGizmoRenderer, with mathematical raycast picking instead of ID buffer.
"""

from __future__ import annotations

from typing import Callable, List, Set, Tuple, TYPE_CHECKING

from termin.visualization.render.framegraph.passes.base import RenderFramePass
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.editor.gizmo_immediate import ImmediateGizmoRenderer
    from tgfx import GraphicsBackend
    from termin.visualization.render.framebuffer import FramebufferHandle
    from termin.visualization.render.framegraph.execute_context import ExecuteContext


class ImmediateGizmoPass(RenderFramePass):
    """
    Framegraph pass that renders the transform gizmo using immediate mode.

    Unlike the entity-based GizmoPass, this doesn't write to the ID buffer.
    Picking is handled separately via mathematical raycast.
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
        gizmo_renderer: "ImmediateGizmoRenderer | Callable[[], ImmediateGizmoRenderer | None] | None" = None,
        input_res: str = "color",
        output_res: str = "color",
        pass_name: str = "ImmediateGizmoPass",
    ):
        super().__init__(pass_name=pass_name)
        self._gizmo_renderer_source = gizmo_renderer
        self.input_res = input_res
        self.output_res = output_res

    def compute_reads(self) -> Set[str]:
        return {self.input_res}

    def compute_writes(self) -> Set[str]:
        return {self.output_res}

    def _get_gizmo_renderer(self) -> "ImmediateGizmoRenderer | None":
        if self._gizmo_renderer_source is None:
            return None
        if callable(self._gizmo_renderer_source):
            return self._gizmo_renderer_source()
        return self._gizmo_renderer_source

    def get_inplace_aliases(self) -> List[Tuple[str, str]]:
        return [(self.input_res, self.output_res)]

    def execute(self, ctx: "ExecuteContext") -> None:
        gizmo = self._get_gizmo_renderer()
        if gizmo is None or not gizmo.visible:
            return

        px, py, pw, ph = ctx.rect

        fb = ctx.writes_fbos.get(self.output_res)
        ctx.graphics.bind_framebuffer(fb)
        ctx.graphics.set_viewport(0, 0, pw, ph)

        # Clear depth so gizmo renders on top of scene
        # Depth test is enabled in gizmo.flush() for proper triangle occlusion
        ctx.graphics.clear_depth()

        view = ctx.camera.get_view_matrix()
        proj = ctx.camera.get_projection_matrix()

        # Draw and flush gizmo (scale is set once in set_target)
        gizmo.begin()
        gizmo.draw()
        gizmo.flush(ctx.graphics, view, proj)
