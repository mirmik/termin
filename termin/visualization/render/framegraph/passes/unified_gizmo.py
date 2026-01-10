"""
UnifiedGizmoPass — unified gizmo rendering pass using GizmoManager.

Renders all gizmos registered with the manager in a single pass.
Uses the new unified gizmo architecture with declarative gizmos.
"""

from __future__ import annotations

from typing import Callable, List, Set, Tuple, TYPE_CHECKING

from termin.visualization.render.framegraph.passes.base import RenderFramePass
from termin.visualization.render.immediate import ImmediateRenderer
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.editor.gizmo import GizmoManager
    from termin.visualization.platform.backends.base import GraphicsBackend
    from termin.visualization.render.framebuffer import FramebufferHandle


class UnifiedGizmoPass(RenderFramePass):
    """
    Framegraph pass that renders all gizmos via GizmoManager.

    Gizmos are rendered on top of the scene (depth is cleared before rendering).
    This replaces both the old entity-based GizmoPass and ImmediateGizmoPass.
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
        gizmo_manager: "GizmoManager | Callable[[], GizmoManager | None] | None" = None,
        input_res: str = "color",
        output_res: str = "color",
        pass_name: str = "UnifiedGizmoPass",
    ):
        super().__init__(pass_name=pass_name)
        self._gizmo_manager_source = gizmo_manager
        self.input_res = input_res
        self.output_res = output_res
        self._renderer = ImmediateRenderer()

    def compute_reads(self) -> Set[str]:
        return {self.input_res}

    def compute_writes(self) -> Set[str]:
        return {self.output_res}

    def _get_gizmo_manager(self) -> "GizmoManager | None":
        if self._gizmo_manager_source is None:
            return None
        if callable(self._gizmo_manager_source):
            return self._gizmo_manager_source()
        return self._gizmo_manager_source

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
        manager = self._get_gizmo_manager()
        if manager is None:
            return

        px, py, pw, ph = rect

        fb = writes_fbos.get(self.output_res)
        graphics.bind_framebuffer(fb)
        graphics.set_viewport(0, 0, pw, ph)

        # Clear depth so gizmo renders on top of scene
        graphics.clear_depth()

        view = camera.get_view_matrix()
        proj = camera.get_projection_matrix()

        # Render all gizmos
        manager.render(self._renderer, graphics, view, proj, context_key)

        # Flush debug lines added by components via ImmediateRenderer.instance()
        # Components add lines during update(), we flush them here
        self._renderer.flush(
            graphics=graphics,
            view_matrix=view,
            proj_matrix=proj,
            depth_test=False,
            blend=False,
        )
