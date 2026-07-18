"""Standalone native frame-capture profiler window."""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
import json
import logging
import time
from typing import Callable
import weakref

from termin.editor_core.profiler_capture import (
    CapturedFrame,
    ProfilerCaptureSession,
    project_captured_sections,
)
from termin.editor_native.ui_host import NativeUiWindow, NativeUiWindowManager
from termin.gui_native import (
    CommandData,
    CommandKind,
    CommandModel,
    Document,
    EdgeInsets,
    FrameTimelineModel,
    FrameTimelineSample,
    RichTextModel,
    Size,
    TableColumn,
    TableColumnModel,
    TableColumnPolicy,
    TreeExpansionModel,
    TreeTableModel,
    TreeTableRowData,
    WidgetRef,
)


_logger = logging.getLogger(__name__)


def _ref(document: Document, reference) -> WidgetRef:
    return reference if isinstance(reference, WidgetRef) else document.ref(reference.handle)


def _path_id(path: tuple[str, ...]) -> str:
    return json.dumps(path, ensure_ascii=False, separators=(",", ":"))


@dataclass
class NativeFrameProfiler:
    document: Document
    window_manager: NativeUiWindowManager
    session: ProfilerCaptureSession
    root: WidgetRef
    command_model: CommandModel
    toolbar: object
    summary_bar: object
    timeline_model: FrameTimelineModel
    timeline: object
    section_model: TreeTableModel
    section_columns: TableColumnModel
    section_expansion: TreeExpansionModel
    section_table: object
    detail_model: RichTextModel
    status_bar: object
    commands: dict[str, int]
    get_include_ui: Callable[[], bool]
    set_include_ui: Callable[[bool], None]
    refresh_interval_seconds: float = 0.1
    window: NativeUiWindow | None = None
    known_section_ids: set[str] = field(default_factory=set)
    _updating: bool = False
    _closed: bool = False
    _rendered_revision: int = -1
    _last_refresh_time: float = 0.0
    _timeline_first_frame_number: int | None = None
    _timeline_last_frame_number: int | None = None
    _timeline_frame_count: int = 0

    def show(self) -> bool:
        if self._closed:
            raise RuntimeError("native frame profiler is closed")
        if self.window is not None and not self.window.closed:
            return False
        self.session.start_capture()
        self.refresh(force=True)
        try:
            self.window = self.window_manager.create_window(
                "Frame Profiler",
                1180,
                760,
                document=self.document,
                on_close=self._on_window_closed,
            )
        except Exception:
            self.session.pause()
            raise
        self.request_render()
        return True

    def update(self) -> bool:
        if self.window is None or self.window.closed:
            return False
        self.session.poll()
        now = time.monotonic()
        if (
            self._rendered_revision != self.session.revision
            and now - self._last_refresh_time >= self.refresh_interval_seconds
        ):
            self.refresh()
            return True
        return False

    def refresh(self, *, force: bool = False) -> None:
        if not force and self._rendered_revision == self.session.revision:
            return
        self._updating = True
        try:
            frames = self.session.frames
            self.command_model.set_checked(self.commands["capture"], self.session.capturing)
            capture_data = self.command_model.command(self.commands["capture"]).data
            capture_data.label = "Pause" if self.session.capturing else "Capture"
            self.command_model.update(self.commands["capture"], capture_data)
            self.command_model.set_checked(self.commands["follow"], self.session.follow_latest)
            self.command_model.set_checked(self.commands["include-ui"], self.get_include_ui())
            self.timeline.follow_latest = self.session.follow_latest
            self._sync_timeline(frames)
            selected = self.session.selected_frame_number
            if selected is not None and self.timeline.selected_id != selected:
                self.timeline.select(selected)
            self._refresh_summary()
            self._refresh_selected_frame()
            self._rendered_revision = self.session.revision
            self._last_refresh_time = time.monotonic()
        finally:
            self._updating = False
        self.request_render()

    @staticmethod
    def _timeline_sample(frame: CapturedFrame) -> FrameTimelineSample:
        return FrameTimelineSample(
            frame.frame_number,
            frame.interval_ms,
            frame.active_ms,
            frame.profile.deadline_lateness_ms,
            frame.profile.target_interval_ms,
            frame.hitch,
            frame.source_gap_before > 0,
        )

    def _sync_timeline(self, frames: tuple[CapturedFrame, ...]) -> None:
        if not frames:
            self.timeline_model.clear()
            self._timeline_first_frame_number = None
            self._timeline_last_frame_number = None
            self._timeline_frame_count = 0
            return

        first_frame_number = frames[0].frame_number
        last_frame_number = frames[-1].frame_number
        if self._timeline_last_frame_number is not None:
            if (
                self._timeline_first_frame_number == first_frame_number
                and self._timeline_last_frame_number == last_frame_number
                and self._timeline_frame_count == len(frames)
            ):
                return
            append_start = len(frames)
            while (
                append_start > 0
                and frames[append_start - 1].frame_number > self._timeline_last_frame_number
            ):
                append_start -= 1
            appended = frames[append_start:]
            if appended:
                self.timeline_model.append_samples(
                    [self._timeline_sample(frame) for frame in appended],
                    self.session.capacity,
                )
                self._timeline_first_frame_number = first_frame_number
                self._timeline_last_frame_number = last_frame_number
                self._timeline_frame_count = len(frames)
                return

        self.timeline_model.set_samples([self._timeline_sample(frame) for frame in frames])
        self._timeline_first_frame_number = first_frame_number
        self._timeline_last_frame_number = last_frame_number
        self._timeline_frame_count = len(frames)

    def clear(self) -> None:
        self.session.clear()
        self.timeline_model.clear()
        self._timeline_first_frame_number = None
        self._timeline_last_frame_number = None
        self._timeline_frame_count = 0
        self.section_model.clear()
        self.section_expansion.clear()
        self.known_section_ids.clear()
        self.refresh(force=True)

    def dismiss(self) -> None:
        if self.window is not None and not self.window.closed:
            self.window.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.dismiss()
        self.session.close()
        if self.document.is_alive(self.root.handle):
            self.document.destroy_widget_recursive(self.root.handle)

    def request_render(self) -> None:
        if self.window is not None and not self.window.closed:
            self.window.request_render_update()

    def _on_window_closed(self) -> None:
        self.window = None
        self.session.pause()
        self._rendered_revision = -1

    def _refresh_summary(self) -> None:
        stats = self.session.statistics()
        state = "capturing" if self.session.capturing else "paused"
        self.summary_bar.text = (
            f"{state.capitalize()} | {stats.frame_count} frames | "
            f"p50 {stats.interval_p50_ms:.2f} ms | p95 {stats.interval_p95_ms:.2f} ms | "
            f"p99 {stats.interval_p99_ms:.2f} ms | max {stats.max_interval_ms:.2f} ms | "
            f"hitches {stats.hitch_count}"
        )
        self.status_bar.text = (
            f"Source gaps: {self.session.source_dropped_count} | "
            "Mouse wheel: scroll history | Ctrl+wheel: zoom timeline | Arrow keys: select frame"
        )

    def _refresh_selected_frame(self) -> None:
        captured = self.session.selected_frame
        if captured is None:
            self.section_model.clear()
            self.detail_model.set_html("<b>No frame selected</b>")
            return

        profile = captured.profile
        rows = project_captured_sections(profile)
        stable_ids = {row.path: _path_id(row.path) for row in rows}
        self.section_model.set_rows(
            [
                TreeTableRowData(
                    stable_ids[row.path],
                    stable_ids.get(row.path[:-1], ""),
                    [
                        row.name,
                        f"{row.inclusive_ms:.3f}",
                        f"{row.self_ms:.3f}",
                        f"{row.percent:.1f}%",
                        f"{row.coverage_percent:.0f}%" if row.has_children else "",
                        str(row.call_count) if row.call_count > 1 else "",
                    ],
                )
                for row in rows
            ]
        )
        current_ids = set(stable_ids.values())
        for root in self.section_model.roots:
            stable_id = self.section_model.node(root).data.stable_id
            if stable_id not in self.known_section_ids:
                self.section_table.set_expanded(root, True)
        self.known_section_ids.update(current_ids)
        gap = "—" if captured.pacing_gap_ms is None else f"{captured.pacing_gap_ms:.3f} ms"
        hitch = "yes" if captured.hitch else "no"
        self.detail_model.set_html(
            f"<b>Frame {profile.frame_number}</b><br>"
            f"Interval: {profile.interval_ms:.3f} ms<br>"
            f"Active: {profile.active_ms:.3f} ms<br>"
            f"Pacing gap: {gap}<br>"
            f"Target: {profile.target_interval_ms:.3f} ms<br>"
            f"Deadline lateness: {profile.deadline_lateness_ms:.3f} ms<br>"
            f"Missed intervals: {profile.missed_intervals}<br>"
            f"Hitch: {hitch}"
        )

    def show_section_details(self, node: int) -> None:
        if self._updating or not self.section_model.contains(node):
            return
        data = self.section_model.node(node).data
        cells = data.cells
        self.detail_model.set_html(
            f"<b>{escape(cells[0])}</b><br>"
            f"Inclusive: {escape(cells[1])} ms<br>"
            f"Self: {escape(cells[2])} ms<br>"
            f"Frame share: {escape(cells[3])}<br>"
            f"Child coverage: {escape(cells[4] or '—')}<br>"
            f"Calls: {escape(cells[5] or '1')}"
        )
        self.request_render()


