"""
Modules panel for project modules runtime.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6 import QtCore, QtGui, QtWidgets

from tcbase import log
from termin.modules import get_project_modules_runtime
from termin_modules import ModuleState

if TYPE_CHECKING:
    from termin_modules import ModuleEvent


class ModulesPanel(QtWidgets.QDockWidget):
    """Dock widget for managing project modules."""

    module_reloaded = QtCore.pyqtSignal(str, bool)

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__("Modules", parent)
        self.setObjectName("ModulesPanel")

        self._update_timer = QtCore.QTimer(self)
        self._update_timer.timeout.connect(self._update_display)
        self._update_timer.setInterval(1000)

        self._modules_runtime = get_project_modules_runtime()
        self._modules_runtime.add_listener(self._on_runtime_event)

        self._build_ui()

    def _build_ui(self) -> None:
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        toolbar = QtWidgets.QHBoxLayout()
        toolbar.setSpacing(8)

        self._auto_reload_check = QtWidgets.QCheckBox("Auto-reload")
        self._auto_reload_check.setToolTip("Not implemented for the new modules runtime yet")
        self._auto_reload_check.setChecked(False)
        self._auto_reload_check.setEnabled(False)
        self._auto_reload_check.toggled.connect(self._on_auto_reload_toggled)
        toolbar.addWidget(self._auto_reload_check)

        toolbar.addStretch()

        rescan_btn = QtWidgets.QPushButton("Rescan")
        rescan_btn.setToolTip("Rescan the current project and reload all modules")
        rescan_btn.clicked.connect(self._on_rescan_clicked)
        toolbar.addWidget(rescan_btn)

        self._reload_btn = QtWidgets.QPushButton("Reload")
        self._reload_btn.setToolTip("Reload selected module")
        self._reload_btn.setEnabled(False)
        self._reload_btn.clicked.connect(self._on_reload_clicked)
        toolbar.addWidget(self._reload_btn)

        self._unload_btn = QtWidgets.QPushButton("Unload")
        self._unload_btn.setToolTip("Unload selected module")
        self._unload_btn.setEnabled(False)
        self._unload_btn.clicked.connect(self._on_unload_clicked)
        toolbar.addWidget(self._unload_btn)

        layout.addLayout(toolbar)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)

        self._module_list = QtWidgets.QTreeWidget()
        self._module_list.setHeaderLabels(["Module", "Status", "Kind / Components"])
        self._module_list.setColumnWidth(0, 180)
        self._module_list.setColumnWidth(1, 90)
        self._module_list.setColumnWidth(2, 180)
        self._module_list.setAlternatingRowColors(True)
        self._module_list.setRootIsDecorated(False)
        self._module_list.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )
        self._module_list.itemSelectionChanged.connect(self._on_selection_changed)
        self._module_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        splitter.addWidget(self._module_list)

        output_group = QtWidgets.QGroupBox("Diagnostics")
        output_layout = QtWidgets.QVBoxLayout(output_group)
        output_layout.setContentsMargins(4, 4, 4, 4)

        self._output_text = QtWidgets.QPlainTextEdit()
        self._output_text.setReadOnly(True)
        self._output_text.setFont(QtGui.QFont("Consolas", 9))
        self._output_text.setMaximumBlockCount(1000)
        output_layout.addWidget(self._output_text)

        splitter.addWidget(output_group)
        splitter.setSizes([220, 120])

        layout.addWidget(splitter)

        self._status_label = QtWidgets.QLabel("No modules")
        self._status_label.setStyleSheet("color: gray;")
        layout.addWidget(self._status_label)

        self.setWidget(widget)

    def _on_runtime_event(self, event: "ModuleEvent") -> None:
        self._append_output(f"{event.kind.name.lower()}: {event.module_id}")
        if event.message:
            self._append_output(event.message)
        QtCore.QTimer.singleShot(100, self._update_display)

    def _update_display(self) -> None:
        selected_name = None
        selected_items = self._module_list.selectedItems()
        if selected_items:
            selected_name = selected_items[0].text(0)

        self._module_list.clear()

        records = sorted(self._modules_runtime.records(), key=lambda record: record.id)
        loaded_count = 0
        failed_count = 0

        for record in records:
            item = QtWidgets.QTreeWidgetItem()
            item.setText(0, record.id)

            state_name = record.state.name.lower()
            item.setText(1, state_name)
            if record.state == ModuleState.Loaded:
                loaded_count += 1
                item.setForeground(1, QtGui.QBrush(QtGui.QColor("green")))
            elif record.state == ModuleState.Failed:
                failed_count += 1
                item.setForeground(1, QtGui.QBrush(QtGui.QColor("red")))
            else:
                item.setForeground(1, QtGui.QBrush(QtGui.QColor("orange")))

            details = ", ".join(record.components)
            if not details:
                details = record.kind.name.lower()
            item.setText(2, details)
            item.setToolTip(0, str(record.descriptor_path))
            if record.error_message:
                item.setToolTip(1, record.error_message)
            elif record.diagnostics:
                item.setToolTip(1, record.diagnostics)

            self._module_list.addTopLevelItem(item)

            if record.id == selected_name:
                item.setSelected(True)

        if loaded_count == 0 and failed_count == 0:
            self._status_label.setText("No modules")
        else:
            parts = []
            if loaded_count > 0:
                parts.append(f"{loaded_count} loaded")
            if failed_count > 0:
                parts.append(f"{failed_count} failed")
            self._status_label.setText(", ".join(parts))

    def _on_auto_reload_toggled(self, checked: bool) -> None:
        if checked:
            self._append_output("Auto-reload is not implemented for the new modules runtime yet")

    def _on_rescan_clicked(self) -> None:
        project_root = self._modules_runtime.project_root
        if project_root is None:
            self._append_output("No project root is configured for modules runtime")
            return

        if not self._modules_runtime.load_project(project_root):
            self._append_output(f"Error: {self._modules_runtime.last_error}")
        self._update_display()

    def _on_reload_clicked(self) -> None:
        selected_items = self._module_list.selectedItems()
        if not selected_items:
            return

        module_name = selected_items[0].text(0)
        self._reload_module(module_name)

    def _on_unload_clicked(self) -> None:
        selected_items = self._module_list.selectedItems()
        if not selected_items:
            return

        module_name = selected_items[0].text(0)
        if not self._modules_runtime.unload_module(module_name):
            self._append_output(f"Error: {self._modules_runtime.last_error}")
        self._update_display()

    def _reload_module(self, module_name: str) -> None:
        try:
            success = self._modules_runtime.reload_module(module_name)
            if not success:
                self._append_output(f"Error: {self._modules_runtime.last_error}")
            self._update_display()
            self.module_reloaded.emit(module_name, success)
        except Exception as e:
            log.error(f"[ModulesPanel] Failed to reload module: {e}")
            self._append_output(f"Error: {e}")

    def _on_selection_changed(self) -> None:
        has_selection = len(self._module_list.selectedItems()) > 0
        self._reload_btn.setEnabled(has_selection)
        self._unload_btn.setEnabled(has_selection)

    def _on_item_double_clicked(
        self, item: QtWidgets.QTreeWidgetItem, column: int
    ) -> None:
        module_name = item.text(0)
        self._reload_module(module_name)

    def _append_output(self, text: str) -> None:
        if text:
            self._output_text.appendPlainText(text)

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        super().showEvent(event)
        self._update_timer.start()
        self._update_display()

    def hideEvent(self, event: QtGui.QHideEvent) -> None:
        super().hideEvent(event)
        self._update_timer.stop()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        super().closeEvent(event)
        self._update_timer.stop()
        self._modules_runtime.remove_listener(self._on_runtime_event)
