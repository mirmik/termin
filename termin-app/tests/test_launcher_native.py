from __future__ import annotations

import importlib
import sys
from pathlib import Path

from termin.gui_native import Document, Rect
from termin.launcher.controller import LaunchResult, LauncherController, LauncherServices
from termin.launcher.native_app import NativeLauncherProjection


class MemoryRecentProjects:
    def __init__(self, entries: list[dict]) -> None:
        self.entries = entries

    def list(self) -> list[dict]:
        return list(self.entries)

    def add(self, project_path: str) -> None:
        self.remove(project_path)
        self.entries.insert(0, {"name": Path(project_path).stem, "path": project_path})

    def remove(self, project_path: str) -> None:
        self.entries = [entry for entry in self.entries if entry["path"] != project_path]


def make_controller(
    *,
    choose_directory=lambda: "",
    choose_project_file=lambda: "",
    create_project=lambda name, location: str(Path(location) / f"{name}.terminproj"),
    launch_editor=lambda _path: LaunchResult(started=True),
) -> LauncherController:
    return LauncherController(
        MemoryRecentProjects(
            [
                {"name": "First", "path": "/projects/First/First.terminproj"},
                {"name": "Second", "path": "/projects/Second/Second.terminproj"},
            ]
        ),
        LauncherServices(
            choose_directory=choose_directory,
            choose_project_file=choose_project_file,
            create_project=create_project,
            launch_editor=launch_editor,
            report_error=lambda _message: None,
        ),
    )


def test_native_launcher_main_projection_has_stable_actions_and_selection() -> None:
    document = Document()
    controller = make_controller()
    projection = NativeLauncherProjection(document, controller)
    document.layout_roots(Rect(0.0, 0.0, 1024.0, 640.0))

    assert projection.root.stable_id == "launcher.main"
    assert projection.widgets["recent_list"].widget.stable_id == "launcher.recent-projects"
    assert projection.widgets["new"].widget.stable_id == "launcher.action.new"
    assert not projection.widgets["open"].widget.enabled
    assert not projection.widgets["remove"].widget.enabled

    projection.widgets["recent_list"].select(1)
    assert controller.state.selected_project_path == "/projects/Second/Second.terminproj"
    assert projection.widgets["open"].widget.enabled
    assert projection.widgets["remove"].widget.enabled
    projection.close()


def test_native_launcher_activation_and_all_main_actions_use_controller() -> None:
    launched: list[str] = []
    controller = make_controller(
        choose_project_file=lambda: "/external/Game.terminproj",
        launch_editor=lambda path: launched.append(path) or LaunchResult(started=True),
    )
    projection = NativeLauncherProjection(Document(), controller)

    projection._project_activated(0, projection.models["recent"].item(0))
    assert launched == ["/projects/First/First.terminproj"]

    projection.widgets["recent_list"].select(1)
    projection._open_selected()
    projection._open_existing()
    assert launched[-2:] == [
        "/projects/Second/Second.terminproj",
        "/external/Game.terminproj",
    ]

    projection.widgets["recent_list"].select(0)
    projection._remove_selected()
    assert len(controller.state.recent_projects) == 2
    assert all(project.path != "/external/Game.terminproj" for project in controller.state.recent_projects)
    projection.close()


def test_native_launcher_new_project_form_preserves_state_and_shows_errors() -> None:
    launched: list[str] = []
    controller = make_controller(
        choose_directory=lambda: "/workspace",
        launch_editor=lambda path: launched.append(path) or LaunchResult(started=True),
    )
    projection = NativeLauncherProjection(Document(), controller)

    projection._show_new_project()
    assert projection.root.stable_id == "launcher.new-project"
    assert projection.widgets["name"].widget.stable_id == "launcher.new-project.name"
    projection._create_project()
    assert projection.widgets["error"].visible
    assert "required" in projection.widgets["error"].text

    projection.widgets["name"].text = "Demo"
    projection._choose_location()
    projection._create_project()
    assert launched == ["/workspace/Demo.terminproj"]

    projection._show_main()
    assert projection.root.stable_id == "launcher.main"
    projection.close()


def test_default_launcher_module_import_does_not_load_tcgui_widgets() -> None:
    for name in tuple(sys.modules):
        if name == "tcgui" or name.startswith("tcgui."):
            del sys.modules[name]

    from termin.launcher import app

    importlib.reload(app)
    assert not any(name.startswith("tcgui.widgets") for name in sys.modules)


def test_launcher_cli_accepts_native_default_and_explicit_legacy(monkeypatch) -> None:
    from termin.launcher import app

    monkeypatch.setattr(sys, "argv", ["termin_launcher"])
    assert app._parse_launcher_args() == (None, None)
    monkeypatch.setattr(sys, "argv", ["termin_launcher", "--ui=native"])
    assert app._parse_launcher_args() == (None, "native")
    monkeypatch.setattr(sys, "argv", ["termin_launcher", "--ui=tcgui"])
    assert app._parse_launcher_args() == (None, "tcgui")
