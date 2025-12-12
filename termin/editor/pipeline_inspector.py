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
)
from PyQt6.QtCore import Qt, pyqtSignal

if TYPE_CHECKING:
    from termin.visualization.render.framegraph.pipeline import RenderPipeline


class PipelineInspector(QWidget):
    """
    Inspector for RenderPipeline.

    Displays:
    - Pipeline name
    - List of passes with enable/disable
    - Selected pass parameters
    """

    pipeline_changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._pipeline: Optional["RenderPipeline"] = None
        self._pipeline_name: str = ""
        self._source_path: Optional[str] = None

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

        # Pass list
        self._pass_list = QListWidget()
        self._pass_list.setMaximumHeight(200)
        self._pass_list.itemChanged.connect(self._on_pass_toggled)
        self._pass_list.currentRowChanged.connect(self._on_pass_selected)
        main_layout.addWidget(self._pass_list)

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

        self._details_info = QLabel("Select a pass to view details")
        self._details_info.setStyleSheet("color: #888;")
        self._details_layout.addWidget(self._details_info)
        self._details_layout.addStretch()

        scroll.setWidget(self._details_widget)
        main_layout.addWidget(scroll, 1)

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
        self.pipeline_changed.emit()

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
            QMessageBox.critical(
                self,
                "Error Saving Pipeline",
                f"Failed to save pipeline:\n{path}\n\nError: {e}",
            )
            return False

    def _rebuild_ui(self) -> None:
        """Rebuild UI for current pipeline."""
        self._pass_list.clear()

        if self._pipeline is None:
            self._name_label.setText("")
            self._details_info.setText("No pipeline loaded")
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

        self._details_info.setText("Select a pass to view details")

    def _on_pass_toggled(self, item: QListWidgetItem) -> None:
        """Handle pass enable/disable toggle."""
        if self._pipeline is None:
            return

        row = self._pass_list.row(item)
        if 0 <= row < len(self._pipeline.passes):
            enabled = item.checkState() == Qt.CheckState.Checked
            self._pipeline.passes[row].enabled = enabled
            self.pipeline_changed.emit()

    def _on_pass_selected(self, row: int) -> None:
        """Handle pass selection - show details."""
        if self._pipeline is None or row < 0 or row >= len(self._pipeline.passes):
            self._details_info.setText("Select a pass to view details")
            return

        p = self._pipeline.passes[row]

        # Show pass info
        info_lines = [
            f"Type: {p.__class__.__name__}",
            f"Name: {p.pass_name}",
            f"Enabled: {p.enabled}",
            f"Reads: {', '.join(p.reads) or 'none'}",
            f"Writes: {', '.join(p.writes) or 'none'}",
        ]

        # Add pass-specific params
        params = p._serialize_params()
        if params:
            info_lines.append("")
            info_lines.append("Parameters:")
            for k, v in params.items():
                info_lines.append(f"  {k}: {v}")

        self._details_info.setText("\n".join(info_lines))

    def _on_save_clicked(self) -> None:
        """Handle save button click."""
        if self.save_pipeline_file():
            pass  # Could show success notification

    @property
    def pipeline(self) -> Optional["RenderPipeline"]:
        """Current pipeline."""
        return self._pipeline
