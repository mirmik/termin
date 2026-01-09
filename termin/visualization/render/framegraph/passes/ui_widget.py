"""UIWidgetPass — Render pass for widget-based UI system."""

from __future__ import annotations

from typing import List, Set, Tuple, TYPE_CHECKING

from termin.visualization.render.framegraph.passes.base import RenderFramePass
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import GraphicsBackend, FramebufferHandle


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

        # Get layer_mask from ViewportHintComponent on camera
        layer_mask = 0xFFFFFFFFFFFFFFFF  # All layers by default
        if camera is not None and camera.entity is not None:
            from termin.visualization.core.viewport_hint import ViewportHintComponent
            hint = camera.entity.get_component(ViewportHintComponent)
            if hint is not None:
                layer_mask = hint.layer_mask

        # Find all UIComponent instances in the scene
        from termin.visualization.ui.widgets.component import UIComponent

        ui_components = scene.find_components(UIComponent)
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
                if not (layer_mask & (1 << entity_layer)):
                    continue
            ui_comp.render(graphics, pw, ph, context_key)
            graphics.check_gl_error(f"UIWidgets: {entity.name if entity else 'ui_component'}")
