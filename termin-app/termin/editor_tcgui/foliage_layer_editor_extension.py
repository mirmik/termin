"""tcgui projection for the toolkit-neutral foliage brush extension."""

from __future__ import annotations

from tcgui.widgets.button import Button
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.units import px
from tcgui.widgets.vstack import VStack

from termin.editor_core.component_editor_extension import (
    register_component_editor_extension,
)
from termin.editor_core.foliage_layer_editor_extension import (
    FoliageBrushSnapshot,
    FoliageLayerEditorExtension as CoreFoliageLayerEditorExtension,
)


_MODE_LABELS = {
    "idle": "Off",
    "paint": "Paint",
    "erase": "Erase",
}


class FoliageLayerEditorExtension(CoreFoliageLayerEditorExtension):
    """Compatibility class retaining the historical tcgui projection API."""

    def __init__(self) -> None:
        super().__init__()
        self._mode_label = Label()
        self._asset_label = Label()
        self._radius_label = Label()
        self._count_label = Label()

    def build_panel(self):
        root = VStack()
        root.spacing = 4

        title = Label()
        title.text = "Foliage Brush"
        root.add_child(title)

        self._mode_label.color = (0.55, 0.60, 0.68, 1.0)
        self._asset_label.color = (0.55, 0.60, 0.68, 1.0)
        self._radius_label.color = (0.55, 0.60, 0.68, 1.0)
        self._count_label.color = (0.55, 0.60, 0.68, 1.0)
        root.add_child(self._mode_label)
        root.add_child(self._asset_label)

        mode_row = HStack()
        mode_row.spacing = 4
        mode_row.preferred_height = px(28)
        mode_row.add_child(self._button("Off", lambda: self.set_mode("idle")))
        mode_row.add_child(self._button("Paint", lambda: self.set_mode("paint")))
        mode_row.add_child(self._button("Erase", lambda: self.set_mode("erase")))
        root.add_child(mode_row)

        radius_row = HStack()
        radius_row.spacing = 4
        radius_row.preferred_height = px(28)
        radius_row.add_child(self._radius_label)
        radius_row.add_child(self._button("-", lambda: self.change_radius(-0.1)))
        radius_row.add_child(self._button("+", lambda: self.change_radius(0.1)))
        root.add_child(radius_row)

        count_row = HStack()
        count_row.spacing = 4
        count_row.preferred_height = px(28)
        count_row.add_child(self._count_label)
        count_row.add_child(self._button("-", lambda: self.change_count(-1)))
        count_row.add_child(self._button("+", lambda: self.change_count(1)))
        root.add_child(count_row)

        self.set_changed_handler(self._apply_snapshot)
        return root

    def build_left_panel(self):
        return None

    def detach(self) -> None:
        self.set_changed_handler(None)
        super().detach()

    @staticmethod
    def _button(text: str, callback) -> Button:
        button = Button()
        button.text = text
        button.on_click = callback
        return button

    def _apply_snapshot(self, snapshot: FoliageBrushSnapshot) -> None:
        self._mode_label.text = f"Mode: {_MODE_LABELS[snapshot.mode]}"
        self._radius_label.text = f"Radius: {snapshot.radius:.2f}"
        self._count_label.text = f"Count: {snapshot.stamp_count}"
        if snapshot.asset_name is None:
            self._asset_label.text = "Asset: <none>"
        else:
            self._asset_label.text = (
                f"Asset: {snapshot.asset_name}; instances: {snapshot.instance_count}"
            )


def register_default_extension() -> None:
    register_component_editor_extension(
        "FoliageLayerComponent",
        FoliageLayerEditorExtension,
    )


__all__ = ["FoliageLayerEditorExtension", "register_default_extension"]
