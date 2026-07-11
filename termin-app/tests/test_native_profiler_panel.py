from tcbase import Key
from tcbase.profiler import FrameProfile, SectionTiming
from termin.editor_core.profiler_model import ProfilerController
from termin.editor_native import (
    build_native_editor_shell,
    build_native_profiler_panel,
    connect_profiler_menu_toggle,
)
from termin.gui_native import Document, DrawList, PaintContext, Rect


class FakeProfiler:
    def __init__(self) -> None:
        self.enabled = False
        self.detailed_rendering = False
        self.frames = []

    def clear_history(self) -> None:
        self.frames.clear()

    def last_complete_frame(self):
        return self.frames[-1] if self.frames else None


def test_native_profiler_panel_is_toggled_by_shell_command_and_presents_frame():
    document = Document()
    shell = build_native_editor_shell(document)
    profiler = FakeProfiler()
    include_ui = {"value": False}
    controller = ProfilerController(
        profiler,
        get_include_ui=lambda: include_ui["value"],
        set_include_ui=lambda value: include_ui.__setitem__("value", value),
    )
    panel = build_native_profiler_panel(document, controller)
    shell.profiler_host.add_stretch_child(panel.root)
    panel.root.visible = False
    renders = []
    connect_profiler_menu_toggle(
        shell.menu_bar,
        shell.profiler_command,
        panel,
        lambda: renders.append(True),
        shell.set_profiler_docked,
    )

    document.layout_roots(Rect(0.0, 0.0, 1280.0, 720.0))
    assert shell.menu_bar.dispatch_shortcut(Key.F7.value, 0)
    assert panel.root.visible
    assert shell.profiler_host.visible
    assert profiler.enabled
    assert renders == [True]

    # A side dock preserves the viewport's vertical extent.
    document.layout_roots(Rect(0.0, 0.0, 1280.0, 720.0))
    assert shell.workspace_host.bounds.height == shell.profiler_host.bounds.height
    assert shell.profiler_host.bounds.x > shell.inspector_host.bounds.x

    profiler.frames.append(
        FrameProfile(
            frame_number=12,
            total_ms=20.0,
            sections={
                "Render": SectionTiming(
                    "Render",
                    cpu_ms=18.0,
                    children_ms=8.0,
                    children={
                        "Compose": SectionTiming("Compose", cpu_ms=8.0, call_count=2)
                    },
                ),
                "Events": SectionTiming("Events", cpu_ms=2.0),
            },
        )
    )
    assert panel.update()
    assert not panel.update()
    assert panel.frame_time_model.samples == [20.0]
    assert panel.table_model.row_count == 3
    assert "50 FPS" in panel.status_bar.text
    assert panel.table_model.row_at(2).data.cells[0] == "  Compose"

    document.layout_roots(Rect(0.0, 0.0, 1280.0, 720.0))
    draw_list = DrawList()
    document.paint(PaintContext(draw_list))
    assert draw_list.command_count > 20


def test_native_profiler_panel_controls_and_clear_boundary():
    document = Document()
    profiler = FakeProfiler()
    include_ui = {"value": False}
    controller = ProfilerController(
        profiler,
        get_include_ui=lambda: include_ui["value"],
        set_include_ui=lambda value: include_ui.__setitem__("value", value),
    )
    panel = build_native_profiler_panel(document, controller)

    controller.set_detailed(True)
    controller.set_include_ui(True)
    panel.command_model.set_checked(panel.detailed_command, controller.detailed)
    panel.command_model.set_checked(panel.include_ui_command, controller.include_ui)
    assert profiler.detailed_rendering
    assert include_ui["value"]

    panel.frame_time_model.add_sample(9.0)
    panel.table_model.set_rows([])
    panel.clear()
    assert panel.frame_time_model.samples == []
    assert panel.table_model.row_count == 0
    assert "waiting" in panel.status_bar.text
