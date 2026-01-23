"""
Pipeline Inspector for the editor.

Displays and allows editing of RenderPipeline configuration:
- List of passes with enable/disable toggles
- Pass parameters editing
- PostEffect list for PostProcessPass
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QFrame,
    QCheckBox,
    QMessageBox,
    QComboBox,
    QInputDialog,
    QGroupBox,
    QLineEdit,
)
from PyQt6.QtCore import Qt, pyqtSignal

from termin.editor.inspect_field_panel import InspectFieldPanel

if TYPE_CHECKING:
    from termin.visualization.render.framegraph.pipeline import RenderPipeline
    from termin.visualization.render.postprocess import PostProcessPass, PostEffect


class PipelineInspector(QWidget):
    """
    Inspector for RenderPipeline.

    Displays:
    - Pipeline name
    - List of passes with enable/disable
    - Selected pass parameters
    """

    pipeline_changed = pyqtSignal(object)  # emits RenderPipeline or None
    apply_to_viewport = pyqtSignal(object)  # emits RenderPipeline

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._pipeline: Optional["RenderPipeline"] = None
        self._pipeline_name: str = ""
        self._source_path: Optional[str] = None
        self._selected_postprocess: Optional["PostProcessPass"] = None
        self._selected_spec_index: int = -1
        self._updating_spec_ui: bool = False  # Prevent recursive updates

        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(8)

        # Header
        title = QLabel("Pipeline Inspector")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        main_layout.addWidget(title)

        # Pipeline name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Name:"))
        self._name_label = QLabel("")
        self._name_label.setStyleSheet("color: #aaa;")
        name_layout.addWidget(self._name_label, 1)
        main_layout.addLayout(name_layout)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(line)

        # Passes section
        passes_label = QLabel("Passes:")
        passes_label.setStyleSheet("font-weight: bold;")
        main_layout.addWidget(passes_label)

        # Pass list with buttons
        list_layout = QHBoxLayout()

        self._pass_list = QListWidget()
        self._pass_list.setMaximumHeight(200)
        self._pass_list.itemChanged.connect(self._on_pass_toggled)
        self._pass_list.currentRowChanged.connect(self._on_pass_selected)
        list_layout.addWidget(self._pass_list)

        # Buttons for pass management
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(4)

        self._add_btn = QPushButton("+")
        self._add_btn.setFixedSize(28, 28)
        self._add_btn.setToolTip("Add pass")
        self._add_btn.clicked.connect(self._on_add_pass)
        btn_layout.addWidget(self._add_btn)

        self._remove_btn = QPushButton("−")
        self._remove_btn.setFixedSize(28, 28)
        self._remove_btn.setToolTip("Remove selected pass")
        self._remove_btn.clicked.connect(self._on_remove_pass)
        btn_layout.addWidget(self._remove_btn)

        btn_layout.addSpacing(8)

        self._up_btn = QPushButton("▲")
        self._up_btn.setFixedSize(28, 28)
        self._up_btn.setToolTip("Move pass up")
        self._up_btn.clicked.connect(self._on_move_up)
        btn_layout.addWidget(self._up_btn)

        self._down_btn = QPushButton("▼")
        self._down_btn.setFixedSize(28, 28)
        self._down_btn.setToolTip("Move pass down")
        self._down_btn.clicked.connect(self._on_move_down)
        btn_layout.addWidget(self._down_btn)

        btn_layout.addStretch()
        list_layout.addLayout(btn_layout)

        main_layout.addLayout(list_layout)

        # Pass details area
        details_label = QLabel("Pass Details:")
        details_label.setStyleSheet("font-weight: bold;")
        main_layout.addWidget(details_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._details_widget = QWidget()
        self._details_layout = QVBoxLayout(self._details_widget)
        self._details_layout.setContentsMargins(0, 0, 0, 0)
        self._details_layout.setSpacing(4)

        # Basic info label
        self._details_info = QLabel("Select a pass to view details")
        self._details_info.setStyleSheet("color: #888;")
        self._details_layout.addWidget(self._details_info)

        # Pass name field
        pass_name_layout = QHBoxLayout()
        pass_name_layout.addWidget(QLabel("Name:"))
        self._pass_name_edit = QLineEdit()
        self._pass_name_edit.setPlaceholderText("Pass name")
        self._pass_name_edit.editingFinished.connect(self._on_pass_name_changed)
        pass_name_layout.addWidget(self._pass_name_edit)
        self._details_layout.addLayout(pass_name_layout)

        # Editable fields panel
        self._pass_inspector = InspectFieldPanel(parent=self._details_widget)
        self._pass_inspector.field_changed.connect(self._on_pass_field_changed)
        self._details_layout.addWidget(self._pass_inspector)

        # Set resources for handle widgets
        from termin.visualization.core.resources import ResourceManager
        rm = ResourceManager.instance()
        self._pass_inspector.set_resources(rm)

        # PostEffect section (shown only for PostProcessPass)
        self._effects_group = QGroupBox("Post Effects")
        self._effects_group.setVisible(False)
        effects_layout = QVBoxLayout(self._effects_group)
        effects_layout.setContentsMargins(4, 4, 4, 4)
        effects_layout.setSpacing(4)

        # Effects list with buttons
        effects_list_layout = QHBoxLayout()

        self._effects_list = QListWidget()
        self._effects_list.setMaximumHeight(120)
        self._effects_list.currentRowChanged.connect(self._on_effect_selected)
        effects_list_layout.addWidget(self._effects_list)

        # Buttons for effect management
        effects_btn_layout = QVBoxLayout()
        effects_btn_layout.setSpacing(4)

        self._add_effect_btn = QPushButton("+")
        self._add_effect_btn.setFixedSize(24, 24)
        self._add_effect_btn.setToolTip("Add effect")
        self._add_effect_btn.clicked.connect(self._on_add_effect)
        effects_btn_layout.addWidget(self._add_effect_btn)

        self._remove_effect_btn = QPushButton("−")
        self._remove_effect_btn.setFixedSize(24, 24)
        self._remove_effect_btn.setToolTip("Remove effect")
        self._remove_effect_btn.clicked.connect(self._on_remove_effect)
        effects_btn_layout.addWidget(self._remove_effect_btn)

        effects_btn_layout.addSpacing(4)

        self._effect_up_btn = QPushButton("▲")
        self._effect_up_btn.setFixedSize(24, 24)
        self._effect_up_btn.setToolTip("Move effect up")
        self._effect_up_btn.clicked.connect(self._on_effect_move_up)
        effects_btn_layout.addWidget(self._effect_up_btn)

        self._effect_down_btn = QPushButton("▼")
        self._effect_down_btn.setFixedSize(24, 24)
        self._effect_down_btn.setToolTip("Move effect down")
        self._effect_down_btn.clicked.connect(self._on_effect_move_down)
        effects_btn_layout.addWidget(self._effect_down_btn)

        effects_btn_layout.addStretch()
        effects_list_layout.addLayout(effects_btn_layout)

        effects_layout.addLayout(effects_list_layout)

        # Effect name field
        effect_name_layout = QHBoxLayout()
        effect_name_layout.addWidget(QLabel("Name:"))
        self._effect_name_edit = QLineEdit()
        self._effect_name_edit.setPlaceholderText("Effect name")
        self._effect_name_edit.editingFinished.connect(self._on_effect_name_changed)
        effect_name_layout.addWidget(self._effect_name_edit)
        effects_layout.addLayout(effect_name_layout)

        # Effect inspector
        self._effect_inspector = InspectFieldPanel(parent=self._effects_group)
        self._effect_inspector.field_changed.connect(self._on_effect_field_changed)
        self._effect_inspector.set_resources(rm)
        effects_layout.addWidget(self._effect_inspector)

        self._details_layout.addWidget(self._effects_group)

        self._details_layout.addStretch()

        scroll.setWidget(self._details_widget)
        main_layout.addWidget(scroll, 1)

        # Resource Specs section (pipeline-level FBO configuration)
        specs_group = QGroupBox("Resource Specs (FBO)")
        specs_group_layout = QVBoxLayout(specs_group)
        specs_group_layout.setContentsMargins(4, 4, 4, 4)
        specs_group_layout.setSpacing(4)

        # Specs list with buttons
        specs_list_layout = QHBoxLayout()

        self._specs_list = QListWidget()
        self._specs_list.setMaximumHeight(100)
        self._specs_list.currentRowChanged.connect(self._on_spec_selected)
        specs_list_layout.addWidget(self._specs_list)

        # Buttons for spec management
        specs_btn_layout = QVBoxLayout()
        specs_btn_layout.setSpacing(4)

        self._add_spec_btn = QPushButton("+")
        self._add_spec_btn.setFixedSize(24, 24)
        self._add_spec_btn.setToolTip("Add resource spec")
        self._add_spec_btn.clicked.connect(self._on_add_spec)
        specs_btn_layout.addWidget(self._add_spec_btn)

        self._remove_spec_btn = QPushButton("−")
        self._remove_spec_btn.setFixedSize(24, 24)
        self._remove_spec_btn.setToolTip("Remove resource spec")
        self._remove_spec_btn.clicked.connect(self._on_remove_spec)
        specs_btn_layout.addWidget(self._remove_spec_btn)

        specs_btn_layout.addStretch()
        specs_list_layout.addLayout(specs_btn_layout)

        specs_group_layout.addLayout(specs_list_layout)

        # Spec editor
        self._spec_editor_widget = QWidget()
        spec_editor_layout = QVBoxLayout(self._spec_editor_widget)
        spec_editor_layout.setContentsMargins(0, 0, 0, 0)
        spec_editor_layout.setSpacing(4)

        # Resource name
        res_layout = QHBoxLayout()
        res_layout.addWidget(QLabel("Resource:"))
        self._spec_resource_edit = QLineEdit()
        self._spec_resource_edit.setPlaceholderText("e.g., empty, color, id")
        self._spec_resource_edit.editingFinished.connect(self._on_spec_field_changed)
        res_layout.addWidget(self._spec_resource_edit)
        spec_editor_layout.addLayout(res_layout)

        # Samples (MSAA)
        samples_layout = QHBoxLayout()
        samples_layout.addWidget(QLabel("Samples:"))
        self._spec_samples_combo = QComboBox()
        self._spec_samples_combo.addItems(["1 (No MSAA)", "2", "4", "8"])
        self._spec_samples_combo.currentIndexChanged.connect(self._on_spec_field_changed)
        samples_layout.addWidget(self._spec_samples_combo)
        samples_layout.addStretch()
        spec_editor_layout.addLayout(samples_layout)

        # Format (RGBA8, RGBA16F for HDR, etc.)
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("Format:"))
        self._spec_format_combo = QComboBox()
        self._spec_format_combo.addItems([
            "rgba8 (Default)",
            "rgba16f (HDR)",
            "rgba32f (HDR High Precision)",
            "r8 (Single Channel 8-bit)",
            "r16f (Single Channel Float)",
            "r32f (Single Channel High Precision)",
        ])
        self._spec_format_combo.currentIndexChanged.connect(self._on_spec_field_changed)
        format_layout.addWidget(self._spec_format_combo)
        format_layout.addStretch()
        spec_editor_layout.addLayout(format_layout)

        # Clear color
        clear_color_layout = QHBoxLayout()
        self._spec_clear_color_check = QCheckBox("Clear Color:")
        self._spec_clear_color_check.stateChanged.connect(self._on_spec_field_changed)
        clear_color_layout.addWidget(self._spec_clear_color_check)
        self._spec_clear_r = QLineEdit("0.0")
        self._spec_clear_r.setFixedWidth(50)
        self._spec_clear_r.editingFinished.connect(self._on_spec_field_changed)
        self._spec_clear_g = QLineEdit("0.0")
        self._spec_clear_g.setFixedWidth(50)
        self._spec_clear_g.editingFinished.connect(self._on_spec_field_changed)
        self._spec_clear_b = QLineEdit("0.0")
        self._spec_clear_b.setFixedWidth(50)
        self._spec_clear_b.editingFinished.connect(self._on_spec_field_changed)
        self._spec_clear_a = QLineEdit("1.0")
        self._spec_clear_a.setFixedWidth(50)
        self._spec_clear_a.editingFinished.connect(self._on_spec_field_changed)
        clear_color_layout.addWidget(self._spec_clear_r)
        clear_color_layout.addWidget(self._spec_clear_g)
        clear_color_layout.addWidget(self._spec_clear_b)
        clear_color_layout.addWidget(self._spec_clear_a)
        clear_color_layout.addStretch()
        spec_editor_layout.addLayout(clear_color_layout)

        # Clear depth
        clear_depth_layout = QHBoxLayout()
        self._spec_clear_depth_check = QCheckBox("Clear Depth:")
        self._spec_clear_depth_check.stateChanged.connect(self._on_spec_field_changed)
        clear_depth_layout.addWidget(self._spec_clear_depth_check)
        self._spec_clear_depth = QLineEdit("1.0")
        self._spec_clear_depth.setFixedWidth(50)
        self._spec_clear_depth.editingFinished.connect(self._on_spec_field_changed)
        clear_depth_layout.addWidget(self._spec_clear_depth)
        clear_depth_layout.addStretch()
        spec_editor_layout.addLayout(clear_depth_layout)

        self._spec_editor_widget.setVisible(False)
        specs_group_layout.addWidget(self._spec_editor_widget)

        main_layout.addWidget(specs_group)
        self._specs_group = specs_group

        # Save button
        self._save_btn = QPushButton("Save")
        self._save_btn.clicked.connect(self._on_save_clicked)
        main_layout.addWidget(self._save_btn)

    def set_pipeline(
        self,
        pipeline: Optional["RenderPipeline"],
        name: str = "",
        source_path: Optional[str] = None,
    ) -> None:
        """Set the pipeline to inspect."""
        self._pipeline = pipeline
        self._pipeline_name = name
        self._source_path = source_path
        self._rebuild_ui()

    def load_pipeline_file(self, path: str | Path) -> None:
        """Load pipeline from .pipeline file."""
        from termin.visualization.core.resources import ResourceManager
        from termin.visualization.render.framegraph.pipeline import RenderPipeline

        path = Path(path)
        if not path.exists():
            return

        rm = ResourceManager.instance()
        pipeline_name = path.stem

        # Try to get from ResourceManager first (loaded by watcher)
        pipeline = rm.get_pipeline(pipeline_name)

        if pipeline is None:
            # Load directly
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                pipeline = RenderPipeline.deserialize(data, rm)
            except Exception as e:
                QMessageBox.warning(
                    self,
                    "Error Loading Pipeline",
                    f"Failed to load pipeline:\n{path}\n\nError: {e}",
                )
                return

        self.set_pipeline(pipeline, pipeline_name, str(path))
        self.pipeline_changed.emit(self._pipeline)

    def save_pipeline_file(self, path: str | Path | None = None) -> bool:
        """Save pipeline to .pipeline file."""
        if self._pipeline is None:
            return False

        if path is None:
            path = self._source_path

        if path is None:
            return False

        path = Path(path)

        try:
            data = self._pipeline.serialize()

            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            return True

        except Exception as e:
            import traceback
            QMessageBox.critical(
                self,
                "Error Saving Pipeline",
                f"Failed to save pipeline:\n{path}\n\nError: {e}\n\n{traceback.format_exc()}",
            )
            return False

    def _rebuild_ui(self) -> None:
        """Rebuild UI for current pipeline."""
        self._pass_list.clear()
        self._pass_inspector.set_target(None)
        self._pass_name_edit.clear()
        self._pass_name_edit.setEnabled(False)
        self._selected_postprocess = None
        self._effects_list.clear()
        self._effect_inspector.set_target(None)
        self._effect_name_edit.clear()
        self._effect_name_edit.setEnabled(False)
        self._effects_group.setVisible(False)
        self._specs_list.clear()
        self._spec_editor_widget.setVisible(False)
        self._selected_spec_index = -1

        if self._pipeline is None:
            self._name_label.setText("")
            self._details_info.setText("No pipeline loaded")
            self._update_buttons_state()
            self._update_specs_buttons_state()
            return

        self._name_label.setText(self._pipeline_name)

        # Add passes to list
        for p in self._pipeline.passes:
            item = QListWidgetItem(f"{p.pass_name} ({p.__class__.__name__})")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if p.enabled else Qt.CheckState.Unchecked
            )
            self._pass_list.addItem(item)

        # Add specs to list
        self._rebuild_specs_list()

        self._details_info.setText("Select a pass to view details")
        self._update_buttons_state()
        self._update_specs_buttons_state()

    def _on_pass_toggled(self, item: QListWidgetItem) -> None:
        """Handle pass enable/disable toggle."""
        if self._pipeline is None:
            return

        row = self._pass_list.row(item)
        if 0 <= row < len(self._pipeline.passes):
            enabled = item.checkState() == Qt.CheckState.Checked
            self._pipeline.passes[row].enabled = enabled
            self.pipeline_changed.emit(self._pipeline)

    def _on_pass_selected(self, row: int) -> None:
        """Handle pass selection - show details."""
        self._update_buttons_state()
        self._selected_postprocess = None
        self._effects_list.clear()
        self._effect_inspector.set_target(None)

        if self._pipeline is None or row < 0 or row >= len(self._pipeline.passes):
            self._details_info.setText("Select a pass to view details")
            self._pass_inspector.set_target(None)
            self._pass_name_edit.clear()
            self._pass_name_edit.setEnabled(False)
            self._effects_group.setVisible(False)
            return

        p = self._pipeline.passes[row]

        # Show basic pass info
        info_lines = [
            f"Type: {p.__class__.__name__}",
            f"Reads: {', '.join(p.reads) or 'none'}",
            f"Writes: {', '.join(p.writes) or 'none'}",
        ]
        self._details_info.setText("\n".join(info_lines))

        # Update name field
        self._pass_name_edit.setEnabled(True)
        self._pass_name_edit.blockSignals(True)
        self._pass_name_edit.setText(p.pass_name)
        self._pass_name_edit.blockSignals(False)

        # Set target for editable fields
        self._pass_inspector.set_target(p)

        # Check if this is a PostProcessPass
        from termin.visualization.render.postprocess import PostProcessPass

        if isinstance(p, PostProcessPass):
            self._selected_postprocess = p
            self._effects_group.setVisible(True)
            self._rebuild_effects_list()
        else:
            self._effects_group.setVisible(False)

    def _on_pass_field_changed(self, key: str, old_value, new_value) -> None:
        """Handle pass field change from inspector."""
        self.pipeline_changed.emit(self._pipeline)

    def _on_pass_name_changed(self) -> None:
        """Handle pass name change."""
        if self._pipeline is None:
            return

        row = self._pass_list.currentRow()
        if row < 0 or row >= len(self._pipeline.passes):
            return

        p = self._pipeline.passes[row]
        new_name = self._pass_name_edit.text().strip()

        if new_name and new_name != p.pass_name:
            p.pass_name = new_name
            # Update list item text
            item = self._pass_list.item(row)
            if item:
                item.setText(f"{new_name} ({p.__class__.__name__})")
            self.pipeline_changed.emit(self._pipeline)

    # ---------- PostEffect handling ----------

    def _rebuild_effects_list(self) -> None:
        """Rebuild the effects list for the selected PostProcessPass."""
        self._effects_list.clear()

        if self._selected_postprocess is None:
            return

        for eff in self._selected_postprocess.effects:
            name = eff.name if hasattr(eff, "name") else eff.__class__.__name__
            item = QListWidgetItem(f"{name} ({eff.__class__.__name__})")
            self._effects_list.addItem(item)

        self._update_effect_buttons_state()

    def _on_effect_selected(self, row: int) -> None:
        """Handle effect selection - show effect inspector."""
        self._update_effect_buttons_state()

        if self._selected_postprocess is None:
            self._effect_inspector.set_target(None)
            self._effect_name_edit.clear()
            self._effect_name_edit.setEnabled(False)
            return

        if row < 0 or row >= len(self._selected_postprocess.effects):
            self._effect_inspector.set_target(None)
            self._effect_name_edit.clear()
            self._effect_name_edit.setEnabled(False)
            return

        eff = self._selected_postprocess.effects[row]
        self._effect_inspector.set_target(eff)

        # Update name field
        self._effect_name_edit.setEnabled(True)
        self._effect_name_edit.blockSignals(True)
        self._effect_name_edit.setText(eff.name if hasattr(eff, "name") else "")
        self._effect_name_edit.blockSignals(False)

    def _on_add_effect(self) -> None:
        """Add a new effect to the PostProcessPass."""
        if self._selected_postprocess is None:
            return

        from termin.visualization.core.resources import ResourceManager

        rm = ResourceManager.instance()
        effect_names = rm.list_post_effect_names()

        if not effect_names:
            QMessageBox.warning(
                self,
                "No Effects Available",
                "No PostEffect types registered.",
            )
            return

        # Show selection dialog
        effect_type, ok = QInputDialog.getItem(
            self,
            "Add Effect",
            "Select effect type:",
            effect_names,
            0,
            False,
        )

        if not ok or not effect_type:
            return

        # Get effect class and create instance
        effect_cls = rm.get_post_effect(effect_type)
        if effect_cls is None:
            return

        try:
            new_effect = effect_cls()
            self._selected_postprocess.effects.append(new_effect)
            self._rebuild_effects_list()
            self.pipeline_changed.emit(self._pipeline)
        except Exception as e:
            QMessageBox.warning(
                self,
                "Error Creating Effect",
                f"Failed to create effect:\n{e}",
            )

    def _on_remove_effect(self) -> None:
        """Remove the selected effect from the PostProcessPass."""
        if self._selected_postprocess is None:
            return

        row = self._effects_list.currentRow()
        if row < 0 or row >= len(self._selected_postprocess.effects):
            return

        eff = self._selected_postprocess.effects[row]
        name = eff.name if hasattr(eff, "name") else eff.__class__.__name__

        reply = QMessageBox.question(
            self,
            "Remove Effect",
            f"Remove effect '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        del self._selected_postprocess.effects[row]
        self._rebuild_effects_list()
        self._effect_inspector.set_target(None)
        self.pipeline_changed.emit(self._pipeline)

    def _on_effect_field_changed(self, key: str, old_value, new_value) -> None:
        """Handle effect field change from inspector."""
        self.pipeline_changed.emit(self._pipeline)

    def _on_effect_name_changed(self) -> None:
        """Handle effect name change."""
        if self._selected_postprocess is None:
            return

        row = self._effects_list.currentRow()
        if row < 0 or row >= len(self._selected_postprocess.effects):
            return

        eff = self._selected_postprocess.effects[row]
        new_name = self._effect_name_edit.text().strip()

        if new_name and new_name != eff.name:
            eff.name = new_name
            self._rebuild_effects_list()
            self._effects_list.setCurrentRow(row)
            self.pipeline_changed.emit(self._pipeline)

    def _on_effect_move_up(self) -> None:
        """Move the selected effect up in the list."""
        if self._selected_postprocess is None:
            return

        row = self._effects_list.currentRow()
        if row <= 0 or row >= len(self._selected_postprocess.effects):
            return

        # Swap effects
        effects = self._selected_postprocess.effects
        effects[row], effects[row - 1] = effects[row - 1], effects[row]

        self._rebuild_effects_list()
        self._effects_list.setCurrentRow(row - 1)
        self.pipeline_changed.emit(self._pipeline)

    def _on_effect_move_down(self) -> None:
        """Move the selected effect down in the list."""
        if self._selected_postprocess is None:
            return

        row = self._effects_list.currentRow()
        if row < 0 or row >= len(self._selected_postprocess.effects) - 1:
            return

        # Swap effects
        effects = self._selected_postprocess.effects
        effects[row], effects[row + 1] = effects[row + 1], effects[row]

        self._rebuild_effects_list()
        self._effects_list.setCurrentRow(row + 1)
        self.pipeline_changed.emit(self._pipeline)

    def _update_effect_buttons_state(self) -> None:
        """Update enabled state of effect buttons."""
        has_postprocess = self._selected_postprocess is not None
        row = self._effects_list.currentRow()
        has_selection = row >= 0

        self._add_effect_btn.setEnabled(has_postprocess)
        self._remove_effect_btn.setEnabled(has_postprocess and has_selection)

        # Up/down buttons
        if has_postprocess and has_selection:
            num_effects = len(self._selected_postprocess.effects)
            self._effect_up_btn.setEnabled(row > 0)
            self._effect_down_btn.setEnabled(row < num_effects - 1)
        else:
            self._effect_up_btn.setEnabled(False)
            self._effect_down_btn.setEnabled(False)

    def _on_save_clicked(self) -> None:
        """Handle save button click."""
        if self.save_pipeline_file():
            pass  # Could show success notification

    def _on_add_pass(self) -> None:
        """Add a new pass to the pipeline."""
        if self._pipeline is None:
            return

        from termin.visualization.core.resources import ResourceManager

        rm = ResourceManager.instance()
        pass_names = rm.list_frame_pass_names()

        if not pass_names:
            QMessageBox.warning(
                self,
                "No Passes Available",
                "No FramePass types registered.",
            )
            return

        # Show selection dialog
        pass_type, ok = QInputDialog.getItem(
            self,
            "Add Pass",
            "Select pass type:",
            pass_names,
            0,
            False,
        )

        if not ok or not pass_type:
            return

        # Get pass class and create instance
        pass_cls = rm.get_frame_pass(pass_type)
        if pass_cls is None:
            return

        # Ask for pass name
        pass_name, ok = QInputDialog.getText(
            self,
            "Pass Name",
            "Enter pass name:",
            text=pass_type,
        )

        if not ok or not pass_name:
            return

        try:
            # Create pass with default parameters
            new_pass = pass_cls(pass_name=pass_name)

            # Insert after current selection or at end
            row = self._pass_list.currentRow()
            if row < 0:
                self._pipeline.add_pass(new_pass)
            else:
                self._pipeline.insert_pass(row + 1, new_pass)

            self._rebuild_ui()
            self.pipeline_changed.emit(self._pipeline)

        except Exception as e:
            QMessageBox.warning(
                self,
                "Error Creating Pass",
                f"Failed to create pass:\n{e}",
            )

    def _on_remove_pass(self) -> None:
        """Remove the selected pass from the pipeline."""
        if self._pipeline is None:
            return

        row = self._pass_list.currentRow()
        if row < 0 or row >= len(self._pipeline.passes):
            return

        pass_obj = self._pipeline.passes[row]

        reply = QMessageBox.question(
            self,
            "Remove Pass",
            f"Remove pass '{pass_obj.pass_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        self._pipeline.remove_pass(pass_obj)
        self._rebuild_ui()
        self.pipeline_changed.emit(self._pipeline)

    def _on_move_up(self) -> None:
        """Move the selected pass up in the list."""
        if self._pipeline is None:
            return

        row = self._pass_list.currentRow()
        if row <= 0 or row >= len(self._pipeline.passes):
            return

        # Move pass up
        self._pipeline.move_pass(row, row - 1)

        self._rebuild_ui()
        self._pass_list.setCurrentRow(row - 1)
        self.pipeline_changed.emit(self._pipeline)

    def _on_move_down(self) -> None:
        """Move the selected pass down in the list."""
        if self._pipeline is None:
            return

        row = self._pass_list.currentRow()
        if row < 0 or row >= len(self._pipeline.passes) - 1:
            return

        # Move pass down
        self._pipeline.move_pass(row, row + 1)

        self._rebuild_ui()
        self._pass_list.setCurrentRow(row + 1)
        self.pipeline_changed.emit(self._pipeline)

    def _update_buttons_state(self) -> None:
        """Update enabled state of buttons based on selection."""
        has_pipeline = self._pipeline is not None
        row = self._pass_list.currentRow()
        has_selection = row >= 0

        self._add_btn.setEnabled(has_pipeline)
        self._remove_btn.setEnabled(has_pipeline and has_selection)

        if has_pipeline and has_selection:
            self._up_btn.setEnabled(row > 0)
            self._down_btn.setEnabled(row < len(self._pipeline.passes) - 1)
        else:
            self._up_btn.setEnabled(False)
            self._down_btn.setEnabled(False)

    @property
    def pipeline(self) -> Optional["RenderPipeline"]:
        """Current pipeline."""
        return self._pipeline

    # ---------- Resource Specs handling ----------

    def _rebuild_specs_list(self) -> None:
        """Rebuild the specs list from pipeline.pipeline_specs."""
        self._specs_list.clear()
        self._selected_spec_index = -1

        if self._pipeline is None:
            return

        for spec in self._pipeline.pipeline_specs:
            # Display: resource name + samples if MSAA enabled
            label = spec.resource
            if spec.samples > 1:
                label += f" ({spec.samples}x MSAA)"
            item = QListWidgetItem(label)
            self._specs_list.addItem(item)

    def _update_specs_buttons_state(self) -> None:
        """Update enabled state of spec buttons."""
        has_pipeline = self._pipeline is not None
        row = self._specs_list.currentRow()
        has_selection = row >= 0

        self._add_spec_btn.setEnabled(has_pipeline)
        self._remove_spec_btn.setEnabled(has_pipeline and has_selection)

    def _on_spec_selected(self, row: int) -> None:
        """Handle spec selection - show spec editor."""
        self._update_specs_buttons_state()
        self._selected_spec_index = row

        if self._pipeline is None or row < 0 or row >= len(self._pipeline.pipeline_specs):
            self._spec_editor_widget.setVisible(False)
            return

        spec = self._pipeline.pipeline_specs[row]
        self._spec_editor_widget.setVisible(True)

        # Block signals to prevent triggering _on_spec_field_changed
        self._updating_spec_ui = True

        # Resource name
        self._spec_resource_edit.setText(spec.resource)

        # Samples
        samples_map = {1: 0, 2: 1, 4: 2, 8: 3}
        samples_idx = samples_map.get(spec.samples, 0)
        self._spec_samples_combo.setCurrentIndex(samples_idx)

        # Format
        format_map = {"": 0, "rgba8": 0, "rgba16f": 1, "rgba32f": 2, "r8": 3, "r16f": 4, "r32f": 5}
        format_val = spec.format if spec.format else ""
        format_idx = format_map.get(format_val, 0)
        self._spec_format_combo.setCurrentIndex(format_idx)

        # Clear color
        if spec.clear_color is not None:
            self._spec_clear_color_check.setChecked(True)
            self._spec_clear_r.setText(str(spec.clear_color[0]))
            self._spec_clear_g.setText(str(spec.clear_color[1]))
            self._spec_clear_b.setText(str(spec.clear_color[2]))
            self._spec_clear_a.setText(str(spec.clear_color[3]))
        else:
            self._spec_clear_color_check.setChecked(False)
            self._spec_clear_r.setText("0.0")
            self._spec_clear_g.setText("0.0")
            self._spec_clear_b.setText("0.0")
            self._spec_clear_a.setText("1.0")

        # Clear depth
        if spec.clear_depth is not None:
            self._spec_clear_depth_check.setChecked(True)
            self._spec_clear_depth.setText(str(spec.clear_depth))
        else:
            self._spec_clear_depth_check.setChecked(False)
            self._spec_clear_depth.setText("1.0")

        self._updating_spec_ui = False

    def _on_add_spec(self) -> None:
        """Add a new ResourceSpec to the pipeline."""
        if self._pipeline is None:
            return

        from termin.visualization.render.framegraph.resource_spec import ResourceSpec

        # Ask for resource name
        resource_name, ok = QInputDialog.getText(
            self,
            "Add Resource Spec",
            "Enter resource name:",
            text="new_resource",
        )

        if not ok or not resource_name.strip():
            return

        resource_name = resource_name.strip()

        # Check for duplicates
        for spec in self._pipeline.pipeline_specs:
            if spec.resource == resource_name:
                QMessageBox.warning(
                    self,
                    "Duplicate Resource",
                    f"Resource '{resource_name}' already exists.",
                )
                return

        # Create new spec with defaults
        new_spec = ResourceSpec(resource=resource_name, resource_type="fbo")
        self._pipeline.pipeline_specs.append(new_spec)

        self._rebuild_specs_list()
        # Select the new spec
        self._specs_list.setCurrentRow(len(self._pipeline.pipeline_specs) - 1)
        self.pipeline_changed.emit(self._pipeline)

    def _on_remove_spec(self) -> None:
        """Remove the selected ResourceSpec from the pipeline."""
        if self._pipeline is None:
            return

        row = self._specs_list.currentRow()
        if row < 0 or row >= len(self._pipeline.pipeline_specs):
            return

        spec = self._pipeline.pipeline_specs[row]

        reply = QMessageBox.question(
            self,
            "Remove Resource Spec",
            f"Remove resource spec '{spec.resource}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        del self._pipeline.pipeline_specs[row]
        self._rebuild_specs_list()
        self._spec_editor_widget.setVisible(False)
        self._update_specs_buttons_state()
        self.pipeline_changed.emit(self._pipeline)

    def _on_spec_field_changed(self) -> None:
        """Update ResourceSpec from editor fields."""
        if self._updating_spec_ui:
            return

        if self._pipeline is None:
            return

        row = self._selected_spec_index
        if row < 0 or row >= len(self._pipeline.pipeline_specs):
            return

        spec = self._pipeline.pipeline_specs[row]

        # Update resource name
        new_resource = self._spec_resource_edit.text().strip()
        if new_resource and new_resource != spec.resource:
            # Check for duplicates
            for i, s in enumerate(self._pipeline.pipeline_specs):
                if i != row and s.resource == new_resource:
                    # Duplicate - don't update
                    self._spec_resource_edit.setText(spec.resource)
                    return
            spec.resource = new_resource
            # Update list item
            item = self._specs_list.item(row)
            if item:
                label = spec.resource
                if spec.samples > 1:
                    label += f" ({spec.samples}x MSAA)"
                item.setText(label)

        # Update samples
        samples_values = [1, 2, 4, 8]
        spec.samples = samples_values[self._spec_samples_combo.currentIndex()]

        # Update format
        format_values = ["", "rgba16f", "rgba32f", "r8", "r16f", "r32f"]
        format_idx = self._spec_format_combo.currentIndex()
        spec.format = format_values[format_idx]

        # Update list item text
        item = self._specs_list.item(row)
        if item:
            label = spec.resource
            parts = []
            if spec.samples > 1:
                parts.append(f"{spec.samples}x MSAA")
            if spec.format:
                parts.append(spec.format.upper())
            if parts:
                label += f" ({', '.join(parts)})"
            item.setText(label)

        # Update clear color
        if self._spec_clear_color_check.isChecked():
            try:
                r = float(self._spec_clear_r.text())
                g = float(self._spec_clear_g.text())
                b = float(self._spec_clear_b.text())
                a = float(self._spec_clear_a.text())
                spec.clear_color = (r, g, b, a)
            except ValueError:
                pass  # Invalid input, keep old value
        else:
            try:
                spec.clear_color = None
            except TypeError:
                # Workaround: C++ bindings may not accept None directly
                pass

        # Update clear depth
        if self._spec_clear_depth_check.isChecked():
            try:
                depth = float(self._spec_clear_depth.text())
                spec.clear_depth = depth
            except ValueError:
                pass  # Invalid input, keep old value
        else:
            try:
                spec.clear_depth = None
            except TypeError:
                # Workaround: C++ bindings may not accept None directly
                pass

        self.pipeline_changed.emit(self._pipeline)
