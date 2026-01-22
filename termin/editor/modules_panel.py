"""
Modules panel for C++ hot-reload system.

Dock widget that displays loaded modules, their status, and allows
manual reload/compilation.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from PyQt6 import QtWidgets, QtCore, QtGui

from termin._native import log
from termin.editor.module_watcher import get_module_watcher

if TYPE_CHECKING:
    from termin.entity._entity_native import ModuleLoader, LoadedModule


class ModulesPanel(QtWidgets.QDockWidget):
    """
    Dock widget for managing C++ modules.

    Shows:
    - List of loaded modules with status
    - Reload/compile buttons
    - Compiler output log
    - Auto-reload toggle
    """

    # Signals
    module_reloaded = QtCore.pyqtSignal(str, bool)  # module_name, success

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__("Modules", parent)
        self.setObjectName("ModulesPanel")

        self._update_timer = QtCore.QTimer(self)
        self._update_timer.timeout.connect(self._update_display)
        self._update_timer.setInterval(1000)  # Update every second

        self._module_watcher = get_module_watcher()
        self._module_watcher._on_module_changed = self._on_module_changed
        self._module_watcher._on_reload_complete = self._on_reload_complete

        self._build_ui()
        self._setup_loader_callback()

    def _build_ui(self) -> None:
        """Build the panel UI."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Toolbar
        toolbar = QtWidgets.QHBoxLayout()
        toolbar.setSpacing(8)

        # Auto-reload checkbox
        self._auto_reload_check = QtWidgets.QCheckBox("Auto-reload")
        self._auto_reload_check.setToolTip(
            "Automatically reload modules when source files change"
        )
        self._auto_reload_check.setChecked(self._module_watcher.auto_reload)
        self._auto_reload_check.toggled.connect(self._on_auto_reload_toggled)
        toolbar.addWidget(self._auto_reload_check)

        toolbar.addStretch()

        # Load module button
        load_btn = QtWidgets.QPushButton("Load Module...")
        load_btn.setToolTip("Load a module from .module file")
        load_btn.clicked.connect(self._on_load_module_clicked)
        toolbar.addWidget(load_btn)

        # Reload button
        self._reload_btn = QtWidgets.QPushButton("Reload")
        self._reload_btn.setToolTip("Reload selected module")
        self._reload_btn.setEnabled(False)
        self._reload_btn.clicked.connect(self._on_reload_clicked)
        toolbar.addWidget(self._reload_btn)

        layout.addLayout(toolbar)

        # Splitter for list and output
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)

        # Module list
        self._module_list = QtWidgets.QTreeWidget()
        self._module_list.setHeaderLabels(["Module", "Status", "Components"])
        self._module_list.setColumnWidth(0, 150)
        self._module_list.setColumnWidth(1, 80)
        self._module_list.setColumnWidth(2, 100)
        self._module_list.setAlternatingRowColors(True)
        self._module_list.setRootIsDecorated(False)
        self._module_list.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )
        self._module_list.itemSelectionChanged.connect(self._on_selection_changed)
        self._module_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        splitter.addWidget(self._module_list)

        # Compiler output
        output_group = QtWidgets.QGroupBox("Compiler Output")
        output_layout = QtWidgets.QVBoxLayout(output_group)
        output_layout.setContentsMargins(4, 4, 4, 4)

        self._output_text = QtWidgets.QPlainTextEdit()
        self._output_text.setReadOnly(True)
        self._output_text.setFont(QtGui.QFont("Consolas", 9))
        self._output_text.setMaximumBlockCount(1000)
        output_layout.addWidget(self._output_text)

        splitter.addWidget(output_group)
        splitter.setSizes([200, 100])

        layout.addWidget(splitter)

        # Status bar
        self._status_label = QtWidgets.QLabel("No modules loaded")
        self._status_label.setStyleSheet("color: gray;")
        layout.addWidget(self._status_label)

        self.setWidget(widget)

    def _setup_loader_callback(self) -> None:
        """Set up event callback on ModuleLoader."""
        try:
            from termin.entity._entity_native import ModuleLoader

            loader = ModuleLoader.instance()
            loader.set_event_callback(self._on_loader_event)
        except Exception as e:
            log.warning(f"[ModulesPanel] Failed to set up loader callback: {e}")

    def _on_loader_event(self, module_name: str, event: str) -> None:
        """Handle events from ModuleLoader."""
        # Update status in list
        self._update_module_status(module_name, event)

        # Log event
        event_messages = {
            "loading": f"Loading module '{module_name}'...",
            "loaded": f"Module '{module_name}' loaded successfully",
            "unloading": f"Unloading module '{module_name}'...",
            "unloaded": f"Module '{module_name}' unloaded",
            "compiling": f"Compiling module '{module_name}'...",
            "compiled": f"Module '{module_name}' compiled successfully",
            "compile_failed": f"Failed to compile module '{module_name}'",
            "load_failed": f"Failed to load module '{module_name}'",
            "reloading": f"Reloading module '{module_name}'...",
            "reloaded": f"Module '{module_name}' reloaded successfully",
        }

        message = event_messages.get(event, f"Module '{module_name}': {event}")
        self._append_output(message)

        # Update display
        QtCore.QTimer.singleShot(100, self._update_display)

    def _update_module_status(self, module_name: str, status: str) -> None:
        """Update the status column for a module."""
        for i in range(self._module_list.topLevelItemCount()):
            item = self._module_list.topLevelItem(i)
            if item and item.text(0) == module_name:
                item.setText(1, status)
                # Color based on status
                if status in ("loaded", "compiled", "reloaded"):
                    item.setForeground(1, QtGui.QBrush(QtGui.QColor("green")))
                elif "failed" in status:
                    item.setForeground(1, QtGui.QBrush(QtGui.QColor("red")))
                else:
                    item.setForeground(1, QtGui.QBrush(QtGui.QColor("orange")))
                break

    def _update_display(self) -> None:
        """Update the module list display."""
        try:
            from termin.entity._entity_native import ModuleLoader

            loader = ModuleLoader.instance()
        except Exception:
            return

        # Remember selection
        selected_name = None
        selected_items = self._module_list.selectedItems()
        if selected_items:
            selected_name = selected_items[0].text(0)

        self._module_list.clear()

        loaded_modules = set(loader.list_modules())
        watched_modules = set(self._module_watcher.get_watched_modules())

        # Show loaded modules
        for name in loaded_modules:
            module = loader.get_module(name)
            if module is None:
                continue

            item = QtWidgets.QTreeWidgetItem()
            item.setText(0, module.name)
            item.setText(1, "loaded")
            item.setForeground(1, QtGui.QBrush(QtGui.QColor("green")))
            item.setText(2, ", ".join(module.registered_components))
            item.setToolTip(0, module.dll_path)

            self._module_list.addTopLevelItem(item)

            if name == selected_name:
                item.setSelected(True)

        # Show watched but not loaded modules (failed to compile)
        failed_modules = watched_modules - loaded_modules
        for name in sorted(failed_modules):
            item = QtWidgets.QTreeWidgetItem()
            item.setText(0, name)
            item.setText(1, "error")
            item.setForeground(1, QtGui.QBrush(QtGui.QColor("red")))
            item.setText(2, "")
            item.setToolTip(0, "Module failed to load - check compiler output")

            self._module_list.addTopLevelItem(item)

            if name == selected_name:
                item.setSelected(True)

        # Update status
        loaded_count = len(loaded_modules)
        failed_count = len(failed_modules)
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
        """Handle auto-reload checkbox toggle."""
        self._module_watcher.auto_reload = checked

    def _on_load_module_clicked(self) -> None:
        """Handle Load Module button click."""
        # Defer dialog to next event loop iteration to avoid COM threading issues on Windows
        QtCore.QTimer.singleShot(0, self._show_load_dialog)

    def _show_load_dialog(self) -> None:
        """Show file dialog and load module."""
        try:
            file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self,
                "Select Module File",
                "",
                "Module Files (*.module);;All Files (*)",
                options=QtWidgets.QFileDialog.Option.DontUseNativeDialog,
            )
        except Exception as e:
            log.error(f"[ModulesPanel] Failed to open file dialog: {e}")
            return

        if not file_path:
            return

        self._load_module_file(file_path)

    def _load_module_file(self, file_path: str) -> None:
        """Load module from file path."""
        try:
            from termin.entity._entity_native import ModuleLoader

            loader = ModuleLoader.instance()

            # Set engine paths if not set
            if not loader.core_c:
                import termin

                termin_path = os.path.dirname(termin.__file__)
                project_root = os.path.normpath(os.path.join(termin_path, ".."))

                # Try development paths first (source checkout)
                core_c_dev = os.path.join(project_root, "core_c", "include")
                core_cpp_dev = os.path.join(project_root, "cpp")

                # Check for pip install -e . (editable install) with build dir
                lib_dir_build = os.path.join(
                    project_root, "build", "temp.win-amd64-cpython-312", "Release", "bin"
                )
                if not os.path.exists(lib_dir_build):
                    lib_dir_build = os.path.join(project_root, "cpp", "build", "bin")

                # Installed package paths
                core_c_pkg = os.path.join(termin_path, "include", "core_c")
                core_cpp_pkg = os.path.join(termin_path, "include", "cpp")
                lib_dir_pkg = os.path.join(termin_path, "lib")

                # Use development paths if available, otherwise installed package
                if os.path.exists(core_c_dev) and os.path.exists(core_cpp_dev):
                    core_c = core_c_dev
                    core_cpp = core_cpp_dev
                    lib_dir = lib_dir_build
                elif os.path.exists(core_c_pkg) and os.path.exists(core_cpp_pkg):
                    core_c = core_c_pkg
                    core_cpp = core_cpp_pkg
                    lib_dir = lib_dir_pkg
                else:
                    self._append_output("Warning: Could not find engine include paths")
                    core_c = core_c_dev
                    core_cpp = core_cpp_dev
                    lib_dir = lib_dir_build

                loader.set_engine_paths(core_c, core_cpp, lib_dir)

            success = loader.load_module(file_path)

            if success:
                # Also start watching the module
                self._module_watcher.watch_module(file_path)
                self._update_display()
            else:
                self._append_output(f"Error: {loader.last_error}")
                QtWidgets.QMessageBox.warning(
                    self,
                    "Load Failed",
                    f"Failed to load module:\n{loader.last_error}",
                )

        except Exception as e:
            log.error(f"[ModulesPanel] Failed to load module: {e}")
            QtWidgets.QMessageBox.critical(
                self,
                "Load Error",
                f"Error loading module:\n{e}",
            )

    def _on_reload_clicked(self) -> None:
        """Handle Reload button click."""
        selected_items = self._module_list.selectedItems()
        if not selected_items:
            return

        module_name = selected_items[0].text(0)
        self._reload_module(module_name)

    def _reload_module(self, module_name: str) -> None:
        """Reload a module."""
        try:
            from termin.entity._entity_native import ModuleLoader

            loader = ModuleLoader.instance()
            success = loader.reload_module(module_name)

            if success:
                self._update_display()
                self._append_output(loader.compiler_output)
            else:
                self._append_output(f"Error: {loader.last_error}")
                self._append_output(loader.compiler_output)

            self.module_reloaded.emit(module_name, success)

        except Exception as e:
            log.error(f"[ModulesPanel] Failed to reload module: {e}")
            self._append_output(f"Error: {e}")

    def _on_selection_changed(self) -> None:
        """Handle selection change in module list."""
        has_selection = len(self._module_list.selectedItems()) > 0
        self._reload_btn.setEnabled(has_selection)

    def _on_item_double_clicked(
        self, item: QtWidgets.QTreeWidgetItem, column: int
    ) -> None:
        """Handle double-click on module item."""
        module_name = item.text(0)
        self._reload_module(module_name)

    def _on_module_changed(self, module_name: str) -> None:
        """Handle module file change from watcher."""
        self._update_module_status(module_name, "modified")
        self._append_output(f"Source files changed for module '{module_name}'")

    def _on_reload_complete(
        self, module_name: str, success: bool, message: str
    ) -> None:
        """Handle reload completion from watcher."""
        if success:
            self._update_module_status(module_name, "reloaded")
        else:
            self._update_module_status(module_name, "failed")
            self._append_output(f"Reload failed: {message}")

        self.module_reloaded.emit(module_name, success)
        self._update_display()

    def _append_output(self, text: str) -> None:
        """Append text to compiler output."""
        if text:
            self._output_text.appendPlainText(text)

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        """Handle show event."""
        super().showEvent(event)
        self._update_timer.start()
        self._module_watcher.enable()
        self._register_loaded_modules()
        self._update_display()

    def _register_loaded_modules(self) -> None:
        """Register all loaded modules with the watcher for hot-reload."""
        try:
            from termin.entity._entity_native import ModuleLoader

            loader = ModuleLoader.instance()
            for name in loader.list_modules():
                module = loader.get_module(name)
                if module and module.descriptor:
                    self._module_watcher.watch_module(module.descriptor.path)
        except Exception as e:
            log.error(f"[ModulesPanel] Failed to register modules: {e}")

    def hideEvent(self, event: QtGui.QHideEvent) -> None:
        """Handle hide event."""
        super().hideEvent(event)
        self._update_timer.stop()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Handle close event."""
        super().closeEvent(event)
        self._update_timer.stop()
        self._module_watcher.disable()
