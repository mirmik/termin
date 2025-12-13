"""
ViewportInspector — inspector panel for Viewport properties.

Allows editing:
- Display selection
- Rect (x, y, width, height in normalized 0..1 coords)
- Camera selection (from entities with CameraComponent)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, List, Optional, Tuple

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from termin.visualization.core.camera import CameraComponent
    from termin.visualization.core.display import Display
    from termin.visualization.core.scene import Scene
    from termin.visualization.core.viewport import Viewport
    from termin.visualization.render.framegraph import RenderPipeline


class ViewportInspector(QWidget):
    """
    Inspector panel for Viewport properties.

    Shows and allows editing:
    - Display (dropdown)
    - Rect: x, y, width, height (spin boxes, 0..1)
    - Camera (dropdown of entities with CameraComponent)

    Signals:
        viewport_changed: Emitted when any property changes.
        display_changed: Emitted when display selection changes.
        camera_changed: Emitted when camera selection changes.
        rect_changed: Emitted when rect changes.
    """

    viewport_changed = pyqtSignal()
    display_changed = pyqtSignal(object)  # new Display
    camera_changed = pyqtSignal(object)  # new CameraComponent
    rect_changed = pyqtSignal(tuple)  # new rect (x, y, w, h)
    depth_changed = pyqtSignal(int)  # new depth value
    pipeline_changed = pyqtSignal(object)  # new RenderPipeline

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._viewport: Optional["Viewport"] = None
        self._displays: List["Display"] = []
        self._display_names: dict[int, str] = {}
        self._cameras: List[Tuple["CameraComponent", str]] = []  # (camera, name)
        self._scene: Optional["Scene"] = None
        self._pipelines: List[Tuple[str, Optional["RenderPipeline"]]] = []  # (name, pipeline or None)
        self._current_pipeline_name: Optional[str] = None
        self._get_editor_pipeline: Optional[Callable[[], "RenderPipeline"]] = None

        self._updating = False  # Prevent recursive updates

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Header
        header = QLabel("Viewport")
        header.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(header)

        # Form
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(4)

        # Display selection
        self._display_combo = QComboBox()
        self._display_combo.currentIndexChanged.connect(self._on_display_changed)
        form.addRow("Display:", self._display_combo)

        # Camera selection
        self._camera_combo = QComboBox()
        self._camera_combo.currentIndexChanged.connect(self._on_camera_changed)
        form.addRow("Camera:", self._camera_combo)

        # Rect section
        rect_label = QLabel("Rect (normalized 0..1):")
        form.addRow(rect_label)

        # X, Y row
        xy_widget = QWidget()
        xy_layout = QHBoxLayout(xy_widget)
        xy_layout.setContentsMargins(0, 0, 0, 0)
        xy_layout.setSpacing(4)

        xy_layout.addWidget(QLabel("X:"))
        self._x_spin = self._create_rect_spinbox()
        xy_layout.addWidget(self._x_spin)

        xy_layout.addWidget(QLabel("Y:"))
        self._y_spin = self._create_rect_spinbox()
        xy_layout.addWidget(self._y_spin)

        form.addRow(xy_widget)

        # Width, Height row
        wh_widget = QWidget()
        wh_layout = QHBoxLayout(wh_widget)
        wh_layout.setContentsMargins(0, 0, 0, 0)
        wh_layout.setSpacing(4)

        wh_layout.addWidget(QLabel("W:"))
        self._w_spin = self._create_rect_spinbox()
        self._w_spin.setValue(1.0)
        wh_layout.addWidget(self._w_spin)

        wh_layout.addWidget(QLabel("H:"))
        self._h_spin = self._create_rect_spinbox()
        self._h_spin.setValue(1.0)
        wh_layout.addWidget(self._h_spin)

        form.addRow(wh_widget)

        # Depth (render priority)
        self._depth_spin = QSpinBox()
        self._depth_spin.setRange(-1000, 1000)
        self._depth_spin.setValue(0)
        self._depth_spin.setToolTip("Render priority: lower values render first")
        self._depth_spin.valueChanged.connect(self._on_depth_changed)
        form.addRow("Depth:", self._depth_spin)

        # Pipeline selection
        self._pipeline_combo = QComboBox()
        self._pipeline_combo.setToolTip("Render pipeline for this viewport")
        self._pipeline_combo.currentIndexChanged.connect(self._on_pipeline_changed)
        form.addRow("Pipeline:", self._pipeline_combo)

        layout.addLayout(form)
        layout.addStretch()

    def _create_rect_spinbox(self) -> QDoubleSpinBox:
        """Create a spinbox for rect values (0..1)."""
        spin = QDoubleSpinBox()
        spin.setRange(0.0, 1.0)
        spin.setSingleStep(0.05)
        spin.setDecimals(3)
        spin.valueChanged.connect(self._on_rect_changed)
        return spin

    def set_displays(
        self,
        displays: List["Display"],
        display_names: Optional[dict[int, str]] = None
    ) -> None:
        """
        Set available displays for selection.

        Args:
            displays: List of Display objects.
            display_names: Optional dict mapping id(display) to name.
        """
        self._displays = list(displays)
        self._display_names = display_names or {}
        self._update_display_combo()

    def set_scene(self, scene: Optional["Scene"]) -> None:
        """
        Set the scene to find cameras from.

        Args:
            scene: Scene to scan for CameraComponent entities.
        """
        self._scene = scene
        self._update_camera_list()

    def set_viewport(self, viewport: Optional["Viewport"]) -> None:
        """
        Set the viewport to inspect.

        Args:
            viewport: Viewport to inspect, or None to clear.
        """
        self._viewport = viewport

        if viewport is None:
            self._clear()
            return

        self._updating = True
        try:
            # Update display selection
            self._update_display_combo()
            if viewport.display is not None and viewport.display in self._displays:
                idx = self._displays.index(viewport.display)
                self._display_combo.setCurrentIndex(idx)
            else:
                self._display_combo.setCurrentIndex(-1)

            # Update camera selection
            self._update_camera_list()
            camera_idx = -1
            for i, (cam, _name) in enumerate(self._cameras):
                if cam is viewport.camera:
                    camera_idx = i
                    break
            self._camera_combo.setCurrentIndex(camera_idx)

            # Update rect
            x, y, w, h = viewport.rect
            self._x_spin.setValue(x)
            self._y_spin.setValue(y)
            self._w_spin.setValue(w)
            self._h_spin.setValue(h)

            # Update depth
            self._depth_spin.setValue(viewport.depth)

            # Update pipeline list
            self.update_pipeline_list()
        finally:
            self._updating = False

    def _clear(self) -> None:
        """Clear all fields."""
        self._updating = True
        try:
            self._display_combo.setCurrentIndex(-1)
            self._camera_combo.setCurrentIndex(-1)
            self._x_spin.setValue(0.0)
            self._y_spin.setValue(0.0)
            self._w_spin.setValue(1.0)
            self._h_spin.setValue(1.0)
            self._depth_spin.setValue(0)
            self._pipeline_combo.setCurrentIndex(0)
            self._current_pipeline_name = None
        finally:
            self._updating = False

    def _update_display_combo(self) -> None:
        """Update display dropdown with current displays."""
        self._updating = True
        try:
            current_display = None
            if self._viewport is not None:
                current_display = self._viewport.display

            self._display_combo.clear()
            for i, display in enumerate(self._displays):
                if id(display) in self._display_names:
                    name = self._display_names[id(display)]
                else:
                    name = f"Display {i}"
                self._display_combo.addItem(name)

            # Restore selection
            if current_display is not None and current_display in self._displays:
                idx = self._displays.index(current_display)
                self._display_combo.setCurrentIndex(idx)
        finally:
            self._updating = False

    def _update_camera_list(self) -> None:
        """Update camera dropdown from scene."""
        self._updating = True
        try:
            current_camera = None
            if self._viewport is not None:
                current_camera = self._viewport.camera

            self._cameras.clear()
            self._camera_combo.clear()

            if self._scene is not None:
                from termin.visualization.core.camera import CameraComponent

                for entity in self._scene.entities:
                    camera = entity.get_component(CameraComponent)
                    if camera is not None:
                        name = entity.name or f"Camera ({id(camera)})"
                        self._cameras.append((camera, name))
                        self._camera_combo.addItem(name)

            # Restore selection
            if current_camera is not None:
                for i, (cam, _name) in enumerate(self._cameras):
                    if cam is current_camera:
                        self._camera_combo.setCurrentIndex(i)
                        break
        finally:
            self._updating = False

    def _on_display_changed(self, index: int) -> None:
        """Handle display selection change."""
        if self._updating or self._viewport is None:
            return

        if 0 <= index < len(self._displays):
            new_display = self._displays[index]
            self.display_changed.emit(new_display)
            self.viewport_changed.emit()

    def _on_camera_changed(self, index: int) -> None:
        """Handle camera selection change."""
        if self._updating or self._viewport is None:
            return

        if 0 <= index < len(self._cameras):
            new_camera, _name = self._cameras[index]
            self.camera_changed.emit(new_camera)
            self.viewport_changed.emit()

    def _on_rect_changed(self) -> None:
        """Handle rect value change."""
        if self._updating or self._viewport is None:
            return

        new_rect = (
            self._x_spin.value(),
            self._y_spin.value(),
            self._w_spin.value(),
            self._h_spin.value(),
        )
        self.rect_changed.emit(new_rect)
        self.viewport_changed.emit()

    def _on_depth_changed(self, value: int) -> None:
        """Handle depth value change."""
        if self._updating or self._viewport is None:
            return

        self.depth_changed.emit(value)
        self.viewport_changed.emit()

    def _on_pipeline_changed(self, index: int) -> None:
        """Handle pipeline selection change."""
        if self._updating or self._viewport is None:
            return

        if 0 <= index < len(self._pipelines):
            name, pipeline = self._pipelines[index]
            self._current_pipeline_name = name

            # Handle special "(Editor)" option
            if name == "(Editor)" and self._get_editor_pipeline is not None:
                pipeline = self._get_editor_pipeline()

            self.pipeline_changed.emit(pipeline)
            self.viewport_changed.emit()

    def set_editor_pipeline_getter(self, getter: Optional[Callable[[], "RenderPipeline"]]) -> None:
        """Set callback to get the editor pipeline."""
        self._get_editor_pipeline = getter

    def update_pipeline_list(self) -> None:
        """Update pipeline list from ResourceManager."""
        from termin.visualization.core.resources import ResourceManager

        rm = ResourceManager.instance()
        pipeline_names = rm.list_pipeline_names()

        self._updating = True
        try:
            self._pipelines.clear()
            self._pipeline_combo.clear()

            # Add "Default" option
            self._pipeline_combo.addItem("(Default)")
            self._pipelines.append(("(Default)", None))

            # Add "Editor" option if getter is available
            if self._get_editor_pipeline is not None:
                self._pipeline_combo.addItem("(Editor)")
                self._pipelines.append(("(Editor)", None))  # Pipeline created on demand

            for name in pipeline_names:
                pipeline = rm.get_pipeline(name)
                if pipeline is not None:
                    self._pipelines.append((name, pipeline))
                    self._pipeline_combo.addItem(name)

            # Restore selection
            if self._current_pipeline_name is not None:
                for i, (name, _) in enumerate(self._pipelines):
                    if name == self._current_pipeline_name:
                        self._pipeline_combo.setCurrentIndex(i)
                        break
        finally:
            self._updating = False

    def set_current_pipeline(self, pipeline: Optional["RenderPipeline"], name: Optional[str] = None) -> None:
        """Set the current pipeline selection."""
        self._current_pipeline_name = name

        self._updating = True
        try:
            if name is None or pipeline is None:
                self._pipeline_combo.setCurrentIndex(0)  # Default
            else:
                for i, (n, _) in enumerate(self._pipelines):
                    if n == name:
                        self._pipeline_combo.setCurrentIndex(i)
                        break
        finally:
            self._updating = False

    def refresh(self) -> None:
        """Refresh all data from current viewport."""
        self._update_camera_list()
        if self._viewport is not None:
            self.set_viewport(self._viewport)
