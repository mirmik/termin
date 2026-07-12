"""Native profiler panel backed by the toolkit-neutral profiler controller."""

from __future__ import annotations

from dataclasses import dataclass

from termin.editor_core.profiler_model import ProfilerController, ProfilerSnapshot
from termin.editor_native.metrics import EDITOR_UI_METRICS
from termin.gui_native import (
    CommandData,
    CommandKind,
    CommandModel,
    Document,
    FrameTimeModel,
    Size,
    TableColumn,
    TableColumnModel,
    TableColumnPolicy,
    TableModel,
    TableRowData,
    WidgetRef,
)


def _ref(document: Document, reference) -> WidgetRef:
    return reference if isinstance(reference, WidgetRef) else document.ref(reference.handle)


@dataclass(frozen=True)
class NativeProfilerPanel:
    root: WidgetRef
    controller: ProfilerController
    toolbar: object
    status_bar: object
    table_widget: object
    command_model: CommandModel
    table_model: TableModel
    column_model: TableColumnModel
    frame_time_model: FrameTimeModel
    enable_command: int
    detailed_command: int
    include_ui_command: int
    clear_command: int

    def set_visible(self, visible: bool) -> None:
        visible = bool(visible)
        self.root.visible = visible
        if visible and not self.controller.enabled:
            self.controller.set_enabled(True)
        self.command_model.set_checked(self.enable_command, self.controller.enabled)

    def clear(self) -> None:
        self.controller.clear()
        self.frame_time_model.clear()
        self.table_model.clear()
        self.status_bar.text = "Profiler | waiting for a complete frame"

    def update(self) -> bool:
        snapshot = self.controller.poll()
        if snapshot is None:
            return False
        self._apply_snapshot(snapshot)
        return True

    def _apply_snapshot(self, snapshot: ProfilerSnapshot) -> None:
        self.frame_time_model.add_sample(snapshot.frame_ms)
        self.status_bar.text = (
            f"Profiler | {snapshot.fps:.0f} FPS | {snapshot.frame_ms:.2f} ms | "
            f"frame {snapshot.frame_number}"
        )
        self.table_model.set_rows(
            [
                TableRowData(
                    row.path,
                    [
                        f"{'  ' * row.depth}{row.name}",
                        f"{row.cpu_ms:.2f}",
                        f"{row.percent:.1f}%",
                        f"{row.coverage_percent:.0f}%" if row.has_children else "",
                        str(row.call_count) if row.call_count > 1 else "",
                    ],
                )
                for row in snapshot.rows
            ]
        )


def build_native_profiler_panel(
    document: Document,
    controller: ProfilerController,
) -> NativeProfilerPanel:
    root = document.create_vstack("native-profiler-panel")
    root.stable_id = "editor.profiler"
    root.preferred_size = Size(480.0, 626.0)
    root.set_layout_padding(EDITOR_UI_METRICS.panel_insets)
    root.set_layout_spacing(EDITOR_UI_METRICS.spacing)

    commands = CommandModel()
    enable = commands.append(
        CommandData("enable", "Enable", checkable=True, checked=controller.enabled)
    )
    detailed = commands.append(
        CommandData("detailed", "Detailed", checkable=True, checked=controller.detailed)
    )
    include_ui = commands.append(
        CommandData("include-ui", "Include UI", checkable=True, checked=controller.include_ui)
    )
    commands.append(CommandData("separator", kind=CommandKind.Separator))
    clear = commands.append(CommandData("clear", "Clear"))
    toolbar = document.create_tool_bar(commands)
    root.add_fixed_child(_ref(document, toolbar), EDITOR_UI_METRICS.toolbar)

    status = document.create_status_bar("Profiler | waiting for a complete frame")
    root.add_fixed_child(_ref(document, status), EDITOR_UI_METRICS.status_row)

    frame_model = FrameTimeModel()
    frame_model.max_samples = 180
    graph = document.create_frame_time_graph(frame_model)
    root.add_fixed_child(_ref(document, graph), 96.0)

    table_model = TableModel()
    column_model = TableColumnModel()
    column_model.set_columns(
        [
            TableColumn(
                "section",
                "Section",
                TableColumnPolicy.Stretch,
                min_width=150.0,
                stretch=1.0,
            ),
            TableColumn("milliseconds", "ms", TableColumnPolicy.Fixed, width=66.0),
            TableColumn("percent", "%", TableColumnPolicy.Fixed, width=58.0),
            TableColumn("coverage", "Cov", TableColumnPolicy.Fixed, width=54.0),
            TableColumn("calls", "N", TableColumnPolicy.Fixed, width=42.0),
        ]
    )
    table = document.create_table_widget(table_model, column_model)
    root.add_stretch_child(_ref(document, table))

    panel = NativeProfilerPanel(
        root=root,
        controller=controller,
        toolbar=toolbar,
        status_bar=status,
        table_widget=table,
        command_model=commands,
        table_model=table_model,
        column_model=column_model,
        frame_time_model=frame_model,
        enable_command=enable,
        detailed_command=detailed,
        include_ui_command=include_ui,
        clear_command=clear,
    )

    def on_activated(_index: int, command_id: int, command) -> None:
        if command_id == enable:
            controller.set_enabled(command.checked)
            if not command.checked:
                panel.clear()
        elif command_id == detailed:
            controller.set_detailed(command.checked)
        elif command_id == include_ui:
            controller.set_include_ui(command.checked)
        elif command_id == clear:
            panel.clear()

    toolbar.connect_activated(on_activated)
    return panel


def connect_profiler_menu_toggle(
    menu_bar,
    profiler_command: int,
    panel: NativeProfilerPanel,
    request_render,
    set_docked=None,
) -> None:
    """Connect the shell-level Profiler command without coupling the shell to its view."""

    def on_menu_activated(_menu_index: int, command_id: int, command) -> None:
        if command_id == profiler_command:
            panel.set_visible(command.checked)
            if set_docked is not None:
                set_docked(command.checked)
            request_render()

    menu_bar.connect_activated(on_menu_activated)


__all__ = [
    "NativeProfilerPanel",
    "build_native_profiler_panel",
    "connect_profiler_menu_toggle",
]
