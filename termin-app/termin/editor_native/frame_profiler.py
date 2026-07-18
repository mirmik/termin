"""Window host for the C++ native frame profiler.

Capture storage, statistics, selection and native model updates live in
``FrameProfilerController``.  This module only attaches its native models to
the editor's process-wide secondary-window/event-loop infrastructure.
"""

from __future__ import annotations

from dataclasses import dataclass
import weakref

from termin.editor._editor_native import FrameProfilerController
from termin.editor_native.ui_host import NativeUiWindow, NativeUiWindowManager
from termin.gui_native import (
    Document,
    EdgeInsets,
    Size,
    TableColumn,
    TableColumnModel,
    TableColumnPolicy,
    TreeExpansionModel,
    WidgetRef,
)


def _ref(document: Document, reference) -> WidgetRef:
    return reference if isinstance(reference, WidgetRef) else document.ref(reference.handle)


@dataclass
class NativeFrameProfiler:
    document: Document
    window_manager: NativeUiWindowManager
    controller: FrameProfilerController
    root: WidgetRef
    toolbar: object
    timeline: object
    section_table: object
    window: NativeUiWindow | None = None
    _closed: bool = False
    _syncing_selection: bool = False

    def show(self) -> bool:
        if self._closed:
            raise RuntimeError("native frame profiler is closed")
        if self.window is not None and not self.window.closed:
            return False
        self.controller.start_capture()
        self.controller.update()
        try:
            self.window = self.window_manager.create_window(
                "Frame Profiler",
                1180,
                760,
                document=self.document,
                on_close=self._on_window_closed,
            )
        except Exception:
            self.controller.pause()
            raise
        self.request_render()
        return True

    def update(self) -> bool:
        if self.window is None or self.window.closed:
            return False
        changed = self.controller.update()
        if changed:
            self.timeline.follow_latest = self.controller.follow_latest
            selected = self.controller.selected_frame_number
            if selected >= 0 and self.timeline.selected_id != selected:
                self._syncing_selection = True
                try:
                    self.timeline.select(selected)
                finally:
                    self._syncing_selection = False
            self.request_render()
        return changed

    def clear(self) -> None:
        self.controller.clear()
        self.request_render()

    def dismiss(self) -> None:
        if self.window is not None and not self.window.closed:
            self.window.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.dismiss()
        self.controller.close()
        if self.document.is_alive(self.root.handle):
            self.document.destroy_widget_recursive(self.root.handle)

    def request_render(self) -> None:
        if self.window is not None and not self.window.closed:
            self.window.request_render_update()

    def _on_window_closed(self) -> None:
        self.window = None
        self.controller.pause()


def build_native_frame_profiler(
    window_manager: NativeUiWindowManager,
    controller: FrameProfilerController,
) -> NativeFrameProfiler:
    document = Document()
    root = document.create_vstack("native-frame-profiler")
    root.stable_id = "editor.frame-profiler"
    root.preferred_size = Size(1180.0, 760.0)
    root.set_layout_padding(EdgeInsets(5.0, 5.0, 5.0, 5.0))
    root.set_layout_spacing(5.0)
    if not document.add_root(root.handle):
        raise RuntimeError("failed to add native frame profiler root")

    toolbar = document.create_tool_bar(controller.command_model)
    root.add_fixed_child(_ref(document, toolbar), 30.0)
    summary = document.create_rich_text_view(controller.summary_model)
    summary.show_scrollbar = False
    root.add_fixed_child(_ref(document, summary), 24.0)

    timeline = document.create_frame_timeline(controller.timeline_model)
    timeline.window_size = 180
    timeline.set_warning_ratio(controller.hitch_ratio)
    root.add_fixed_child(_ref(document, timeline), 220.0)

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
        controller.section_model,
        section_columns,
        section_expansion,
    )
    detail_view = document.create_rich_text_view(controller.detail_model)
    details = document.create_splitter(True, "frame-profiler-details")
    details.set_first(_ref(document, section_table))
    details.set_second(_ref(document, detail_view))
    details.set_min_extents(420.0, 240.0)
    details.split_fraction = 0.72
    root.add_stretch_child(_ref(document, details))

    status = document.create_rich_text_view(controller.status_model)
    status.show_scrollbar = False
    root.add_fixed_child(_ref(document, status), 24.0)

    profiler = NativeFrameProfiler(
        document=document,
        window_manager=window_manager,
        controller=controller,
        root=root,
        toolbar=toolbar,
        timeline=timeline,
        section_table=section_table,
    )
    weak_profiler = weakref.ref(profiler)

    def activated(_index: int, command_id: int, _command) -> None:
        owner = weak_profiler()
        if owner is not None and owner.controller.activate(command_id):
            owner.timeline.follow_latest = owner.controller.follow_latest
            owner.request_render()

    def selected(frame_number: int) -> None:
        owner = weak_profiler()
        if owner is not None and not owner._syncing_selection and frame_number >= 0:
            owner.controller.select_frame(frame_number)
            owner.request_render()

    def section_selected(node: int) -> None:
        owner = weak_profiler()
        if owner is not None:
            owner.controller.show_section_details(node)
            owner.request_render()

    toolbar.connect_activated(activated)
    timeline.connect_selection_changed(selected)
    section_table.connect_selection_changed(section_selected)
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
