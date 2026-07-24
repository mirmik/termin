"""Native projection of the toolkit-neutral project Modules panel."""

from __future__ import annotations

from dataclasses import dataclass

from termin.editor_core.modules_panel_model import ModulesPanelController, ModulesSnapshot
from termin.editor_native.metrics import EDITOR_UI_METRICS
from termin.gui_native import (
    CommandData,
    CommandModel,
    TcDocument,
    TableColumn,
    TableColumnModel,
    TableColumnPolicy,
    TableModel,
    TableRowData,
    WidgetRef,
)


@dataclass(frozen=True)
class NativeModulesPanel:
    root: WidgetRef
    controller: ModulesPanelController
    toolbar: object
    command_model: CommandModel
    table: object
    table_model: TableModel
    status: object
    log_view: object
    commands: dict[str, int]

    def refresh(self, snapshot: ModulesSnapshot | None = None) -> None:
        snapshot = snapshot or self.controller.snapshot()
        rows = [
            TableRowData(
                row.module_id,
                [row.module_id, row.status, row.details],
            )
            for row in snapshot.rows
        ]
        current = [
            (row.data.stable_id, list(row.data.cells)) for row in self.table_model.rows
        ]
        incoming = [(row.stable_id, list(row.cells)) for row in rows]
        if current != incoming:
            self.table_model.set_rows(rows)
        self.status.text = snapshot.status
        self.log_view.text = "\n".join(snapshot.operation_log)
        for command_id in self.commands.values():
            self.command_model.set_enabled(command_id, not snapshot.operation_running)
        selected_enabled = (
            not snapshot.operation_running and snapshot.selected_module is not None
        )
        for name in ("reload", "build", "clean", "rebuild", "unload"):
            self.command_model.set_enabled(self.commands[name], selected_enabled)

    def close(self) -> None:
        self.controller.close()


def build_native_modules_panel(
    document: TcDocument,
    controller: ModulesPanelController,
) -> NativeModulesPanel:
    root = document.create_vstack("native-modules-panel")
    root.stable_id = "editor.modules"
    root.set_layout_padding(EDITOR_UI_METRICS.panel_insets)
    root.set_layout_spacing(EDITOR_UI_METRICS.spacing)

    command_model = CommandModel()
    commands = {
        name: command_model.append(CommandData(name, label))
        for name, label in (
            ("rescan", "Rescan"),
            ("reload-changed", "Reload Changed"),
            ("build-reload-changed", "Build & Reload Changed"),
            ("reload", "Reload"),
            ("build", "Build"),
            ("clean", "Clean"),
            ("rebuild", "Rebuild"),
            ("unload", "Unload"),
        )
    }
    toolbar = document.create_tool_bar(command_model)
    root.add_fixed_child(toolbar.widget, EDITOR_UI_METRICS.toolbar)

    table_model = TableModel()
    columns = TableColumnModel()
    columns.set_columns(
        [
            TableColumn("module", "Module", TableColumnPolicy.Stretch, min_width=130.0),
            TableColumn("status", "Status", TableColumnPolicy.Fixed, width=76.0),
            TableColumn("details", "Details", TableColumnPolicy.Fixed, width=220.0),
        ]
    )
    table = document.create_table_widget(table_model, columns)
    root.add_stretch_child(table.widget)
    status = document.create_status_bar("No modules")
    root.add_fixed_child(status.widget, EDITOR_UI_METRICS.status_row)
    log_view = document.create_text_area()
    log_view.widget.enabled = False
    root.add_fixed_child(log_view.widget, 110.0)

    panel = NativeModulesPanel(
        root,
        controller,
        toolbar,
        command_model,
        table,
        table_model,
        status,
        log_view,
        commands,
    )

    actions = {
        commands["rescan"]: controller.rescan,
        commands["reload-changed"]: controller.reload_changed,
        commands["build-reload-changed"]: controller.build_reload_changed,
        commands["reload"]: controller.reload_selected,
        commands["build"]: controller.build_selected,
        commands["clean"]: controller.clean_selected,
        commands["rebuild"]: controller.rebuild_selected,
        commands["unload"]: controller.unload_selected,
    }

    def activated(_index: int, command_id: int, _command) -> None:
        action = actions.get(command_id)
        if action is not None:
            action()

    def selected(indices) -> None:
        if not indices:
            controller.select(None)
            return
        row = table_model.row_at(indices[0])
        controller.select(row.data.stable_id)

    toolbar.connect_activated(activated)
    table.connect_selection_changed(selected)
    controller.set_changed_handler(panel.refresh)
    panel.refresh()
    return panel


__all__ = ["NativeModulesPanel", "build_native_modules_panel"]
