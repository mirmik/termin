"""UnifiedGizmoPass - renders a retained overlay draw source."""

from __future__ import annotations

from typing import Any, Callable, List, Protocol, Set, Tuple, TYPE_CHECKING

from termin.render_framework.python_pass import PythonFramePass
from termin.render import ImmediateRenderer
from termin.inspect import InspectField
from termin.base.profiler import Profiler

if TYPE_CHECKING:
    from termin.render_framework import ExecuteContext


class OverlayDrawSource(Protocol):
    """Object capable of submitting retained overlay geometry."""

    def render(self, renderer: ImmediateRenderer, ctx2: Any, view: Any, proj: Any) -> None:
        ...


class UnifiedGizmoPass(PythonFramePass):
    """
    Framegraph pass that renders one retained overlay draw source.

    Gizmos are rendered on top of the scene: the pass clears its depth
    attachment before rendering, then uses it for depth between gizmo elements.
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
        draw_source: OverlayDrawSource | Callable[[], OverlayDrawSource | None] | None = None,
        before_render: Callable[["ExecuteContext"], None] | None = None,
        input_res: str = "color",
        output_res: str = "color",
        pass_name: str = "UnifiedGizmoPass",
    ):
        super().__init__(pass_name=pass_name)
        self._draw_source = draw_source
        self._before_render = before_render
        self.input_res = input_res
        self.output_res = output_res

    def compute_reads(self) -> Set[str]:
        return {self.input_res}

    def compute_writes(self) -> Set[str]:
        return {self.output_res}

    def _get_draw_source(self) -> OverlayDrawSource | None:
        if self._draw_source is None:
            return None
        if callable(self._draw_source):
            return self._draw_source()
        return self._draw_source

    def get_inplace_aliases(self) -> List[Tuple[str, str]]:
        return [(self.input_res, self.output_res)]

    def execute(self, ctx: "ExecuteContext") -> None:
        profiler = Profiler.instance()

        with profiler.section("UnifiedGizmoPass"):
            if ctx.ctx2 is None:
                from termin.base import log
                log.error("[UnifiedGizmoPass] ctx.ctx2 is None — pass is tgfx2-only")
                return

            draw_source = self._get_draw_source()
            renderer = ImmediateRenderer.instance()

            px, py, pw, ph = ctx.render_rect

            target_tex2 = ctx.tex2_writes.get(self.output_res)
            if not target_tex2:
                from termin.base import log
                log.warn(f"[UnifiedGizmoPass] tex2 write '{self.output_res}' missing, skipping")
                return
            target_depth_tex2 = ctx.tex2_depth_writes.get(self.output_res)
            if not target_depth_tex2:
                from termin.base import log
                log.error(f"[UnifiedGizmoPass] depth tex2 write '{self.output_res}' missing, skipping")
                return

            ctx2 = ctx.ctx2

            with profiler.section("Setup"):
                # Open one ctx2 pass and clear depth — gizmos render on
                # top of scene, while gizmo elements still depth-test
                # against each other inside this cleared attachment.
                ctx2.begin_pass(
                    target_tex2,
                    target_depth_tex2,
                    clear_depth_enabled=True,
                    clear_depth=1.0,
                )
                ctx2.set_viewport(0, 0, pw, ph)

                view = ctx.view.get_view_matrix()
                proj = ctx.view.get_projection_matrix()

            try:
                if self._before_render is not None:
                    self._before_render(ctx)
                if draw_source is not None and renderer is not None:
                    with profiler.section("OverlayRender"):
                        draw_source.render(renderer, ctx2, view, proj)

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
