"""UIWidgetPass - Render pass for widget-based UI system."""

from __future__ import annotations

from typing import List, Set, Tuple, TYPE_CHECKING

from termin.inspect import InspectField
from termin.render_framework.python_pass import PythonFramePass

if TYPE_CHECKING:
    from termin.visualization.render.framegraph.execute_context import ExecuteContext


class UIWidgetPass(PythonFramePass):
    """
    Render pass that renders all UIComponent widgets in the scene.

    Finds all UIComponent instances in the scene and renders them sorted by
    priority (lower priority renders first, appears behind).
    """

    category = "UI"

    node_inputs = [("input_res", "fbo")]
    node_outputs = [("output_res", "fbo")]
    node_inplace_pairs = [("input_res", "output_res")]

    inspect_fields = {
        "input_res": InspectField(path="input_res", label="Input Resource", kind="string"),
        "output_res": InspectField(path="output_res", label="Output Resource", kind="string"),
        "include_internal_entities": InspectField(
            path="include_internal_entities", label="Include Internal Entities", kind="bool"
        ),
    }

    def __init__(
        self,
        input_res: str = "color+ui",
        output_res: str = "color+widgets",
        pass_name: str = "UIWidgets",
        include_internal_entities: bool = False,
    ):
        super().__init__(pass_name=pass_name)
        self.input_res = input_res
        self.output_res = output_res
        self.include_internal_entities = include_internal_entities

    def compute_reads(self) -> Set[str]:
        return {self.input_res}

    def compute_writes(self) -> Set[str]:
        return {self.output_res}

    def get_inplace_aliases(self) -> List[Tuple[str, str]]:
        """UIWidgetPass reads input_res and writes output_res inplace."""
        return [(self.input_res, self.output_res)]

    def execute(self, ctx: "ExecuteContext") -> None:
        px, py, pw, ph = ctx.render_rect

        target_tex2 = ctx.tex2_writes.get(self.output_res)
        if not target_tex2:
            return

        ui_components = []

        if ctx.scene is not None:
            scene_ui = ctx.scene.get_components_of_type("UIComponent")
            if scene_ui:
                ui_components.extend(scene_ui)

        if self.include_internal_entities:
            internal_root = ctx.internal_entities
            if internal_root is not None:
                internal_ui = self._collect_ui_from_hierarchy(internal_root)
                ui_components.extend(internal_ui)

        if not ui_components:
            return

        ui_components.sort(key=lambda c: c.priority)

        for ui_comp in ui_components:
            if not ui_comp.enabled:
                continue
            entity = ui_comp.entity
            if entity is not None:
                entity_layer = entity.layer
                if not (ctx.layer_mask & (1 << entity_layer)):
                    continue
            ui_comp.render(pw, ph, ctx2=ctx.ctx2, target_tex2=target_tex2)

    def _collect_ui_from_hierarchy(self, entity) -> list:
        """Recursively collect UIComponents from entity hierarchy."""
        from termin.ui_components import UIComponent

        result = []
        ui = entity.get_component(UIComponent)
        if ui is not None:
            result.append(ui)

        for child_tf in entity.transform.children:
            if child_tf.entity is not None:
                result.extend(self._collect_ui_from_hierarchy(child_tf.entity))

        return result
