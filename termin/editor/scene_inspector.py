"""Scene-level properties inspector widget."""

from __future__ import annotations

from typing import Optional, Callable

import numpy as np
from PyQt6.QtWidgets import (
    QWidget,
    QFormLayout,
    QDoubleSpinBox,
    QLabel,
    QVBoxLayout,
    QPushButton,
    QGroupBox,
    QComboBox,
)
from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt, pyqtSignal

from termin.editor.color_dialog import ColorDialog
from termin.editor.undo_stack import UndoCommand
from termin.visualization.core.scene import Scene
from termin._native import log


class ScenePropertyEditCommand(UndoCommand):
    """Undo command for editing scene properties."""

    def __init__(
        self,
        scene: Scene,
        property_name: str,
        old_value,
        new_value,
    ):
        self._scene = scene
        self._property_name = property_name
        self._old_value = self._clone_value(old_value)
        self._new_value = self._clone_value(new_value)

    def _clone_value(self, value):
        if isinstance(value, np.ndarray):
            return value.copy()
        return value

    def do(self) -> None:
        setattr(self._scene, self._property_name, self._clone_value(self._new_value))

    def undo(self) -> None:
        setattr(self._scene, self._property_name, self._clone_value(self._old_value))

    def merge_with(self, other: UndoCommand) -> bool:
        if not isinstance(other, ScenePropertyEditCommand):
            return False
        if other._scene is not self._scene:
            return False
        if other._property_name != self._property_name:
            return False
        self._new_value = self._clone_value(other._new_value)
        return True

    def __repr__(self) -> str:
        return f"ScenePropertyEditCommand({self._property_name})"


def _to_qcolor(value) -> QColor:
    """Convert color value to QColor."""
    if isinstance(value, QColor):
        return value
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        r = float(value[0])
        g = float(value[1])
        b = float(value[2])
        a = float(value[3]) if len(value) > 3 else 1.0
        return QColor.fromRgbF(
            max(0.0, min(1.0, r)),
            max(0.0, min(1.0, g)),
            max(0.0, min(1.0, b)),
            max(0.0, min(1.0, a)),
        )
    try:
        arr = np.asarray(value).reshape(-1)
        if arr.size >= 3:
            r = float(arr[0])
            g = float(arr[1])
            b = float(arr[2])
            a = float(arr[3]) if arr.size > 3 else 1.0
            return QColor.fromRgbF(
                max(0.0, min(1.0, r)),
                max(0.0, min(1.0, g)),
                max(0.0, min(1.0, b)),
                max(0.0, min(1.0, a)),
            )
    except Exception as e:
        log.debug(f"[SceneInspector] Failed to convert value to QColor: {e}")
    return QColor(255, 255, 255)


