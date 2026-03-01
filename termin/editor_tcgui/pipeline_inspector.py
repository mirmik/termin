"""Pipeline inspector for tcgui."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from tcgui.widgets.vstack import VStack
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.list_widget import ListWidget
from tcgui.widgets.separator import Separator

from termin.editor_tcgui.inspect_field_panel import InspectFieldPanel


class PipelineInspectorTcgui(VStack):
    """Specialized tcgui inspector for render pipelines."""

    def __init__(self, resource_manager) -> None:
        super().__init__()
        self.spacing = 4
        self._rm = resource_manager
        self._pipeline = None
        self._passes = []

        self.on_changed: Optional[Callable[[], None]] = None

        title = Label(); title.text = "Pipeline Inspector"; self.add_child(title)
        self._subtitle = Label(); self._subtitle.color = (0.62, 0.66, 0.74, 1.0); self.add_child(self._subtitle)
        self.add_child(Separator())

        self._passes_list = ListWidget()
        self._passes_list.item_height = 22
        self._passes_list.item_spacing = 1
        self._passes_list.on_select = self._on_pass_selected
        self._passes_list.preferred_height = self._passes_list.preferred_height
        self.add_child(self._passes_list)

        self._fields = InspectFieldPanel(resource_manager)
        self._fields.on_field_changed = self._on_field_changed
        self.add_child(self._fields)

        self._empty = Label()
        self._empty.text = "No pipeline selected."
        self._empty.color = (0.52, 0.56, 0.62, 1.0)
        self.add_child(self._empty)

        self._set_visible_state(False)

    def set_pipeline(self, pipeline, subtitle: str = "") -> None:
        self._pipeline = pipeline
        self._subtitle.text = subtitle

        if pipeline is None:
            self._set_visible_state(False)
            self._passes = []
            self._passes_list.set_items([])
            self._fields.set_target(None)
            return

        self._set_visible_state(True)
        self._passes = list(pipeline.passes)
        items = [{"text": getattr(p, "pass_name", p.__class__.__name__)} for p in self._passes]
        self._passes_list.set_items(items)
        if self._passes:
            self._passes_list.selected_index = 0
            self._fields.set_target(self._passes[0])
        else:
            self._fields.set_target(None)

        if self._ui is not None:
            self._ui.request_layout()

    def load_pipeline_file(self, file_path: str) -> None:
        name = Path(file_path).stem
        asset = self._rm.get_pipeline_asset(name)
        pipeline = asset.data if asset is not None else None
        self.set_pipeline(pipeline, f"File: {file_path}")

    def _set_visible_state(self, has_pipeline: bool) -> None:
        self._passes_list.visible = has_pipeline
        self._fields.visible = has_pipeline
        self._empty.visible = not has_pipeline

    def _on_pass_selected(self, index: int, _item: dict) -> None:
        if index < 0 or index >= len(self._passes):
            self._fields.set_target(None)
            return
        self._fields.set_target(self._passes[index])

    def _on_field_changed(self, _key, _old, _new) -> None:
        if self.on_changed is not None:
            self.on_changed()
