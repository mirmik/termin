"""
Custom QDoubleSpinBox and QSpinBox subclasses.

setKeyboardTracking(False) — valueChanged fires only on Enter / focus loss,
not on every keystroke.
"""

from PyQt6.QtWidgets import QDoubleSpinBox, QSpinBox


class DoubleSpinBox(QDoubleSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setKeyboardTracking(False)


class SpinBox(QSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setKeyboardTracking(False)
