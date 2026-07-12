from types import SimpleNamespace

from tcbase import Key
from termin.editor_core.modules_panel_model import ModulesPanelController
from termin.editor_native.modules_panel import build_native_modules_panel
from termin.editor_native.shell import build_native_editor_shell
from termin.gui_native import Document, Rect
from termin_modules import ModuleKind, ModuleState


class _Runtime:
    project_root = "/project"
    last_error = ""

    def __init__(self) -> None:
        self.listeners = []

    def add_listener(self, callback) -> None:
        self.listeners.append(callback)

    def remove_listener(self, callback) -> None:
        self.listeners.remove(callback)

    def records(self):
        return [SimpleNamespace(id="game", kind=ModuleKind.Python, state=ModuleState.Loaded)]

    def dirty_modules(self):
        return {}

    def stale_modules(self):
        return []


def test_native_modules_panel_projects_runtime_and_selection() -> None:
    document = Document()
    runtime = _Runtime()
    controller = ModulesPanelController(runtime, defer=lambda callback: callback())
    panel = build_native_modules_panel(document, controller)

    assert panel.table_model.row_count == 1
    assert panel.table_model.row_at(0).data.cells == ["game", "loaded", "python"]
    assert panel.status.text == "1 loaded"
    assert not panel.command_model.command(panel.commands["build"]).data.enabled

    panel.table.select(0)

    assert controller.snapshot().selected_module == "game"
    assert panel.command_model.command(panel.commands["build"]).data.enabled
    panel.close()


def test_modules_shortcut_docks_native_debug_panel() -> None:
    document = Document()
    shell = build_native_editor_shell(document)
    runtime = _Runtime()
    controller = ModulesPanelController(runtime, defer=lambda callback: callback())
    panel = build_native_modules_panel(document, controller)
    shell.debug_tabs.add_page("Modules", panel.root)

    def activated(_index: int, command_id: int, command) -> None:
        if command_id == shell.modules_command:
            shell.set_profiler_docked(command.checked)

    shell.menu_route("debug").connect_activated(activated)
    document.layout_roots(Rect(0.0, 0.0, 1280.0, 720.0))

    assert shell.menu_bar.dispatch_shortcut(Key.F8.value, 0)
    document.layout_roots(Rect(0.0, 0.0, 1280.0, 720.0))
    assert shell.profiler_host.visible
    assert shell.profiler_host.bounds.width > 0
    assert shell.workspace_host.bounds.height == shell.profiler_host.bounds.height

    assert shell.menu_bar.dispatch_shortcut(Key.F8.value, 0)
    document.layout_roots(Rect(0.0, 0.0, 1280.0, 720.0))
    assert not shell.profiler_host.visible
    assert shell.workspace_host.bounds.width > 0
    panel.close()