class SceneInspector(QWidget):
    """Inspector widget for scene-level properties."""

    scene_changed = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._scene: Optional[Scene] = None
        self._updating_from_model = False
        self._push_undo_command: Optional[Callable[[UndoCommand, bool], None]] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        # Title
        title = QLabel("Scene Properties")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)

        # Background color group
        bg_group = QGroupBox("Background")
        bg_layout = QFormLayout(bg_group)
        bg_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self._bg_color_btn = self._create_color_button()
        bg_layout.addRow(QLabel("Color:"), self._bg_color_btn)
        layout.addWidget(bg_group)

        # Ambient lighting group
        ambient_group = QGroupBox("Ambient Lighting")
        ambient_layout = QFormLayout(ambient_group)
        ambient_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self._ambient_color_btn = self._create_color_button()
        ambient_layout.addRow(QLabel("Color:"), self._ambient_color_btn)

        self._ambient_intensity_spin = QDoubleSpinBox()
        self._ambient_intensity_spin.setDecimals(3)
        self._ambient_intensity_spin.setRange(0.0, 10.0)
        self._ambient_intensity_spin.setSingleStep(0.01)
        ambient_layout.addRow(QLabel("Intensity:"), self._ambient_intensity_spin)

        layout.addWidget(ambient_group)

        # Skybox group
        skybox_group = QGroupBox("Skybox")
        skybox_layout = QFormLayout(skybox_group)
        skybox_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self._skybox_type_combo = QComboBox()
        self._skybox_type_combo.addItem("Gradient", "gradient")
        self._skybox_type_combo.addItem("Solid Color", "solid")
        self._skybox_type_combo.addItem("None", "none")
        skybox_layout.addRow(QLabel("Type:"), self._skybox_type_combo)

        # Solid color
        self._skybox_color_btn = self._create_color_button()
        self._skybox_color_label = QLabel("Color:")
        skybox_layout.addRow(self._skybox_color_label, self._skybox_color_btn)

        # Gradient colors
        self._skybox_top_color_btn = self._create_color_button()
        self._skybox_top_color_label = QLabel("Top:")
        skybox_layout.addRow(self._skybox_top_color_label, self._skybox_top_color_btn)

        self._skybox_bottom_color_btn = self._create_color_button()
        self._skybox_bottom_color_label = QLabel("Bottom:")
        skybox_layout.addRow(self._skybox_bottom_color_label, self._skybox_bottom_color_btn)

        layout.addWidget(skybox_group)

        layout.addStretch()

        # Connect signals
        self._bg_color_btn.clicked.connect(self._on_bg_color_clicked)
        self._ambient_color_btn.clicked.connect(self._on_ambient_color_clicked)
        self._ambient_intensity_spin.valueChanged.connect(self._on_ambient_intensity_changed)
        self._skybox_type_combo.currentIndexChanged.connect(self._on_skybox_type_changed)
        self._skybox_color_btn.clicked.connect(self._on_skybox_color_clicked)
        self._skybox_top_color_btn.clicked.connect(self._on_skybox_top_color_clicked)
        self._skybox_bottom_color_btn.clicked.connect(self._on_skybox_bottom_color_clicked)

    def _create_color_button(self) -> QPushButton:
        """Create a color picker button."""
        btn = QPushButton()
        btn.setAutoFillBackground(True)
        btn._current_color = (1.0, 1.0, 1.0, 1.0)

        def set_btn_color(color: QColor):
            btn._current_color = (
                color.redF(),
                color.greenF(),
                color.blueF(),
                color.alphaF(),
            )
            pal = btn.palette()
            pal.setColor(btn.backgroundRole(), color)
            btn.setPalette(pal)
            btn.setText(
                f"{color.redF():.2f}, {color.greenF():.2f}, {color.blueF():.2f}"
            )

        btn._set_color = set_btn_color
        return btn

    def set_undo_command_handler(
        self, handler: Optional[Callable[[UndoCommand, bool], None]]
    ) -> None:
        """Register undo command handler."""
        self._push_undo_command = handler

    def set_scene(self, scene: Optional[Scene]) -> None:
        """Set the scene to inspect."""
        self._scene = scene
        self._refresh_from_scene()

    def _refresh_from_scene(self) -> None:
        """Refresh all widgets from scene values."""
        if self._scene is None:
            return

        self._updating_from_model = True
        try:
            # Background color
            bg_color = self._scene.background_color
            qcolor = _to_qcolor(bg_color[:3] if len(bg_color) > 3 else bg_color)
            self._bg_color_btn._set_color(qcolor)

            # Ambient color
            ambient_color = self._scene.ambient_color
            qcolor = _to_qcolor(ambient_color)
            self._ambient_color_btn._set_color(qcolor)

            # Ambient intensity
            self._ambient_intensity_spin.setValue(self._scene.ambient_intensity)

            # Skybox type
            skybox_type = self._scene.skybox_type
            index = self._skybox_type_combo.findData(skybox_type)
            if index >= 0:
                self._skybox_type_combo.setCurrentIndex(index)

            # Skybox color visibility based on type
            show_solid = (skybox_type == "solid")
            show_gradient = (skybox_type == "gradient")

            self._skybox_color_btn.setVisible(show_solid)
            self._skybox_color_label.setVisible(show_solid)
            self._skybox_top_color_btn.setVisible(show_gradient)
            self._skybox_top_color_label.setVisible(show_gradient)
            self._skybox_bottom_color_btn.setVisible(show_gradient)
            self._skybox_bottom_color_label.setVisible(show_gradient)

            # Solid color
            skybox_color = self._scene.skybox_color
            qcolor = _to_qcolor(skybox_color)
            self._skybox_color_btn._set_color(qcolor)

            # Gradient colors
            top_color = self._scene.skybox_top_color
            qcolor = _to_qcolor(top_color)
            self._skybox_top_color_btn._set_color(qcolor)

            bottom_color = self._scene.skybox_bottom_color
            qcolor = _to_qcolor(bottom_color)
            self._skybox_bottom_color_btn._set_color(qcolor)
        finally:
            self._updating_from_model = False

    def _on_bg_color_clicked(self) -> None:
        """Handle background color button click."""
        if self._scene is None:
            return

        current = self._scene.background_color
        initial = (float(current[0]), float(current[1]), float(current[2]), 1.0)

        result = ColorDialog.get_color(initial, self)
        if result is None:
            return

        old_value = self._scene.background_color.copy()
        new_value = np.array([result[0], result[1], result[2], current[3]], dtype=np.float32)

        if self._push_undo_command is not None:
            cmd = ScenePropertyEditCommand(
                self._scene, "background_color", old_value, new_value
            )
            self._push_undo_command(cmd, False)
        else:
            self._scene.background_color = new_value

        self._refresh_from_scene()
        self.scene_changed.emit()

    def _on_ambient_color_clicked(self) -> None:
        """Handle ambient color button click."""
        if self._scene is None:
            return

        current = self._scene.ambient_color
        initial = (float(current[0]), float(current[1]), float(current[2]), 1.0)

        result = ColorDialog.get_color(initial, self)
        if result is None:
            return

        old_value = self._scene.ambient_color.copy()
        new_value = np.array([result[0], result[1], result[2]], dtype=np.float32)

        if self._push_undo_command is not None:
            cmd = ScenePropertyEditCommand(
                self._scene, "ambient_color", old_value, new_value
            )
            self._push_undo_command(cmd, False)
        else:
            self._scene.ambient_color = new_value

        self._refresh_from_scene()
        self.scene_changed.emit()

    def _on_ambient_intensity_changed(self, value: float) -> None:
        """Handle ambient intensity spinbox change."""
        if self._updating_from_model or self._scene is None:
            return

        old_value = self._scene.ambient_intensity
        new_value = value

        if self._push_undo_command is not None:
            cmd = ScenePropertyEditCommand(
                self._scene, "ambient_intensity", old_value, new_value
            )
            self._push_undo_command(cmd, True)  # merge for drag
        else:
            self._scene.ambient_intensity = new_value

        self.scene_changed.emit()

    def _on_skybox_type_changed(self, index: int) -> None:
        """Handle skybox type combo change."""
        if self._updating_from_model or self._scene is None:
            return

        new_type = self._skybox_type_combo.itemData(index)
        old_type = self._scene.skybox_type

        if new_type == old_type:
            return

        # Update visibility of color buttons
        show_solid = (new_type == "solid")
        show_gradient = (new_type == "gradient")
        self._skybox_color_btn.setVisible(show_solid)
        self._skybox_color_label.setVisible(show_solid)
        self._skybox_top_color_btn.setVisible(show_gradient)
        self._skybox_top_color_label.setVisible(show_gradient)
        self._skybox_bottom_color_btn.setVisible(show_gradient)
        self._skybox_bottom_color_label.setVisible(show_gradient)

        if self._push_undo_command is not None:
            cmd = SkyboxTypeEditCommand(self._scene, old_type, new_type)
            self._push_undo_command(cmd, False)
        else:
            self._scene.set_skybox_type(new_type)

        self.scene_changed.emit()

    def _on_skybox_color_clicked(self) -> None:
        """Handle skybox color button click."""
        if self._scene is None:
            return

        current = self._scene.skybox_color
        initial = (float(current[0]), float(current[1]), float(current[2]), 1.0)

        result = ColorDialog.get_color(initial, self)
        if result is None:
            return

        old_value = self._scene.skybox_color.copy()
        new_value = np.array([result[0], result[1], result[2]], dtype=np.float32)

        if self._push_undo_command is not None:
            cmd = ScenePropertyEditCommand(
                self._scene, "skybox_color", old_value, new_value
            )
            self._push_undo_command(cmd, False)
        else:
            self._scene.skybox_color = new_value

        self._refresh_from_scene()
        self.scene_changed.emit()

    def _on_skybox_top_color_clicked(self) -> None:
        """Handle skybox top color button click."""
        if self._scene is None:
            return

        current = self._scene.skybox_top_color
        initial = (float(current[0]), float(current[1]), float(current[2]), 1.0)

        result = ColorDialog.get_color(initial, self)
        if result is None:
            return

        old_value = self._scene.skybox_top_color.copy()
        new_value = np.array([result[0], result[1], result[2]], dtype=np.float32)

        if self._push_undo_command is not None:
            cmd = ScenePropertyEditCommand(
                self._scene, "skybox_top_color", old_value, new_value
            )
            self._push_undo_command(cmd, False)
        else:
            self._scene.skybox_top_color = new_value

        self._refresh_from_scene()
        self.scene_changed.emit()

    def _on_skybox_bottom_color_clicked(self) -> None:
        """Handle skybox bottom color button click."""
        if self._scene is None:
            return

        current = self._scene.skybox_bottom_color
        initial = (float(current[0]), float(current[1]), float(current[2]), 1.0)

        result = ColorDialog.get_color(initial, self)
        if result is None:
            return

        old_value = self._scene.skybox_bottom_color.copy()
        new_value = np.array([result[0], result[1], result[2]], dtype=np.float32)

        if self._push_undo_command is not None:
            cmd = ScenePropertyEditCommand(
                self._scene, "skybox_bottom_color", old_value, new_value
            )
            self._push_undo_command(cmd, False)
        else:
            self._scene.skybox_bottom_color = new_value

        self._refresh_from_scene()
        self.scene_changed.emit()


class SkyboxTypeEditCommand(UndoCommand):
    """Undo command for changing skybox type."""

    def __init__(self, scene: Scene, old_type: str, new_type: str):
        self._scene = scene
        self._old_type = old_type
        self._new_type = new_type

    def do(self) -> None:
        self._scene.set_skybox_type(self._new_type)

    def undo(self) -> None:
        self._scene.set_skybox_type(self._old_type)

    def __repr__(self) -> str:
        return f"SkyboxTypeEditCommand({self._old_type} -> {self._new_type})"
