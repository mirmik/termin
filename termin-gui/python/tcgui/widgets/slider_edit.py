"""SliderEdit widget."""

from __future__ import annotations
from typing import Callable

from tcgui.widgets.widget import Widget
from tcgui.widgets.slider import Slider
from tcgui.widgets.spin_box import SpinBox


class SliderEdit(Widget):
    """Composite widget: Slider + SpinBox side by side."""

    def __init__(self):
        super().__init__()

        # Numeric parameters
        self.value: float = 0.0
        self.min_value: float = 0.0
        self.max_value: float = 1.0
        self.step: float = 0.0
        self.decimals: int = 2

        # Layout
        self.spacing: float = 4
        self.spinbox_width: float = 80

        # Internal widgets
        self._slider = Slider()
        self._spinbox = SpinBox()
        self.add_child(self._slider)
        self.add_child(self._spinbox)

        self._updating: bool = False

        # Callback
        self.on_changed: Callable[[float], None] | None = None

        # Sync parameters to children
        self._sync_params()
        self._slider.on_changed = self._on_slider_change
        self._spinbox.on_changed = self._on_spinbox_change

    def _sync_params(self):
        """Push numeric params to child widgets."""
        self._slider.min_value = self.min_value
        self._slider.max_value = self.max_value
        self._slider.step = self.step
        self._slider.value = self.value
        self._spinbox.min_value = self.min_value
        self._spinbox.max_value = self.max_value
        self._spinbox.step = self.step if self.step > 0 else 0.01
        self._spinbox.value = self.value
        self._spinbox.decimals = self.decimals

    def _on_slider_change(self, val: float):
        if self._updating:
            return
        self._updating = True
        self._spinbox.value = val
        if self._spinbox._editing:
            self._spinbox._edit_text = self._spinbox._format_value()
            self._spinbox._cursor_pos = len(self._spinbox._edit_text)
        self.value = val
        if self.on_changed:
            self.on_changed(val)
        self._updating = False

    def _on_spinbox_change(self, val: float):
        if self._updating:
            return
        self._updating = True
        self._slider.value = val
        self.value = val
        if self.on_changed:
            self.on_changed(val)
        self._updating = False

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        if self.preferred_width and self.preferred_height:
            return (
                self.preferred_width.to_pixels(viewport_w),
                self.preferred_height.to_pixels(viewport_h)
            )
        w = self.preferred_width.to_pixels(viewport_w) if self.preferred_width else 300
        slider_h = self._slider.compute_size(viewport_w, viewport_h)[1]
        spinbox_h = self._spinbox.compute_size(viewport_w, viewport_h)[1]
        h = max(slider_h, spinbox_h)
        return (w, h)

    def layout(self, x: float, y: float, width: float, height: float,
               viewport_w: float, viewport_h: float):
        super().layout(x, y, width, height, viewport_w, viewport_h)
        self._sync_params()
        slider_w = width - self.spinbox_width - self.spacing
        self._slider.layout(x, y, slider_w, height, viewport_w, viewport_h)
        self._spinbox.layout(x + slider_w + self.spacing, y, self.spinbox_width, height, viewport_w, viewport_h)
