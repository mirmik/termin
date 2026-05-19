"""
ViewportInspector — inspector panel for Viewport properties.

Allows editing:
- Display selection
- Render target selection
- Rect (x, y, width, height in normalized 0..1 coords)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from tcbase import log

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)
from termin.editor.widgets.spinbox import DoubleSpinBox, SpinBox

if TYPE_CHECKING:
    from termin.visualization.core.display import Display
    from termin.visualization.core.scene import Scene
    from termin.visualization.core.viewport import Viewport


class ViewportInspector(QWidget):
    """
    Inspector panel for Viewport properties.

    Shows and allows editing:
    - Display (dropdown)
    - Render Target (dropdown)
    - Rect: x, y, width, height (spin boxes, 0..1)

    Signals:
        viewport_changed: Emitted when any property changes.
        display_changed: Emitted when display selection changes.
        rect_changed: Emitted when rect changes.
    """

    viewport_changed = pyqtSignal()
    display_changed = pyqtSignal(object)  # new Display
    scene_changed = pyqtSignal(object)  # new Scene
    rect_changed = pyqtSignal(tuple)  # new rect (x, y, w, h)
    depth_changed = pyqtSignal(int)  # new depth value
    enabled_changed = pyqtSignal(bool)  # new enabled state

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._viewport: Optional["Viewport"] = None
        self._current_display: Optional["Display"] = None
        self._displays: List["Display"] = []
        self._display_names: dict[int, str] = {}  # tc_display_ptr -> name
        self._scenes: List["Scene"] = []
        self._scene: Optional["Scene"] = None

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

        # Enabled checkbox
        self._enabled_checkbox = QCheckBox("Enabled")
        self._enabled_checkbox.setChecked(True)
        self._enabled_checkbox.setToolTip("Whether this viewport is rendered")
        self._enabled_checkbox.stateChanged.connect(self._on_enabled_changed)
        layout.addWidget(self._enabled_checkbox)

        # Form
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(4)

        # Display selection
        self._display_combo = QComboBox()
        self._display_combo.currentIndexChanged.connect(self._on_display_changed)
        form.addRow("Display:", self._display_combo)

        # Render target selection
        self._render_target_combo = QComboBox()
        self._render_target_combo.currentIndexChanged.connect(self._on_render_target_changed)
        form.addRow("Render Target:", self._render_target_combo)

        # Scene selection
        self._scene_combo = QComboBox()
        self._scene_combo.currentIndexChanged.connect(self._on_scene_changed)
        form.addRow("Scene:", self._scene_combo)

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
        self._depth_spin = SpinBox()
        self._depth_spin.setRange(-1000, 1000)
        self._depth_spin.setValue(0)
        self._depth_spin.setToolTip("Render priority: lower values render first")
        self._depth_spin.valueChanged.connect(self._on_depth_changed)
        form.addRow("Depth:", self._depth_spin)

        # Input mode
        self._input_mode_combo = QComboBox()
        self._input_mode_combo.addItem("none")
        self._input_mode_combo.addItem("simple")
        self._input_mode_combo.addItem("editor")
        self._input_mode_combo.currentTextChanged.connect(self._on_input_mode_changed)
        form.addRow("Input Mode:", self._input_mode_combo)

        # Block input in editor
        self._block_input_check = QCheckBox()
        self._block_input_check.toggled.connect(self._on_block_input_changed)
        form.addRow("Block in Editor:", self._block_input_check)

        # Scene pipeline label (shown when viewport is managed by scene pipeline)
        self._scene_pipeline_label = QLabel("Managed by scene pipeline")
        self._scene_pipeline_label.setStyleSheet("color: #6a9; font-style: italic;")
        self._scene_pipeline_label.hide()
        form.addRow(self._scene_pipeline_label)

        layout.addLayout(form)

        # Debug info section
        debug_header = QLabel("Native State")
        debug_header.setStyleSheet("font-weight: bold; font-size: 12px; margin-top: 8px;")
        layout.addWidget(debug_header)

        self._debug_label = QLabel("-")
        self._debug_label.setStyleSheet("font-family: monospace; font-size: 11px; color: #aaa;")
        self._debug_label.setWordWrap(True)
        self._debug_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._debug_label)

        layout.addStretch()

    def _create_rect_spinbox(self) -> DoubleSpinBox:
        """Create a spinbox for rect values (0..1)."""
        spin = DoubleSpinBox()
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
            display_names: Optional dict mapping tc_display_ptr to name.
        """
        self._displays = list(displays)
        self._display_names = display_names or {}
        self._update_display_combo()

    def set_scene(self, scene: Optional["Scene"]) -> None:
        """Set the scene (kept for API compat, camera/pipeline now on render_target)."""
        self._scene = scene

    def set_scenes(self, scenes: List["Scene"]) -> None:
        """Set available scenes for the scene dropdown."""
        self._scenes = list(scenes)
        self._refresh_scene_combo()
        self._select_current_scene()

    def set_viewport(self, viewport: Optional["Viewport"], current_display: Optional["Display"] = None) -> None:
        """
        Set the viewport to inspect.

        Args:
            viewport: Viewport to inspect, or None to clear.
            current_display: Display that contains this viewport.
        """
        self._viewport = viewport
        self._current_display = current_display

        if viewport is None:
            self._clear()
            return

        self._updating = True
        try:
            # Update enabled checkbox
            self._enabled_checkbox.setChecked(viewport.enabled)

            # Update display selection
            self._update_display_combo()
            if current_display is not None and current_display in self._displays:
                idx = self._displays.index(current_display)
                self._display_combo.setCurrentIndex(idx)
            else:
                self._display_combo.setCurrentIndex(-1)

            # Update render target combo
            self._update_render_target_combo()
            self._select_current_render_target()

            # Update scene combo
            self._refresh_scene_combo()
            self._select_current_scene()

            # Update rect
            x, y, w, h = viewport.rect
            self._x_spin.setValue(x)
            self._y_spin.setValue(y)
            self._w_spin.setValue(w)
            self._h_spin.setValue(h)

            # Update depth
            self._depth_spin.setValue(viewport.depth)

            # Update input mode
            self._input_mode_combo.blockSignals(True)
            mode = viewport.input_mode or "none"
            idx = self._input_mode_combo.findText(mode)
            self._input_mode_combo.setCurrentIndex(idx if idx >= 0 else 0)
            self._input_mode_combo.blockSignals(False)

            # Update block input in editor
            self._block_input_check.blockSignals(True)
            self._block_input_check.setChecked(viewport.block_input_in_editor)
            self._block_input_check.blockSignals(False)

            # Debug info
            self._update_debug_info(viewport)
        finally:
            self._updating = False

    def _update_scene_pipeline_state(self, viewport: "Viewport") -> None:
        """Update scene pipeline label visibility."""
        if viewport.managed_by_scene_pipeline:
            self._scene_pipeline_label.setText(
                f"Managed by scene pipeline: {viewport.managed_by_scene_pipeline}"
            )
            self._scene_pipeline_label.show()
        else:
            self._scene_pipeline_label.hide()

    def _clear(self) -> None:
        """Clear all fields."""
        self._updating = True
        try:
            self._enabled_checkbox.setChecked(True)
            self._display_combo.setCurrentIndex(-1)
            self._render_target_combo.setCurrentIndex(0)
            self._scene_combo.setCurrentIndex(-1)
            self._x_spin.setValue(0.0)
            self._y_spin.setValue(0.0)
            self._w_spin.setValue(1.0)
            self._h_spin.setValue(1.0)
            self._depth_spin.setValue(0)
            self._input_mode_combo.setCurrentIndex(0)
            self._block_input_check.setChecked(False)
            self._scene_pipeline_label.hide()
            self._debug_label.setText("-")
        finally:
            self._updating = False

    def _update_display_combo(self) -> None:
        """Update display dropdown with current displays."""
        self._updating = True
        try:
            self._display_combo.clear()
            for i, display in enumerate(self._displays):
                if display.tc_display_ptr in self._display_names:
                    name = self._display_names[display.tc_display_ptr]
                else:
                    name = f"Display {i}"
                self._display_combo.addItem(name)

            # Restore selection
            if self._current_display is not None and self._current_display in self._displays:
                idx = self._displays.index(self._current_display)
                self._display_combo.setCurrentIndex(idx)
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

    def _update_render_target_combo(self) -> None:
        """Populate render target combo from pool."""
        self._render_target_combo.blockSignals(True)
        self._render_target_combo.clear()
        self._render_target_combo.addItem("(none)")
        try:
            from termin.render_framework._render_framework_native import render_target_pool_list
            self._render_target_list = render_target_pool_list()
            for rt in self._render_target_list:
                self._render_target_combo.addItem(rt.name or "(unnamed)")
        except Exception as e:
            log.debug(f"[ViewportInspector] Failed to load render targets: {e}")
            self._render_target_list = []
        self._render_target_combo.blockSignals(False)

    def _select_current_render_target(self) -> None:
        """Select current viewport's render target in combo."""
        if self._viewport is None:
            self._render_target_combo.setCurrentIndex(0)
            return
        rt = self._viewport.render_target
        if rt is None:
            self._render_target_combo.setCurrentIndex(0)
            return
        for i, pool_rt in enumerate(self._render_target_list):
            if pool_rt.index == rt.index and pool_rt.generation == rt.generation:
                self._render_target_combo.setCurrentIndex(i + 1)
                return
        self._render_target_combo.setCurrentIndex(0)

    def _on_render_target_changed(self, index: int) -> None:
        """Handle render target combo change."""
        if self._updating or self._viewport is None:
            return
        if index <= 0:
            self._viewport.render_target = None
            self.viewport_changed.emit()
            return
        rt_list = self._render_target_list
        idx = index - 1
        if 0 <= idx < len(rt_list):
            self._viewport.render_target = rt_list[idx]
            self.viewport_changed.emit()

    def _refresh_scene_combo(self) -> None:
        """Populate scene combo with available scenes."""
        self._scene_combo.blockSignals(True)
        self._scene_combo.clear()
        for scene in self._scenes:
            self._scene_combo.addItem(scene.name or "(unnamed)")
        self._scene_combo.blockSignals(False)

    def _select_current_scene(self) -> None:
        """Select current viewport's scene in combo."""
        if self._viewport is None:
            self._scene_combo.setCurrentIndex(-1)
            return
        vp_scene = self._viewport.scene
        if vp_scene is None:
            self._scene_combo.setCurrentIndex(-1)
            return
        for i, scene in enumerate(self._scenes):
            if scene.equal(vp_scene):
                self._scene_combo.setCurrentIndex(i)
                return
        self._scene_combo.setCurrentIndex(-1)

    def _on_scene_changed(self, index: int) -> None:
        """Handle scene selection change."""
        if self._updating or self._viewport is None:
            return
        if 0 <= index < len(self._scenes):
            new_scene = self._scenes[index]
            self.scene_changed.emit(new_scene)
            self.viewport_changed.emit()

    def _on_input_mode_changed(self, text: str) -> None:
        if self._updating or self._viewport is None:
            return
        self._viewport.input_mode = text
        self.viewport_changed.emit()

    def _on_block_input_changed(self, checked: bool) -> None:
        if self._updating or self._viewport is None:
            return
        self._viewport.block_input_in_editor = checked
        self.viewport_changed.emit()

    def _on_enabled_changed(self, state: int) -> None:
        """Handle enabled checkbox change."""
        if self._updating or self._viewport is None:
            return

        enabled = state != 0
        self.enabled_changed.emit(enabled)
        self.viewport_changed.emit()

    def _update_debug_info(self, viewport: "Viewport") -> None:
        """Update debug info label with native state."""
        try:
            from termin.display import _viewport_get_input_manager

            vh = viewport._viewport_handle()
            vp_index, vp_generation = vh
            vp_im = _viewport_get_input_manager(vp_index, vp_generation)

            lines = [
                f"handle: idx={vp_index} gen={vp_generation}",
                f"name:   {viewport.name}",
                f"im:     0x{vp_im:X}" + (" (NULL)" if vp_im == 0 else ""),
            ]

            # Show input_mode field
            input_mode = viewport.input_mode
            lines.append(f"input_mode: {input_mode!r}")

            self._debug_label.setText("\n".join(lines))
        except Exception as e:
            self._debug_label.setText(f"Error: {e}")

    def refresh(self) -> None:
        """Refresh all data from current viewport."""
        if self._viewport is not None:
            self.set_viewport(self._viewport)
