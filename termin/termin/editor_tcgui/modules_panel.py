"""Modules panel for tcgui editor — C++ hot-reload system.

Toggleable right-side panel showing loaded modules, their status,
and controls for reload/compilation.  Activated via Debug → Modules (F8).
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from tcbase import log
from tcgui.widgets.widget import Widget
from tcgui.widgets.basic import Label, Button, Checkbox
from tcgui.widgets.containers import VStack, HStack
from tcgui.widgets.scroll_area import ScrollArea
from tcgui.widgets.tree import TreeWidget, TreeNode
from tcgui.widgets.units import px

if TYPE_CHECKING:
    pass


# Colors
_GREEN = (0.31, 0.78, 0.31, 1.0)
_ORANGE = (0.85, 0.60, 0.20, 1.0)
_RED = (0.85, 0.31, 0.31, 1.0)
_TEXT = (0.75, 0.75, 0.75, 1.0)
_TEXT_DIM = (0.50, 0.50, 0.50, 1.0)


def _status_color(status: str) -> tuple:
    if status in ("loaded", "compiled", "reloaded"):
        return _GREEN
    if "failed" in status or status == "error":
        return _RED
    return _ORANGE


class ModulesPanel(VStack):
    """Modules debug panel (right-side, toggled by F8)."""

    def __init__(self):
        super().__init__()
        self.spacing = 4

        self._output_lines: list[str] = []
        self._max_output_lines: int = 200
        self._selected_module: str | None = None

        # Callback: (module_name, success) after reload
        self.on_module_reloaded = None

        self._build_ui()
        self._setup_loader_callback()

    def _build_ui(self) -> None:
        # Toolbar
        toolbar = HStack()
        toolbar.spacing = 8
        toolbar.preferred_height = px(28)

        self._auto_reload_check = Checkbox()
        self._auto_reload_check.text = "Auto-reload"
        self._auto_reload_check.font_size = 12
        self._auto_reload_check.on_changed = self._on_auto_reload_toggled
        toolbar.add_child(self._auto_reload_check)

        spacer = Label()
        spacer.stretch = True
        toolbar.add_child(spacer)

        load_btn = Button()
        load_btn.text = "Load..."
        load_btn.font_size = 11
        load_btn.padding = 4
        load_btn.on_click = self._on_load_clicked
        toolbar.add_child(load_btn)

        self._reload_btn = Button()
        self._reload_btn.text = "Reload"
        self._reload_btn.font_size = 11
        self._reload_btn.padding = 4
        self._reload_btn.on_click = self._on_reload_clicked
        toolbar.add_child(self._reload_btn)

        self._recompile_btn = Button()
        self._recompile_btn.text = "Force Recompile"
        self._recompile_btn.font_size = 11
        self._recompile_btn.padding = 4
        self._recompile_btn.on_click = self._on_force_recompile_clicked
        toolbar.add_child(self._recompile_btn)

        self.add_child(toolbar)

        # Header
        header = HStack()
        header.spacing = 4
        header.preferred_height = px(20)

        def _hdr(text, width=None, stretch=False):
            lbl = Label()
            lbl.text = text
            lbl.font_size = 11
            lbl.text_color = _TEXT_DIM
            if width:
                lbl.preferred_width = px(width)
            if stretch:
                lbl.stretch = True
            return lbl

        header.add_child(_hdr("Module", stretch=True))
        header.add_child(_hdr("Status", 70))
        header.add_child(_hdr("Components", 120))
        self.add_child(header)

        # Module list
        list_scroll = ScrollArea()
        list_scroll.stretch = True
        self._tree = TreeWidget()
        self._tree.row_height = 22
        self._tree.font_size = 12
        self._tree.on_select = self._on_selection_changed
        list_scroll.add_child(self._tree)
        self.add_child(list_scroll)

        # Compiler output label
        out_header = Label()
        out_header.text = "Compiler Output"
        out_header.font_size = 11
        out_header.text_color = _TEXT_DIM
        self.add_child(out_header)

        # Output area
        out_scroll = ScrollArea()
        out_scroll.preferred_height = px(120)
        self._output_label = Label()
        self._output_label.text = ""
        self._output_label.font_size = 10
        self._output_label.text_color = _TEXT
        out_scroll.add_child(self._output_label)
        self.add_child(out_scroll)

        # Status bar
        self._status_label = Label()
        self._status_label.text = "No modules"
        self._status_label.font_size = 11
        self._status_label.text_color = _TEXT_DIM
        self.add_child(self._status_label)

    # ------------------------------------------------------------------
    # Loader integration
    # ------------------------------------------------------------------

    def _setup_loader_callback(self) -> None:
        try:
            from termin.entity._entity_native import ModuleLoader
            loader = ModuleLoader.instance()
            loader.set_event_callback(self._on_loader_event)
        except Exception as e:
            log.warning(f"[ModulesPanel] Failed to set up loader callback: {e}")

    def _on_loader_event(self, module_name: str, event: str) -> None:
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

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _on_auto_reload_toggled(self, checked: bool) -> None:
        try:
            from termin.editor.module_watcher import get_module_watcher
            get_module_watcher().auto_reload = checked
        except Exception as e:
            log.error(f"[ModulesPanel] Auto-reload toggle failed: {e}")

    def _on_load_clicked(self) -> None:
        ui = self._ui
        if ui is None:
            return
        from tcgui.widgets.file_dialog_overlay import show_open_file_dialog
        show_open_file_dialog(
            ui,
            on_result=lambda path: self._load_module_file(path) if path else None,
            title="Select Module File",
            windowed=True,
        )

    def _on_reload_clicked(self) -> None:
        if self._selected_module:
            self._reload_module(self._selected_module)

    def _on_force_recompile_clicked(self) -> None:
        if self._selected_module:
            self._force_recompile_module(self._selected_module)

    def _on_selection_changed(self, node) -> None:
        if node and node.data:
            self._selected_module = node.data
        else:
            self._selected_module = None

    # ------------------------------------------------------------------
    # Module operations
    # ------------------------------------------------------------------

    def _load_module_file(self, file_path: str) -> None:
        try:
            from termin.entity._entity_native import ModuleLoader
            loader = ModuleLoader.instance()

            if not loader.core_c:
                self._set_engine_paths(loader)

            success = loader.load_module(file_path)
            if success:
                try:
                    from termin.editor.module_watcher import get_module_watcher
                    get_module_watcher().watch_module(file_path)
                except Exception:
                    pass
                self.update_display()
            else:
                self._append_output(f"Error: {loader.last_error}")
        except Exception as e:
            log.error(f"[ModulesPanel] Failed to load module: {e}")
            self._append_output(f"Error: {e}")

    def _reload_module(self, module_name: str) -> None:
        try:
            from termin.entity._entity_native import ModuleLoader
            loader = ModuleLoader.instance()
            success = loader.reload_module(module_name)
            if success:
                self._append_output(loader.compiler_output)
            else:
                self._append_output(f"Error: {loader.last_error}")
                self._append_output(loader.compiler_output)
            self.update_display()
            if self.on_module_reloaded:
                self.on_module_reloaded(module_name, success)
        except Exception as e:
            log.error(f"[ModulesPanel] Failed to reload module: {e}")
            self._append_output(f"Error: {e}")

    def _force_recompile_module(self, module_name: str) -> None:
        import shutil
        try:
            from termin.entity._entity_native import ModuleLoader
            loader = ModuleLoader.instance()

            module = loader.get_module(module_name)
            module_file_path = None
            if module and module.descriptor:
                module_file_path = module.descriptor.path

            if not module_file_path:
                self._append_output(f"Error: Cannot find module file for '{module_name}'")
                return

            module_dir = os.path.dirname(module_file_path)
            build_dir = os.path.join(module_dir, "build")

            if loader.is_loaded(module_name):
                self._append_output(f"Unloading module '{module_name}'...")
                loader.unload_module(module_name)

            if os.path.exists(build_dir):
                self._append_output(f"Deleting build cache: {build_dir}")
                shutil.rmtree(build_dir, ignore_errors=True)

            self._append_output(f"Recompiling module '{module_name}' from scratch...")
            success = loader.load_module(module_file_path)
            if success:
                self._append_output(f"Module '{module_name}' recompiled successfully")
            self._append_output(loader.compiler_output)
            self.update_display()
            if self.on_module_reloaded:
                self.on_module_reloaded(module_name, success)
        except Exception as e:
            log.error(f"[ModulesPanel] Failed to force recompile: {e}")
            self._append_output(f"Error: {e}")

    def _set_engine_paths(self, loader) -> None:
        import termin
        termin_path = os.path.dirname(termin.__file__)
        project_root = os.path.normpath(os.path.join(termin_path, ".."))

        core_c_dev = os.path.join(project_root, "core_c", "include")
        core_cpp_dev = os.path.join(project_root, "cpp")
        lib_dir_build = os.path.join(project_root, "cpp", "build", "bin")

        core_c_pkg = os.path.join(termin_path, "include", "core_c")
        core_cpp_pkg = os.path.join(termin_path, "include", "cpp")
        lib_dir_pkg = os.path.join(termin_path, "lib")

        if os.path.exists(core_c_dev) and os.path.exists(core_cpp_dev):
            loader.set_engine_paths(core_c_dev, core_cpp_dev, lib_dir_build)
        elif os.path.exists(core_c_pkg) and os.path.exists(core_cpp_pkg):
            loader.set_engine_paths(core_c_pkg, core_cpp_pkg, lib_dir_pkg)
        else:
            self._append_output("Warning: Could not find engine include paths")
            loader.set_engine_paths(core_c_dev, core_cpp_dev, lib_dir_build)

    # ------------------------------------------------------------------
    # Display update (called from editor_window.poll at ~1 Hz)
    # ------------------------------------------------------------------

    def update_display(self) -> None:
        try:
            from termin.entity._entity_native import ModuleLoader
            loader = ModuleLoader.instance()
        except Exception:
            return

        self._tree.clear()
        loaded_modules = set(loader.list_modules())
        loaded_count = 0
        failed_count = 0

        for name in sorted(loaded_modules):
            module = loader.get_module(name)
            if module is None:
                continue
            loaded_count += 1

            row = self._make_module_row(
                module.name, "loaded",
                ", ".join(module.registered_components),
            )
            node = TreeNode(content=row)
            node.data = module.name
            self._tree.add_root(node)

        # Watched but not loaded
        try:
            from termin.editor.module_watcher import get_module_watcher
            watched = set(get_module_watcher().get_watched_modules())
            failed_modules = watched - loaded_modules
            for name in sorted(failed_modules):
                failed_count += 1
                row = self._make_module_row(name, "error", "")
                node = TreeNode(content=row)
                node.data = name
                self._tree.add_root(node)
        except Exception:
            pass

        if loaded_count == 0 and failed_count == 0:
            self._status_label.text = "No modules"
        else:
            parts = []
            if loaded_count > 0:
                parts.append(f"{loaded_count} loaded")
            if failed_count > 0:
                parts.append(f"{failed_count} failed")
            self._status_label.text = ", ".join(parts)

    def _make_module_row(self, name: str, status: str,
                         components: str) -> Widget:
        row = HStack()
        row.spacing = 4

        name_lbl = Label()
        name_lbl.text = name
        name_lbl.font_size = 12
        name_lbl.text_color = _TEXT
        name_lbl.stretch = True
        row.add_child(name_lbl)

        status_lbl = Label()
        status_lbl.text = status
        status_lbl.font_size = 12
        status_lbl.text_color = _status_color(status)
        status_lbl.preferred_width = px(70)
        row.add_child(status_lbl)

        comp_lbl = Label()
        comp_lbl.text = components
        comp_lbl.font_size = 12
        comp_lbl.text_color = _TEXT_DIM
        comp_lbl.preferred_width = px(120)
        row.add_child(comp_lbl)

        return row

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def _append_output(self, text: str) -> None:
        if not text:
            return
        for line in text.split("\n"):
            self._output_lines.append(line)
        while len(self._output_lines) > self._max_output_lines:
            self._output_lines.pop(0)
        self._output_label.text = "\n".join(self._output_lines)
