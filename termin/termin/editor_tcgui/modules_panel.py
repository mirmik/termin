"""Modules panel for tcgui editor — project modules runtime."""

from __future__ import annotations

from tcbase import log
from tcgui.widgets.widget import Widget
from tcgui.widgets.basic import Label, Button, Checkbox
from tcgui.widgets.containers import VStack, HStack
from tcgui.widgets.scroll_area import ScrollArea
from tcgui.widgets.tree import TreeWidget, TreeNode
from tcgui.widgets.units import px

from termin.modules import get_project_modules_runtime
from termin_modules import ModuleEvent, ModuleState


_GREEN = (0.31, 0.78, 0.31, 1.0)
_ORANGE = (0.85, 0.60, 0.20, 1.0)
_RED = (0.85, 0.31, 0.31, 1.0)
_GRAY = (0.45, 0.45, 0.45, 1.0)
_TEXT = (0.75, 0.75, 0.75, 1.0)
_TEXT_DIM = (0.50, 0.50, 0.50, 1.0)

_TAG = "[ModulesPanel]"


def _status_color(status: str) -> tuple:
    if status == "loaded":
        return _GREEN
    if status == "failed":
        return _RED
    if status == "ignored":
        return _GRAY
    return _ORANGE


class ModulesPanel(VStack):
    """Modules debug panel."""

    def __init__(self):
        super().__init__()
        self.spacing = 4

        self._selected_module: str | None = None
        self._modules_runtime = get_project_modules_runtime()
        self._modules_runtime.add_listener(self._on_runtime_event)

        self.on_module_reloaded = None

        self._build_ui()

    def _build_ui(self) -> None:
        toolbar = HStack()
        toolbar.spacing = 8
        toolbar.preferred_height = px(28)

        self._auto_reload_check = Checkbox()
        self._auto_reload_check.text = "Auto-reload"
        self._auto_reload_check.font_size = 12
        self._auto_reload_check.enabled = False
        self._auto_reload_check.on_changed = self._on_auto_reload_toggled
        toolbar.add_child(self._auto_reload_check)

        spacer = Label()
        spacer.stretch = True
        toolbar.add_child(spacer)

        rescan_btn = Button()
        rescan_btn.text = "Rescan"
        rescan_btn.font_size = 11
        rescan_btn.padding = 4
        rescan_btn.on_click = self._on_rescan_clicked
        toolbar.add_child(rescan_btn)

        self._reload_btn = Button()
        self._reload_btn.text = "Reload"
        self._reload_btn.font_size = 11
        self._reload_btn.padding = 4
        self._reload_btn.on_click = self._on_reload_clicked
        toolbar.add_child(self._reload_btn)

        self._build_btn = Button()
        self._build_btn.text = "Build"
        self._build_btn.font_size = 11
        self._build_btn.padding = 4
        self._build_btn.on_click = self._on_build_clicked
        toolbar.add_child(self._build_btn)

        self._clean_btn = Button()
        self._clean_btn.text = "Clean"
        self._clean_btn.font_size = 11
        self._clean_btn.padding = 4
        self._clean_btn.on_click = self._on_clean_clicked
        toolbar.add_child(self._clean_btn)

        self._rebuild_btn = Button()
        self._rebuild_btn.text = "Rebuild"
        self._rebuild_btn.font_size = 11
        self._rebuild_btn.padding = 4
        self._rebuild_btn.on_click = self._on_rebuild_clicked
        toolbar.add_child(self._rebuild_btn)

        self._unload_btn = Button()
        self._unload_btn.text = "Unload"
        self._unload_btn.font_size = 11
        self._unload_btn.padding = 4
        self._unload_btn.on_click = self._on_unload_clicked
        toolbar.add_child(self._unload_btn)

        self.add_child(toolbar)

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
        header.add_child(_hdr("Kind / Components", 160))
        self.add_child(header)

        list_scroll = ScrollArea()
        list_scroll.stretch = True
        self._tree = TreeWidget()
        self._tree.row_height = 22
        self._tree.font_size = 12
        self._tree.on_select = self._on_selection_changed
        list_scroll.add_child(self._tree)
        self.add_child(list_scroll)

        self._status_label = Label()
        self._status_label.text = "No modules"
        self._status_label.font_size = 11
        self._status_label.text_color = _TEXT_DIM
        self.add_child(self._status_label)

    def _on_runtime_event(self, event: ModuleEvent) -> None:
        log.info(f"{_TAG} {event.kind.name.lower()}: {event.module_id}")
        if event.message:
            log.info(f"{_TAG} {event.message}")

    def _on_auto_reload_toggled(self, checked: bool) -> None:
        if checked:
            log.warn(f"{_TAG} Auto-reload is not implemented yet")

    def _on_rescan_clicked(self) -> None:
        project_root = self._modules_runtime.project_root
        if project_root is None:
            log.error(f"{_TAG} No project root is configured for modules runtime")
            return
        log.info(f"{_TAG} Rescanning project: {project_root}")
        if not self._modules_runtime.load_project(project_root):
            log.error(f"{_TAG} Rescan failed: {self._modules_runtime.last_error}")
        else:
            log.info(f"{_TAG} Rescan complete")
        self.update_display()

    def _on_reload_clicked(self) -> None:
        if self._selected_module:
            self._reload_module(self._selected_module)

    def _on_build_clicked(self) -> None:
        if not self._selected_module:
            return
        log.info(f"{_TAG} Building module '{self._selected_module}'...")
        if not self._modules_runtime.build_module(self._selected_module):
            log.error(f"{_TAG} Build failed: {self._modules_runtime.last_error}")
        else:
            log.info(f"{_TAG} Build complete: '{self._selected_module}'")
        self.update_display()

    def _on_clean_clicked(self) -> None:
        if not self._selected_module:
            return
        log.info(f"{_TAG} Cleaning module '{self._selected_module}'...")
        if not self._modules_runtime.clean_module(self._selected_module):
            log.error(f"{_TAG} Clean failed: {self._modules_runtime.last_error}")
        else:
            log.info(f"{_TAG} Clean complete: '{self._selected_module}'")
        self.update_display()

    def _on_rebuild_clicked(self) -> None:
        if not self._selected_module:
            return
        module_name = self._selected_module
        log.info(f"{_TAG} Rebuilding module '{module_name}'...")
        try:
            success = self._modules_runtime.rebuild_module(module_name)
            if not success:
                log.error(f"{_TAG} Rebuild failed: {self._modules_runtime.last_error}")
            else:
                log.info(f"{_TAG} Rebuild complete: '{module_name}'")
            self.update_display()
        except Exception as e:
            log.error(f"{_TAG} Rebuild exception for '{module_name}': {e}")

    def _on_unload_clicked(self) -> None:
        if not self._selected_module:
            return
        log.info(f"{_TAG} Unloading module '{self._selected_module}'...")
        if not self._modules_runtime.unload_module(self._selected_module):
            log.error(f"{_TAG} Unload failed: {self._modules_runtime.last_error}")
        else:
            log.info(f"{_TAG} Unloaded: '{self._selected_module}'")
        self.update_display()

    def _on_selection_changed(self, node) -> None:
        if node and node.data:
            self._selected_module = node.data
        else:
            self._selected_module = None

    def _reload_module(self, module_name: str) -> None:
        log.info(f"{_TAG} Reloading module '{module_name}'...")
        try:
            success = self._modules_runtime.reload_module(module_name)
            if not success:
                log.error(f"{_TAG} Reload failed: {self._modules_runtime.last_error}")
            else:
                log.info(f"{_TAG} Reload complete: '{module_name}'")
            self.update_display()
            if self.on_module_reloaded:
                self.on_module_reloaded(module_name, success)
        except Exception as e:
            log.error(f"{_TAG} Reload exception for '{module_name}': {e}")

    def update_display(self) -> None:
        self._tree.clear()

        records = sorted(self._modules_runtime.records(), key=lambda record: record.id)
        loaded_count = 0
        failed_count = 0

        for record in records:
            if record.state == ModuleState.Loaded:
                loaded_count += 1
            elif record.state == ModuleState.Failed:
                failed_count += 1

            row = self._make_module_row(
                record.id,
                record.state.name.lower(),
                ", ".join(record.components) if record.components else record.kind.name.lower(),
            )
            node = TreeNode(content=row)
            node.data = record.id
            self._tree.add_root(node)

        if loaded_count == 0 and failed_count == 0:
            self._status_label.text = "No modules"
        else:
            parts = []
            if loaded_count > 0:
                parts.append(f"{loaded_count} loaded")
            if failed_count > 0:
                parts.append(f"{failed_count} failed")
            self._status_label.text = ", ".join(parts)

    def _make_module_row(self, name: str, status: str, components: str) -> Widget:
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
        comp_lbl.preferred_width = px(160)
        row.add_child(comp_lbl)

        return row
