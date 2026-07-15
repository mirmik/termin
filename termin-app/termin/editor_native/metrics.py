"""Shared composition metrics for the compact native editor UI."""

from __future__ import annotations

from dataclasses import dataclass

from termin.gui_native import EdgeInsets


@dataclass(frozen=True, slots=True)
class EditorUiMetrics:
    compact_spacing: float = 2.0
    dense_spacing: float = 3.0
    spacing: float = 4.0
    dialog_spacing: float = 6.0
    panel_padding: float = 6.0
    collection_padding: float = 4.0
    dialog_padding: float = 8.0
    embedded_panel_padding: float = 2.0
    compact_row: float = 28.0
    field_row: float = 30.0
    section_row: float = 24.0
    compact_status_row: float = 22.0
    status_row: float = 24.0
    action_row: float = 34.0
    toolbar: float = 32.0
    prefab_toolbar: float = 30.0
    form_label: float = 120.0
    inspector_label: float = 112.0

    @property
    def panel_insets(self) -> EdgeInsets:
        value = self.panel_padding
        return EdgeInsets(value, value, value, value)

    @property
    def collection_insets(self) -> EdgeInsets:
        value = self.collection_padding
        return EdgeInsets(value, value, value, value)

    @property
    def dialog_insets(self) -> EdgeInsets:
        value = self.dialog_padding
        return EdgeInsets(value, value, value, value)

    @property
    def embedded_panel_insets(self) -> EdgeInsets:
        value = self.embedded_panel_padding
        return EdgeInsets(value, value, value, value)


EDITOR_UI_METRICS = EditorUiMetrics()


__all__ = ["EDITOR_UI_METRICS", "EditorUiMetrics"]
