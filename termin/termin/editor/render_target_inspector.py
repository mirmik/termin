"""
RenderTargetInspector — inspector panel for RenderTarget properties.

Allows editing:
- Enabled
- Camera selection
- Pipeline selection
- Width / Height
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)
from termin.editor.widgets.spinbox import SpinBox

from tcbase import log

if TYPE_CHECKING:
    from termin.visualization.core.camera import CameraComponent
    from termin.visualization.core.scene import Scene


class RenderTargetInspector(QWidget):
    """Inspector for render target properties."""

    camera_changed = pyqtSignal(object)
    pipeline_changed = pyqtSignal(str)
    size_changed = pyqtSignal(int, int)
    enabled_changed = pyqtSignal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._render_target = None
        self._scene: Scene | None = None
        self._scenes: list = []
        self._cameras: list[CameraComponent] = []
        self._updating = False
        self._pipeline_names: list[str] = []
        self._pipeline_name_getter: Callable[[], list[str]] | None = None
        self._scene_getter: Callable[[], list] | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self._title = QLabel("No render target selected")
        layout.addWidget(self._title)

        form = QFormLayout()
        form.setSpacing(4)

        self._enabled_check = QCheckBox()
        self._enabled_check.toggled.connect(self._on_enabled_toggled)
        form.addRow("Enabled:", self._enabled_check)

        self._scene_combo = QComboBox()
        self._scene_combo.currentIndexChanged.connect(self._on_scene_changed)
        form.addRow("Scene:", self._scene_combo)

        self._camera_combo = QComboBox()
        self._camera_combo.currentIndexChanged.connect(self._on_camera_changed)
        form.addRow("Camera:", self._camera_combo)

        self._pipeline_combo = QComboBox()
        self._pipeline_combo.currentIndexChanged.connect(self._on_pipeline_changed)
        form.addRow("Pipeline:", self._pipeline_combo)

        self._width_spin = SpinBox()
        self._width_spin.setRange(1, 8192)
        self._width_spin.setSingleStep(64)
        self._width_spin.setValue(512)
        self._width_spin.valueChanged.connect(self._on_size_changed)
        form.addRow("Width:", self._width_spin)

        self._height_spin = SpinBox()
        self._height_spin.setRange(1, 8192)
        self._height_spin.setSingleStep(64)
        self._height_spin.setValue(512)
        self._height_spin.valueChanged.connect(self._on_size_changed)
        form.addRow("Height:", self._height_spin)

        layout.addLayout(form)
        layout.addStretch()

    def set_pipeline_name_getter(self, getter: Callable[[], list[str]]) -> None:
        self._pipeline_name_getter = getter

    def set_scene_getter(self, getter: Callable[[], list]) -> None:
        self._scene_getter = getter

    def set_scene(self, scene: "Scene | None") -> None:
        self._scene = scene

    def set_render_target(self, render_target, scene: "Scene | None" = None) -> None:
        self._render_target = render_target
        if scene is not None:
            self._scene = scene

        self._updating = True
        try:
            if render_target is None:
                self._title.setText("No render target selected")
                self.setEnabled(False)
                return

            is_locked = getattr(render_target, 'locked', False)
            self.setEnabled(not is_locked)
            label = render_target.name or '<unnamed>'
            if is_locked:
                label += " (locked)"
            self._title.setText(f"Render Target: {label}")

            self._enabled_check.setChecked(bool(render_target.enabled))

            self._refresh_scene_combo()
            self._select_current_scene()
            self._refresh_camera_combo()
            self._select_current_camera()
            self._refresh_pipeline_combo()
            self._select_current_pipeline()

            self._width_spin.setValue(render_target.width)
            self._height_spin.setValue(render_target.height)
        finally:
            self._updating = False

    def _refresh_scene_combo(self) -> None:
        self._scene_combo.blockSignals(True)
        self._scene_combo.clear()
        self._scenes.clear()
        self._scene_combo.addItem("(none)")
        if self._scene_getter is not None:
            try:
                for scene in self._scene_getter():
                    name = scene.name or scene.uuid or "Scene"
                    self._scenes.append(scene)
                    self._scene_combo.addItem(name)
            except Exception as e:
                log.error(f"[RenderTargetInspector] scene scan failed: {e}")
        self._scene_combo.blockSignals(False)

    def _select_current_scene(self) -> None:
        if self._render_target is None or self._render_target.scene is None:
            self._scene_combo.setCurrentIndex(0)
            return
        rt_scene = self._render_target.scene
        for i, scene in enumerate(self._scenes):
            try:
                if scene.scene_handle().index == rt_scene.scene_handle().index:
                    self._scene_combo.setCurrentIndex(i + 1)
                    return
            except Exception:
                pass
        self._scene_combo.setCurrentIndex(0)

    def _on_scene_changed(self, index: int) -> None:
        if self._updating or self._render_target is None:
            return
        if index <= 0:
            self._render_target.scene = None
            # Refresh camera combo — no scene means no cameras
            self._scene = None
            self._refresh_camera_combo()
            return
        idx = index - 1
        if 0 <= idx < len(self._scenes):
            self._render_target.scene = self._scenes[idx]
            self._scene = self._scenes[idx]
            self._refresh_camera_combo()

    def _refresh_camera_combo(self) -> None:
        self._camera_combo.blockSignals(True)
        self._camera_combo.clear()
        self._cameras.clear()
        self._camera_combo.addItem("(none)")

        if self._scene is not None:
            try:
                from termin.visualization.core.camera import CameraComponent
                for ent in self._scene.entities:
                    cam = ent.get_component(CameraComponent)
                    if cam is None:
                        continue
                    label = ent.name or ent.uuid or "Camera"
                    self._cameras.append(cam)
                    self._camera_combo.addItem(label)
            except Exception as e:
                log.error(f"[RenderTargetInspector] camera scan failed: {e}")

        self._camera_combo.blockSignals(False)

    def _select_current_camera(self) -> None:
        if self._render_target is None or self._render_target.camera is None:
            self._camera_combo.setCurrentIndex(0)
            return
        for i, cam in enumerate(self._cameras):
            if cam is self._render_target.camera:
                self._camera_combo.setCurrentIndex(i + 1)
                return
        self._camera_combo.setCurrentIndex(0)

    def _refresh_pipeline_combo(self) -> None:
        self._pipeline_combo.blockSignals(True)
        self._pipeline_combo.clear()
        self._pipeline_names.clear()
        self._pipeline_combo.addItem("(none)")
        self._pipeline_combo.addItem("(Default)")

        if self._pipeline_name_getter is not None:
            for name in self._pipeline_name_getter():
                self._pipeline_names.append(name)
                self._pipeline_combo.addItem(name)

        self._pipeline_combo.blockSignals(False)

    def _select_current_pipeline(self) -> None:
        if self._render_target is None or self._render_target.pipeline is None:
            self._pipeline_combo.setCurrentIndex(0)
            return
        current = self._render_target.pipeline.name or ""
        # Match by name in combo
        for i in range(self._pipeline_combo.count()):
            if self._pipeline_combo.itemText(i) == current:
                self._pipeline_combo.setCurrentIndex(i)
                return
        # "default"/"Default" → "(Default)" combo item
        if current.lower() == "default":
            self._pipeline_combo.setCurrentIndex(1)
            return
        # Pipeline exists but not in combo — still show it's set, not (none)
        self._pipeline_combo.setCurrentIndex(1)

    def _on_enabled_toggled(self, checked: bool) -> None:
        if self._updating or self._render_target is None:
            return
        self._render_target.enabled = checked
        self.enabled_changed.emit(checked)

    def _on_camera_changed(self, index: int) -> None:
        if self._updating or self._render_target is None:
            return
        if index <= 0:
            self._render_target.camera = None
            self.camera_changed.emit(None)
            return
        idx = index - 1
        if 0 <= idx < len(self._cameras):
            self._render_target.camera = self._cameras[idx]
            self.camera_changed.emit(self._cameras[idx])

    def _on_pipeline_changed(self, index: int) -> None:
        if self._updating or self._render_target is None:
            return
        text = self._pipeline_combo.currentText()
        if index == 0:
            self._render_target.pipeline = None
            self.pipeline_changed.emit("")
            return

        if text == "(Default)":
            from termin._native.render import RenderingManager
            pipeline = RenderingManager.instance().create_pipeline("Default")
            if pipeline is not None:
                self._render_target.pipeline = pipeline
        else:
            # Pipeline by name via pipeline_name_getter
            idx = index - 2
            if 0 <= idx < len(self._pipeline_names):
                from termin._native.render import RenderingManager
                pipeline = RenderingManager.instance().create_pipeline(self._pipeline_names[idx])
                if pipeline is not None:
                    self._render_target.pipeline = pipeline

        self.pipeline_changed.emit(text)

    def _on_size_changed(self) -> None:
        if self._updating or self._render_target is None:
            return
        w = self._width_spin.value()
        h = self._height_spin.value()
        self._render_target.width = w
        self._render_target.height = h
        self.size_changed.emit(w, h)
