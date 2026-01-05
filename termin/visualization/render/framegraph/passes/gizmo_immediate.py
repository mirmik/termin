"""
ImmediateGizmoPass - Renders transform gizmo using immediate mode rendering.

This pass renders the gizmo on top of the scene (no depth test) using
ImmediateGizmoRenderer, with mathematical raycast picking instead of ID buffer.
"""

from __future__ import annotations

from typing import Callable, List, Tuple, TYPE_CHECKING

from termin.visualization.render.framegraph.passes.base import RenderFramePass

if TYPE_CHECKING:
    from termin.editor.gizmo_immediate import ImmediateGizmoRenderer
    from termin.visualization.platform.backends.base import GraphicsBackend
    from termin.visualization.render.framebuffer import FramebufferHandle


class ImmediateGizmoPass(RenderFramePass):
    """
    Framegraph pass that renders the transform gizmo using immediate mode.

    Unlike the entity-based GizmoPass, this doesn't write to the ID buffer.
    Picking is handled separately via mathematical raycast.
    """

    def __init__(
        self,
        gizmo_renderer: "ImmediateGizmoRenderer | Callable[[], ImmediateGizmoRenderer | None] | None" = None,
        input_res: str = "color",
        output_res: str = "color",
        pass_name: str = "ImmediateGizmoPass",
    ):
        super().__init__(
            pass_name=pass_name,
            reads={input_res},
            writes={output_res},
        )
        self._gizmo_renderer_source = gizmo_renderer
        self.input_res = input_res
        self.output_res = output_res

    def _get_gizmo_renderer(self) -> "ImmediateGizmoRenderer | None":
        if self._gizmo_renderer_source is None:
            return None
        if callable(self._gizmo_renderer_source):
            return self._gizmo_renderer_source()
        return self._gizmo_renderer_source

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
        gizmo = self._get_gizmo_renderer()
        if gizmo is None or not gizmo.visible:
            return

        px, py, pw, ph = rect

        fb = writes_fbos.get(self.output_res)
        graphics.bind_framebuffer(fb)
        graphics.set_viewport(0, 0, pw, ph)

        # Clear depth so gizmo renders on top of scene
        # Depth test is enabled in gizmo.flush() for proper triangle occlusion
        graphics.clear_depth()

        view = camera.get_view_matrix()
        proj = camera.get_projection_matrix()

        # Draw and flush gizmo (scale is set once in set_target)
        gizmo.begin()
        gizmo.draw()
        gizmo.flush(graphics, view, proj)
