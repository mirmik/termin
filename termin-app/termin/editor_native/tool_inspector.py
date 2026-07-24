"""Lifecycle-managed host for native project/tool inspector panels."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging

from termin.gui_native import TcDocument, WidgetRef

from .metrics import EDITOR_UI_METRICS


_logger = logging.getLogger(__name__)


@dataclass
class NativeToolInspector:
    document: TcDocument
    root: WidgetRef
    empty: WidgetRef
    panels: dict[str, WidgetRef] = field(default_factory=dict)
    active_key: str | None = None

    def register(self, key: str, panel: WidgetRef) -> None:
        normalized = key.strip()
        if not normalized:
            raise ValueError("tool inspector key must not be empty")
        if not self.document.is_alive(panel.handle):
            raise ValueError("tool inspector panel is not alive")
        if normalized in self.panels:
            raise ValueError(f"tool inspector is already registered: {normalized}")
        self.panels[normalized] = panel

    def unregister(self, key: str) -> WidgetRef | None:
        panel = self.panels.pop(key, None)
        if panel is not None and self.active_key == key:
            if not self.root.remove_child(panel):
                _logger.error("Failed to detach active tool inspector panel '%s'", key)
            self.active_key = None
            self.empty.visible = True
        return panel

    def set_target(self, key: object, *, label: str = "") -> None:
        normalized = str(key)
        next_panel = self.panels.get(normalized)
        if next_panel is None:
            _logger.error("Missing native tool inspector panel '%s'", normalized)
        if self.active_key is not None:
            current = self.panels.get(self.active_key)
            if current is not None and not self.root.remove_child(current):
                _logger.error("Failed to detach native tool inspector panel '%s'", self.active_key)
        self.active_key = None
        self.empty.visible = next_panel is None
        if next_panel is not None:
            if not next_panel.detach():
                _logger.debug("Tool inspector panel '%s' was already detached", normalized)
            self.root.add_stretch_child(next_panel)
            self.active_key = normalized


def build_native_tool_inspector(document: TcDocument) -> NativeToolInspector:
    root = document.create_vstack("native-tool-inspector")
    root.set_layout_padding(EDITOR_UI_METRICS.embedded_panel_insets)
    root.set_layout_spacing(EDITOR_UI_METRICS.compact_spacing)
    empty = document.create_label("No tool inspector panel selected.", "native-tool-inspector-empty")
    root.add_fixed_child(empty, EDITOR_UI_METRICS.compact_row)
    return NativeToolInspector(document, root, empty)


__all__ = ["NativeToolInspector", "build_native_tool_inspector"]
