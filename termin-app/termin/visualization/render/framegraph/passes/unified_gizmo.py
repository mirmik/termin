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
from termin.core.profiler import Profiler

if TYPE_CHECKING:
    from termin.editor.gizmo import GizmoManager
    from termin.visualization.render.framegraph.execute_context import ExecuteContext


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

    def execute(self, ctx: "ExecuteContext") -> None:
        profiler = Profiler.instance()

        with profiler.section("UnifiedGizmoPass"):
            if ctx.ctx2 is None:
                from tcbase import log
                log.error(f"[UnifiedGizmoPass] ctx.ctx2 is None — UnifiedGizmoPass is tgfx2-only")
                return

            from tgfx._tgfx_native import PIXEL_RGBA8

            manager = self._get_gizmo_manager()
            renderer = ImmediateRenderer.instance()

            px, py, pw, ph = ctx.rect

            target_tex2 = ctx.tex2_writes.get(self.output_res)
            if not target_tex2:
                from tcbase import log
                log.warn(f"[UnifiedGizmoPass] tex2 write '{self.output_res}' missing, skipping")
                return

            ctx2 = ctx.ctx2

            with profiler.section("Setup"):
                # Open one ctx2 pass and clear depth — gizmos render on
                # top of scene. GizmoManager/ImmediateRenderer render
                # into this pass via their ctx2 entry points.
                ctx2.begin_pass(
                    target_tex2,
                    clear_depth_enabled=True,
                    clear_depth=1.0,
                )
                ctx2.set_viewport(0, 0, pw, ph)
                ctx2.set_color_format(PIXEL_RGBA8)

                view = ctx.camera.get_view_matrix()
                proj = ctx.camera.get_projection_matrix()

            try:
                if manager is not None and renderer is not None:
                    with profiler.section("GizmoRender"):
                        manager.render(renderer, ctx2, view, proj)

                if renderer is not None:
                    renderer.flush_depth(
                        ctx2=ctx2,
                        view_matrix=view,
                        proj_matrix=proj,
                        blend=True,
                    )
                    renderer.flush(
                        ctx2=ctx2,
                        view_matrix=view,
                        proj_matrix=proj,
                        depth_test=False,
                        blend=True,
                    )
                    renderer.begin()
            finally:
                ctx2.end_pass()
