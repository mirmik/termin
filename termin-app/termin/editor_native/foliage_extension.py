"""Native projection for the toolkit-neutral foliage brush extension."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from termin.editor_core.component_editor_extension import (
    ComponentEditorExtension,
    ComponentExtensionPresentation,
)
from termin.gui_native import Document, EdgeInsets, Size


if TYPE_CHECKING:
    from termin.editor_core.foliage_layer_editor_extension import FoliageBrushSnapshot


_logger = logging.getLogger(__name__)


def project_native_foliage_extension(
    extension: ComponentEditorExtension,
    document: Document,
) -> ComponentExtensionPresentation:
    from termin.editor_core.foliage_layer_editor_extension import FoliageLayerEditorExtension

    if not isinstance(extension, FoliageLayerEditorExtension):
        _logger.error("Foliage projector received incompatible extension")
        raise TypeError("foliage projector requires FoliageLayerEditorExtension")

    root = document.create_vstack("native-foliage-extension")
    root.stable_id = "editor.inspector.extension.foliage"
    root.set_layout_padding(EdgeInsets(2.0, 2.0, 2.0, 2.0))
    root.set_layout_spacing(4.0)
    root.preferred_size = Size(340.0, 178.0)

    title = document.create_label("Foliage Brush", "native-foliage-title")
    mode_label = document.create_status_bar("Mode: Off")
    mode_label.widget.debug_name = "native-foliage-mode"
    asset_label = document.create_status_bar("Asset: <none>")
    asset_label.widget.debug_name = "native-foliage-asset"
    radius_label = document.create_status_bar("Radius: 0.50")
    radius_label.widget.debug_name = "native-foliage-radius"
    count_label = document.create_status_bar("Count: 1")
    count_label.widget.debug_name = "native-foliage-count"
    root.add_fixed_child(title, 24.0)
    root.add_fixed_child(mode_label.widget, 22.0)
    root.add_fixed_child(asset_label.widget, 22.0)

    mode_row = document.create_hstack("native-foliage-mode-row")
    mode_row.set_layout_spacing(4.0)
    off = document.create_button("Off", "native-foliage-mode-off")
    paint = document.create_button("Paint", "native-foliage-mode-paint")
    erase = document.create_button("Erase", "native-foliage-mode-erase")
    mode_row.add_stretch_child(off.widget)
    mode_row.add_stretch_child(paint.widget)
    mode_row.add_stretch_child(erase.widget)
    root.add_fixed_child(mode_row, 28.0)

    radius_row = document.create_hstack("native-foliage-radius-row")
    radius_row.set_layout_spacing(4.0)
    radius_minus = document.create_button("−", "native-foliage-radius-minus")
    radius_plus = document.create_button("+", "native-foliage-radius-plus")
    radius_row.add_stretch_child(radius_label.widget)
    radius_row.add_fixed_child(radius_minus.widget, 32.0)
    radius_row.add_fixed_child(radius_plus.widget, 32.0)
    root.add_fixed_child(radius_row, 28.0)

    count_row = document.create_hstack("native-foliage-count-row")
    count_row.set_layout_spacing(4.0)
    count_minus = document.create_button("−", "native-foliage-count-minus")
    count_plus = document.create_button("+", "native-foliage-count-plus")
    count_row.add_stretch_child(count_label.widget)
    count_row.add_fixed_child(count_minus.widget, 32.0)
    count_row.add_fixed_child(count_plus.widget, 32.0)
    root.add_fixed_child(count_row, 28.0)

    def apply_snapshot(snapshot: FoliageBrushSnapshot) -> None:
        mode_label.text = f"Mode: {snapshot.mode.title() if snapshot.mode != 'idle' else 'Off'}"
        radius_label.text = f"Radius: {snapshot.radius:.2f}"
        count_label.text = f"Count: {snapshot.stamp_count}"
        if snapshot.asset_name is None:
            asset_label.text = "Asset: <none>"
        else:
            asset_label.text = (
                f"Asset: {snapshot.asset_name}; instances: {snapshot.instance_count}"
            )
        mode_label.widget.name = mode_label.text
        asset_label.widget.name = asset_label.text
        radius_label.widget.name = radius_label.text
        count_label.widget.name = count_label.text

    off.connect_clicked(lambda: extension.set_mode("idle"))
    paint.connect_clicked(lambda: extension.set_mode("paint"))
    erase.connect_clicked(lambda: extension.set_mode("erase"))
    radius_minus.connect_clicked(lambda: extension.change_radius(-0.1))
    radius_plus.connect_clicked(lambda: extension.change_radius(0.1))
    count_minus.connect_clicked(lambda: extension.change_count(-1))
    count_plus.connect_clicked(lambda: extension.change_count(1))
    extension.set_changed_handler(apply_snapshot)
    return ComponentExtensionPresentation(right_panel=root)


__all__ = ["project_native_foliage_extension"]
