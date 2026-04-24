"""
Dialog for editing project settings.
"""

from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QGroupBox,
    QFormLayout,
    QComboBox,
    QDialogButtonBox,
    QLabel,
)

from termin.project.settings import ProjectSettingsManager, RenderSyncMode


class ProjectSettingsDialog(QDialog):
    """
    Dialog for editing project-level settings.

    Non-modal dialog with immediate apply (no OK/Cancel).
    """

    def __init__(
        self,
        parent=None,
        on_changed: Optional[Callable[[], None]] = None,
    ):
        super().__init__(parent)
        self._manager = ProjectSettingsManager.instance()
        self._on_changed = on_changed

        self.setWindowTitle("Project Settings")
        self.setMinimumWidth(350)

        self._init_ui()
        self._load_from_settings()
        self._connect_signals()

    def _init_ui(self) -> None:
        """Initialize UI components."""
        layout = QVBoxLayout(self)

        # Check if project is open
        if self._manager.project_path is None:
            no_project_label = QLabel("No project is currently open.\n\nOpen a project to configure settings.")
            no_project_label.setWordWrap(True)
            layout.addWidget(no_project_label)
            layout.addStretch()

            button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            button_box.rejected.connect(self.close)
            layout.addWidget(button_box)
            return

        # Render settings group
        render_group = QGroupBox("Render")
        render_layout = QFormLayout(render_group)

        # Render sync mode
        self._sync_mode_combo = QComboBox()
        self._sync_mode_combo.addItem("None (fastest)", RenderSyncMode.NONE.value)
        self._sync_mode_combo.addItem("glFlush (force submit)", RenderSyncMode.FLUSH.value)
        self._sync_mode_combo.addItem("glFinish (wait GPU)", RenderSyncMode.FINISH.value)

        sync_mode_label = QLabel("Sync between passes:")
        sync_mode_label.setToolTip(
            "Controls GPU synchronization between render passes.\n\n"
            "None: No synchronization (fastest, default)\n"
            "glFlush: Forces command submission to GPU\n"
            "glFinish: Waits for GPU to complete all commands\n\n"
            "Use glFlush/glFinish for debugging render issues."
        )
        render_layout.addRow(sync_mode_label, self._sync_mode_combo)

        layout.addWidget(render_group)
        layout.addStretch()

        # Close button
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.close)
        layout.addWidget(button_box)

    def _load_from_settings(self) -> None:
        """Load current values from settings."""
        if self._manager.project_path is None:
            return

        settings = self._manager.settings

        # Find index for current sync mode
        sync_mode_value = settings.render_sync_mode.value
        for i in range(self._sync_mode_combo.count()):
            if self._sync_mode_combo.itemData(i) == sync_mode_value:
                self._sync_mode_combo.setCurrentIndex(i)
                break

    def _connect_signals(self) -> None:
        """Connect UI signals."""
        if self._manager.project_path is None:
            return

        self._sync_mode_combo.currentIndexChanged.connect(self._on_sync_mode_changed)

    def _on_sync_mode_changed(self, index: int) -> None:
        """Handle sync mode combo change."""
        sync_mode_value = self._sync_mode_combo.itemData(index)
        try:
            sync_mode = RenderSyncMode(sync_mode_value)
        except ValueError:
            sync_mode = RenderSyncMode.NONE

        self._manager.set_render_sync_mode(sync_mode)

        if self._on_changed is not None:
            self._on_changed()
