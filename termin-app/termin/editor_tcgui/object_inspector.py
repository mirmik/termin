"""Generic tcgui object inspector based on InspectFieldPanel."""

from __future__ import annotations

from typing import Any, Callable, Optional

from tcgui.widgets.vstack import VStack
from tcgui.widgets.label import Label
from tcgui.widgets.separator import Separator

from termin.editor_tcgui.inspect_field_panel import InspectFieldPanel


class ObjectInspector(VStack):
    """Inspector panel for arbitrary objects with InspectRegistry metadata."""

    def __init__(self, title: str, resources=None) -> None:
        super().__init__()
        self.spacing = 4

        self._title = Label()
        self._title.text = title
        self.add_child(self._title)

        self._subtitle = Label()
        self._subtitle.color = (0.62, 0.66, 0.74, 1.0)
        self.add_child(self._subtitle)

        self.add_child(Separator())

        self._empty_label = Label()
        self._empty_label.text = "No object selected."
        self._empty_label.color = (0.52, 0.56, 0.62, 1.0)
        self.add_child(self._empty_label)

        self._panel = InspectFieldPanel(resources)
        self._panel.visible = False
        self.add_child(self._panel)

        self._target: Any = None
        self.on_changed: Optional[Callable[[], None]] = None
        self._panel.on_field_changed = self._on_field_changed

    def set_scene_getter(self, getter) -> None:
        self._panel.set_scene_getter(getter)

    def set_title(self, text: str) -> None:
        self._title.text = text

    def set_target(self, target: Any, subtitle: str = "") -> None:
        self._target = target
        self._subtitle.text = subtitle

        if target is None:
            self._empty_label.visible = True
            self._panel.visible = False
            self._panel.set_target(None)
            self._empty_label.text = "Object not found."
        else:
            self._panel.set_target(target)
            self._panel.visible = bool(self._panel._fields)
            self._empty_label.visible = not self._panel.visible
            if self._empty_label.visible:
                self._empty_label.text = "No inspectable fields."

        if self._ui is not None:
            self._ui.request_layout()

    def refresh(self) -> None:
        self._panel.refresh()

    def _on_field_changed(self, _key: str, _old_value: Any, _new_value: Any) -> None:
        if self.on_changed is not None:
            self.on_changed()
