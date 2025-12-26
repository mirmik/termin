"""UIWidgetPass — Render pass for widget-based UI system."""

from __future__ import annotations

from typing import List, Tuple, TYPE_CHECKING

from termin.visualization.render.framegraph.passes.base import RenderFramePass

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import GraphicsBackend, FramebufferHandle


class UIWidgetPass(RenderFramePass):
    """
    Render pass that renders all UIComponent widgets in the scene.

    Finds all UIComponent instances in the scene and renders them
    sorted by priority (lower priority renders first, appears behind).

    This pass is typically placed after CanvasPass in the pipeline
    to render widgets on top of the old Canvas system.

    Usage in pipeline:
        UIWidgetPass(
            src="color+ui",      # Input from CanvasPass
            dst="color+widgets", # Output with widgets
            pass_name="UIWidgets",
        )
    """

    def __init__(
        self,
        input_res: str = "color+ui",
        output_res: str = "color+widgets",
        pass_name: str = "UIWidgets",
    ):
        super().__init__(
            pass_name=pass_name,
            reads={input_res},
            writes={output_res},
        )
        self.input_res = input_res
        self.output_res = output_res

    def _serialize_params(self) -> dict:
        """Serialize UIWidgetPass parameters."""
        return {
            "input_res": self.input_res,
            "output_res": self.output_res,
        }

    @classmethod
    def _deserialize_instance(cls, data: dict, resource_manager=None) -> "UIWidgetPass":
        """Create UIWidgetPass from serialized data."""
        return cls(
            input_res=data.get("input_res", "color+ui"),
            output_res=data.get("output_res", "color+widgets"),
            pass_name=data.get("pass_name", "UIWidgets"),
        )

    def get_inplace_aliases(self) -> List[Tuple[str, str]]:
        """UIWidgetPass reads input_res and writes output_res inplace."""
        return [(self.input_res, self.output_res)]

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

        fb_out = writes_fbos.get(self.output_res)
        graphics.bind_framebuffer(fb_out)
        graphics.set_viewport(0, 0, pw, ph)

        if scene is None:
            return

        # Find all UIComponent instances in the scene
        from termin.visualization.ui.widgets.component import UIComponent

        ui_components = scene.find_components(UIComponent)
        if not ui_components:
            return

        # Sort by priority (lower priority renders first)
        ui_components.sort(key=lambda c: c.priority)

        # Render each UIComponent
        for ui_comp in ui_components:
            if ui_comp.enabled:
                ui_comp.render(graphics, pw, ph, context_key)
