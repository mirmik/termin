"""Modules panel for tcgui editor — project modules runtime."""

from __future__ import annotations

from tcbase import log
from tcgui.widgets.widget import Widget
from tcgui.widgets.basic import Label, Button
from tcgui.widgets.containers import VStack, HStack
from tcgui.widgets.scroll_area import ScrollArea
from tcgui.widgets.tree import TreeWidget, TreeNode
from tcgui.widgets.units import px

from termin.project_modules.runtime import get_project_modules_runtime
from termin.editor_core.modules_panel_model import module_recovery_hint
from termin.editor_tcgui.dialogs.module_operation_dialog import show_module_operation_dialog
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
    if status in ("failed", "cleanup-failed"):
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
        self._operation_running = False
        self._operation_message = ""
        self._operation_buttons: list[Button] = []
        self._modules_runtime = get_project_modules_runtime()
        self._modules_runtime.add_listener(self._on_runtime_event)

        self.on_module_reloaded = None

        self._build_ui()

    def _build_ui(self) -> None:
        toolbar = HStack()
        toolbar.spacing = 8
        toolbar.preferred_height = px(28)

        rescan_btn = Button()
        rescan_btn.text = "Rescan"
        rescan_btn.font_size = 11
        rescan_btn.padding = 4
        rescan_btn.on_click = self._on_rescan_clicked
        toolbar.add_child(rescan_btn)
        self._operation_buttons.append(rescan_btn)

        reload_changed_btn = Button()
        reload_changed_btn.text = "Reload Changed"
        reload_changed_btn.font_size = 11
        reload_changed_btn.padding = 4
        reload_changed_btn.on_click = self._on_reload_changed_clicked
        toolbar.add_child(reload_changed_btn)
        self._operation_buttons.append(reload_changed_btn)

        build_reload_changed_btn = Button()
        build_reload_changed_btn.text = "Build & Reload Changed"
        build_reload_changed_btn.font_size = 11
        build_reload_changed_btn.padding = 4
        build_reload_changed_btn.on_click = self._on_build_reload_changed_clicked
        toolbar.add_child(build_reload_changed_btn)
        self._operation_buttons.append(build_reload_changed_btn)

        spacer = Label()
        spacer.stretch = True
        toolbar.add_child(spacer)

        self._reload_btn = Button()
        self._reload_btn.text = "Reload"
        self._reload_btn.font_size = 11
        self._reload_btn.padding = 4
        self._reload_btn.on_click = self._on_reload_clicked
        toolbar.add_child(self._reload_btn)
        self._operation_buttons.append(self._reload_btn)

        self._build_btn = Button()
        self._build_btn.text = "Build"
        self._build_btn.font_size = 11
        self._build_btn.padding = 4
        self._build_btn.on_click = self._on_build_clicked
        toolbar.add_child(self._build_btn)
        self._operation_buttons.append(self._build_btn)

        self._clean_btn = Button()
        self._clean_btn.text = "Clean"
        self._clean_btn.font_size = 11
        self._clean_btn.padding = 4
        self._clean_btn.on_click = self._on_clean_clicked
        toolbar.add_child(self._clean_btn)
        self._operation_buttons.append(self._clean_btn)

        self._rebuild_btn = Button()
        self._rebuild_btn.text = "Rebuild"
        self._rebuild_btn.font_size = 11
        self._rebuild_btn.padding = 4
        self._rebuild_btn.on_click = self._on_rebuild_clicked
        toolbar.add_child(self._rebuild_btn)
        self._operation_buttons.append(self._rebuild_btn)

        self._unload_btn = Button()
        self._unload_btn.text = "Unload"
        self._unload_btn.font_size = 11
        self._unload_btn.padding = 4
        self._unload_btn.on_click = self._on_unload_clicked
        toolbar.add_child(self._unload_btn)
        self._operation_buttons.append(self._unload_btn)

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
        header.add_child(_hdr("Details", 260))
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

    def _on_rescan_clicked(self) -> None:
        project_root = self._modules_runtime.project_root
        if project_root is None:
            log.error(f"{_TAG} No project root is configured for modules runtime")
            return
        self._run_operation(
            title="Rescan Project Modules",
            running_message=f"Rescanning project: {project_root}",
            success_message="Rescan complete",
            failure_message="Rescan failed",
            prepare_action=lambda: self._modules_runtime.prepare_module_artifacts(
                project_root=project_root
            ),
            followup_action=lambda: self._modules_runtime.load_project(project_root),
        )

    def _on_reload_changed_clicked(self) -> None:
        self._run_operation(
            title="Reload Changed Modules",
            running_message="Reloading changed modules...",
            success_message="Reload changed modules complete",
            failure_message="Reload changed modules failed",
            prepare_action=self._modules_runtime.prepare_module_artifacts,
            followup_action=self._modules_runtime.reload_dirty_modules,
        )

    def _on_build_reload_changed_clicked(self) -> None:
        self._run_operation(
            title="Build and Reload Changed Modules",
            running_message="Building and reloading changed modules...",
            success_message="Build and reload changed modules complete",
            failure_message="Build and reload changed modules failed",
            prepare_action=self._modules_runtime.prepare_module_artifacts,
            followup_action=self._modules_runtime.prepare_changed_modules_for_play,
        )

    def _on_reload_clicked(self) -> None:
        if self._selected_module:
            self._reload_module(self._selected_module)

    def _on_build_clicked(self) -> None:
        if not self._selected_module:
            return
        module_name = self._selected_module
        self._run_operation(
            title=f"Build Module: {module_name}",
            running_message=f"Building module '{module_name}'...",
            success_message=f"Build complete: '{module_name}'",
            failure_message="Build failed",
            prepare_action=lambda: self._modules_runtime.prepare_module_artifacts(
                operation="build", module_id=module_name
            ),
        )

    def _on_clean_clicked(self) -> None:
        if not self._selected_module:
            return
        module_name = self._selected_module
        self._run_operation(
            title=f"Clean Module: {module_name}",
            running_message=f"Cleaning module '{module_name}'...",
            success_message=f"Clean complete: '{module_name}'",
            failure_message="Clean failed",
            prepare_action=lambda: self._modules_runtime.prepare_module_artifacts(
                operation="clean", module_id=module_name
            ),
        )

    def _on_rebuild_clicked(self) -> None:
        if not self._selected_module:
            return
        module_name = self._selected_module
        self._run_operation(
            title=f"Rebuild Module: {module_name}",
            running_message=f"Rebuilding module '{module_name}'...",
            success_message=f"Rebuild complete: '{module_name}'",
            failure_message="Rebuild failed",
            prepare_action=lambda: self._modules_runtime.prepare_module_artifacts(
                operation="rebuild", module_id=module_name
            ),
            followup_action=lambda: self._modules_runtime.unload_module(module_name),
        )

    def _on_unload_clicked(self) -> None:
        if not self._selected_module:
            return
        module_name = self._selected_module
        self._run_operation(
            title=f"Unload Module: {module_name}",
            running_message=f"Unloading module '{module_name}'...",
            success_message=f"Unloaded: '{module_name}'",
            failure_message="Unload failed",
            followup_action=lambda: self._modules_runtime.unload_module(module_name),
        )

    def _on_selection_changed(self, node) -> None:
        if node and node.data:
            self._selected_module = node.data
        else:
            self._selected_module = None

    def _reload_module(self, module_name: str) -> None:
        def on_complete(success: bool) -> None:
            if self.on_module_reloaded:
                self.on_module_reloaded(module_name, success)

        self._run_operation(
            title=f"Reload Module: {module_name}",
            running_message=f"Reloading module '{module_name}'...",
            success_message=f"Reload complete: '{module_name}'",
            failure_message="Reload failed",
            prepare_action=self._modules_runtime.prepare_module_artifacts,
            followup_action=lambda: self._modules_runtime.reload_module(module_name),
            on_complete=on_complete,
        )

    def _run_operation(
        self,
        *,
        title: str,
        running_message: str,
        success_message: str,
        failure_message: str,
        prepare_action=None,
        followup_action=None,
        on_complete=None,
    ) -> None:
        if self._operation_running:
            log.info(f"{_TAG} Ignoring '{title}' because another module operation is running")
            return

        ui = self._ui
        if ui is None:
            log.info(f"{_TAG} {running_message}")
            try:
                success = True
                if prepare_action is not None:
                    success = prepare_action()
                if success and followup_action is not None:
                    success = followup_action()
            except Exception as e:
                log.error(f"{_TAG} {failure_message}: {e}", exc_info=True)
                success = False
            self._finish_operation(success, success_message, failure_message, on_complete)
            return

        log.info(f"{_TAG} {running_message}")
        self._operation_running = True
        self._operation_message = running_message
        self._set_operation_buttons_enabled(False)
        self._status_label.text = running_message
        ui.request_layout()

        show_module_operation_dialog(
            ui,
            self._modules_runtime,
            title=title,
            start_message=running_message,
            prepare_action=prepare_action,
            followup_action=followup_action,
            on_complete=lambda success: self._finish_operation(
                success,
                success_message,
                failure_message,
                on_complete,
            ),
        )

    def _finish_operation(
        self,
        success: bool,
        success_message: str,
        failure_message: str,
        on_complete,
    ) -> None:
        if success:
            log.info(f"{_TAG} {success_message}")
        else:
            log.error(f"{_TAG} {failure_message}: {self._modules_runtime.last_error}")

        self._operation_running = False
        self._operation_message = ""
        self._set_operation_buttons_enabled(True)
        self.update_display()
        if on_complete:
            on_complete(success)

    def _set_operation_buttons_enabled(self, enabled: bool) -> None:
        for button in self._operation_buttons:
            button.enabled = enabled

    def update_display(self) -> None:
        if self._operation_running:
            if self._operation_message:
                self._status_label.text = self._operation_message
            return

        self._tree.clear()

        records = sorted(self._modules_runtime.records(), key=lambda record: record.id)
        dirty = self._modules_runtime.dirty_modules()
        stale = set(self._modules_runtime.stale_modules())
        loaded_count = 0
        failed_count = 0
        dirty_count = 0

        for record in records:
            if record.state == ModuleState.Loaded:
                loaded_count += 1
            elif record.state in (ModuleState.Failed, ModuleState.CleanupFailed):
                failed_count += 1
            if record.id in dirty or record.id in stale:
                dirty_count += 1

            details = record.kind.name.lower()
            flags = []
            recovery = (
                module_recovery_hint(record.state, record.cleanup_phase)
                if record.state == ModuleState.CleanupFailed
                else module_recovery_hint(record.state)
            )
            if recovery is not None:
                flags.append(recovery)
            if record.id in dirty:
                flags.append("dirty")
            if record.id in stale:
                flags.append("stale")
            if flags:
                details = f"{details} ({', '.join(flags)})"
            row = self._make_module_row(
                record.id,
                "cleanup-failed"
                if record.state == ModuleState.CleanupFailed
                else record.state.name.lower(),
                details,
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
            if dirty_count > 0:
                parts.append(f"{dirty_count} changed")
            self._status_label.text = ", ".join(parts)

    def _make_module_row(self, name: str, status: str, details: str) -> Widget:
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

        details_lbl = Label()
        details_lbl.text = details
        details_lbl.font_size = 12
        details_lbl.text_color = _TEXT_DIM
        details_lbl.preferred_width = px(260)
        row.add_child(details_lbl)

        return row
