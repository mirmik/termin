"""UIWidgetPass — Render pass for widget-based UI system."""

from __future__ import annotations

from typing import List, Set, Tuple, TYPE_CHECKING

from termin.visualization.render.framegraph.passes.base import RenderFramePass
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import GraphicsBackend, FramebufferHandle
    from termin.visualization.render.framegraph.execute_context import ExecuteContext


class UIWidgetPass(RenderFramePass):
    """
    Render pass that renders all UIComponent widgets in the scene.

    Finds all UIComponent instances in the scene and renders them
    sorted by priority (lower priority renders first, appears behind).

    Usage in pipeline:
        UIWidgetPass(
            input_res="color_pp",
            output_res="color+widgets",
            pass_name="UIWidgets",
        )
    """

    category = "UI"

    node_inputs = [("input_res", "fbo")]
    node_outputs = [("output_res", "fbo")]
    node_inplace_pairs = [("input_res", "output_res")]

    inspect_fields = {
        "input_res": InspectField(path="input_res", label="Input Resource", kind="string"),
        "output_res": InspectField(path="output_res", label="Output Resource", kind="string"),
    }

    def __init__(
        self,
        input_res: str = "color+ui",
        output_res: str = "color+widgets",
        pass_name: str = "UIWidgets",
    ):
        super().__init__(pass_name=pass_name)
        self.input_res = input_res
        self.output_res = output_res

    def compute_reads(self) -> Set[str]:
        return {self.input_res}

    def compute_writes(self) -> Set[str]:
        return {self.output_res}

    def get_inplace_aliases(self) -> List[Tuple[str, str]]:
        """UIWidgetPass reads input_res and writes output_res inplace."""
        return [(self.input_res, self.output_res)]

    def execute(self, ctx: "ExecuteContext") -> None:
        px, py, pw, ph = ctx.rect

        fb_out = ctx.writes_fbos.get(self.output_res)
        ctx.graphics.bind_framebuffer(fb_out)
        ctx.graphics.set_viewport(0, 0, pw, ph)

        if ctx.scene is None:
            return

        # Find all UIComponent instances in the scene
        from termin.visualization.ui.widgets.component import UIComponent

        ui_components = ctx.scene.find_components(UIComponent)
        if not ui_components:
            return

        # Sort by priority (lower priority renders first)
        ui_components.sort(key=lambda c: c.priority)

        # Render each UIComponent that passes layer mask filter
        for ui_comp in ui_components:
            if not ui_comp.enabled:
                continue
            # Check if UI entity's layer is in the mask
            entity = ui_comp.entity
            if entity is not None:
                entity_layer = entity.layer
                if not (ctx.layer_mask & (1 << entity_layer)):
                    continue
            ui_comp.render(ctx.graphics, pw, ph, ctx.context_key)
            ctx.graphics.check_gl_error(f"UIWidgets: {entity.name if entity else 'ui_component'}")
