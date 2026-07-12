"""Shared composition metrics for the compact native editor UI."""

from __future__ import annotations

from dataclasses import dataclass

from termin.gui_native import EdgeInsets


@dataclass(frozen=True, slots=True)
class EditorUiMetrics:
    spacing: float = 4.0
    panel_padding: float = 6.0
    collection_padding: float = 4.0
    compact_row: float = 28.0
    field_row: float = 30.0
    section_row: float = 24.0
    status_row: float = 24.0
    toolbar: float = 32.0
    prefab_toolbar: float = 30.0
    inspector_label: float = 112.0

    @property
    def panel_insets(self) -> EdgeInsets:
        value = self.panel_padding
        return EdgeInsets(value, value, value, value)

    @property
    def collection_insets(self) -> EdgeInsets:
        value = self.collection_padding
        return EdgeInsets(value, value, value, value)


EDITOR_UI_METRICS = EditorUiMetrics()


__all__ = ["EDITOR_UI_METRICS", "EditorUiMetrics"]