def build_native_frame_profiler(
    window_manager: NativeUiWindowManager,
    session: ProfilerCaptureSession,
    *,
    get_include_ui: Callable[[], bool],
    set_include_ui: Callable[[bool], None],
) -> NativeFrameProfiler:
    document = Document()
    root = document.create_vstack("native-frame-profiler")
    root.stable_id = "editor.frame-profiler"
    root.preferred_size = Size(1180.0, 760.0)
    root.set_layout_padding(EdgeInsets(5.0, 5.0, 5.0, 5.0))
    root.set_layout_spacing(5.0)
    if not document.add_root(root.handle):
        raise RuntimeError("failed to add native frame profiler root")

    command_model = CommandModel()
    commands = {
        "capture": command_model.append(CommandData("capture", "Capture", checkable=True)),
        "clear": command_model.append(CommandData("clear", "Clear")),
    }
    command_model.append(CommandData("separator-1", kind=CommandKind.Separator))
    commands["follow"] = command_model.append(
        CommandData("follow", "Follow", checkable=True, checked=True)
    )
    commands["include-ui"] = command_model.append(
        CommandData("include-ui", "Include UI", checkable=True, checked=get_include_ui())
    )
    command_model.append(CommandData("separator-2", kind=CommandKind.Separator))
    commands["previous-hitch"] = command_model.append(CommandData("previous-hitch", "Previous Hitch"))
    commands["next-hitch"] = command_model.append(CommandData("next-hitch", "Next Hitch"))
    toolbar = document.create_tool_bar(command_model)
    root.add_fixed_child(_ref(document, toolbar), 30.0)

    summary = document.create_status_bar("Frame capture is not started")
    root.add_fixed_child(_ref(document, summary), 24.0)

    timeline_model = FrameTimelineModel()
    timeline = document.create_frame_timeline(timeline_model)
    timeline.window_size = 180
    timeline.set_warning_ratio(session.hitch_ratio)
    root.add_fixed_child(_ref(document, timeline), 220.0)

    section_model = TreeTableModel()
    section_columns = TableColumnModel()
    section_columns.set_columns(
        [
            TableColumn("section", "Section", TableColumnPolicy.Stretch, min_width=180.0),
            TableColumn("inclusive", "Incl ms", TableColumnPolicy.Fixed, width=74.0),
            TableColumn("self", "Self ms", TableColumnPolicy.Fixed, width=74.0),
            TableColumn("percent", "% frame", TableColumnPolicy.Fixed, width=68.0),
            TableColumn("coverage", "Child %", TableColumnPolicy.Fixed, width=66.0),
            TableColumn("calls", "N", TableColumnPolicy.Fixed, width=42.0),
        ]
    )
    section_expansion = TreeExpansionModel()
    section_table = document.create_tree_table_widget(
        section_model,
        section_columns,
        section_expansion,
    )
    detail_model = RichTextModel()
    detail_view = document.create_rich_text_view(detail_model)
    details = document.create_splitter(True, "frame-profiler-details")
    details.set_first(_ref(document, section_table))
    details.set_second(_ref(document, detail_view))
    details.set_min_extents(420.0, 240.0)
    details.split_fraction = 0.72
    root.add_stretch_child(_ref(document, details))

    status = document.create_status_bar("No captured frames")
    root.add_fixed_child(_ref(document, status), 24.0)

    profiler = NativeFrameProfiler(
        document=document,
        window_manager=window_manager,
        session=session,
        root=root,
        command_model=command_model,
        toolbar=toolbar,
        summary_bar=summary,
        timeline_model=timeline_model,
        timeline=timeline,
        section_model=section_model,
        section_columns=section_columns,
        section_expansion=section_expansion,
        section_table=section_table,
        detail_model=detail_model,
        status_bar=status,
        commands=commands,
        get_include_ui=get_include_ui,
        set_include_ui=set_include_ui,
    )
    weak_profiler = weakref.ref(profiler)

    def activated(_index: int, command_id: int, command) -> None:
        owner = weak_profiler()
        if owner is None:
            return
        if command_id == commands["capture"]:
            owner.session.start_capture() if command.checked else owner.session.pause()
        elif command_id == commands["clear"]:
            owner.clear()
            return
        elif command_id == commands["follow"]:
            owner.session.set_follow_latest(command.checked)
        elif command_id == commands["include-ui"]:
            owner.set_include_ui(command.checked)
        elif command_id == commands["previous-hitch"]:
            owner.session.select_adjacent_hitch(-1)
        elif command_id == commands["next-hitch"]:
            owner.session.select_adjacent_hitch(1)
        owner.refresh(force=True)

    def selected(frame_number: int) -> None:
        owner = weak_profiler()
        if owner is None or owner._updating or frame_number < 0:
            return
        if owner.session.select_frame(frame_number):
            owner.refresh(force=True)

    toolbar.connect_activated(activated)
    timeline.connect_selection_changed(selected)
    def section_selected(node: int) -> None:
        owner = weak_profiler()
        if owner is not None:
            owner.show_section_details(node)

    section_table.connect_selection_changed(section_selected)
    profiler.refresh(force=True)
    return profiler


def connect_frame_profiler_command(menu_bar, command_id: int, profiler) -> None:
    weak_profiler = weakref.ref(profiler)

    def activated(_menu_index: int, activated_id: int, _command) -> None:
        if activated_id != command_id:
            return
        owner = weak_profiler()
        if owner is not None:
            owner.show()

    menu_bar.connect_activated(activated)


__all__ = [
    "NativeFrameProfiler",
    "build_native_frame_profiler",
    "connect_frame_profiler_command",
]
