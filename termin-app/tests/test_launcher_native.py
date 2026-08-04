from __future__ import annotations
from termin.gui_native import tc_ui_document_create, tc_ui_document_destroy

import importlib
import sys
from pathlib import Path

import pytest

from termin.gui_native import Rect
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

    def restore(self, projects: list[dict]) -> None:
        self.entries = list(projects)

    def remove(self, project_path: str) -> None:
        self.entries = [entry for entry in self.entries if entry["path"] != project_path]


def make_controller(
    *,
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
            create_project=create_project,
            launch_editor=launch_editor,
            report_error=lambda _message: None,
        ),
    )


def test_native_launcher_main_projection_has_stable_actions_and_selection() -> None:
    document = tc_ui_document_create()
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
    tc_ui_document_destroy(document)


def test_native_launcher_activation_and_all_main_actions_use_controller(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: tmp_path))
    launched: list[str] = []
    controller = make_controller(
        launch_editor=lambda path: launched.append(path) or LaunchResult(started=True),
    )
    project = tmp_path / "Game.terminproj"
    project.write_text("", encoding="utf-8")
    document = tc_ui_document_create()
    projection = NativeLauncherProjection(document, controller)

    projection._project_activated(0, projection.models["recent"].item(0))
    assert launched == ["/projects/First/First.terminproj"]

    projection.widgets["recent_list"].select(1)
    projection._open_selected()
    projection._open_existing()
    assert projection.active_file_dialog_count == 1
    dialog = next(iter(projection._file_dialogs.values()))
    assert dialog.model.navigate(str(tmp_path))
    project_index = next(
        index
        for index, entry in enumerate(dialog.model.entries)
        if entry.path == str(project)
    )
    assert dialog.model.select(project_index)
    assert dialog.activate("accept")
    assert projection.active_file_dialog_count == 0
    assert launched[-2:] == [
        "/projects/Second/Second.terminproj",
        str(project),
    ]

    projection.widgets["recent_list"].select(0)
    projection._remove_selected()
    assert len(controller.state.recent_projects) == 2
    assert all(project.path != "/external/Game.terminproj" for project in controller.state.recent_projects)
    projection.close()
    tc_ui_document_destroy(document)


def test_native_launcher_new_project_form_preserves_state_and_shows_errors(
    tmp_path: Path,
) -> None:
    launched: list[str] = []
    controller = make_controller(
        launch_editor=lambda path: launched.append(path) or LaunchResult(started=True),
    )
    document = tc_ui_document_create()
    projection = NativeLauncherProjection(document, controller)

    projection._show_new_project()
    assert projection.root.stable_id == "launcher.new-project"
    assert projection.widgets["name"].widget.stable_id == "launcher.new-project.name"
    projection._create_project()
    assert projection.widgets["error"].visible
    assert "required" in projection.widgets["error"].text

    projection.widgets["name"].text = "Demo"
    controller.set_new_project_location(str(tmp_path))
    projection._choose_location()
    assert projection.active_file_dialog_count == 1
    dialog = next(iter(projection._file_dialogs.values()))
    assert dialog.model.current_directory == str(tmp_path)
    assert dialog.activate("accept")
    assert projection.active_file_dialog_count == 0
    projection._create_project()
    assert launched == [str(tmp_path / "Demo.terminproj")]

    projection._show_main()
    assert projection.root.stable_id == "launcher.main"
    projection.close()
    tc_ui_document_destroy(document)


def test_native_launcher_file_dialog_cancel_and_projection_close_release_overlays(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: tmp_path))
    launched: list[str] = []
    controller = make_controller(
        launch_editor=lambda path: launched.append(path) or LaunchResult(started=True),
    )
    document = tc_ui_document_create()
    projection = NativeLauncherProjection(document, controller)

    projection._open_existing()
    dialog = next(iter(projection._file_dialogs.values()))
    assert dialog.activate("cancel")
    assert projection.active_file_dialog_count == 0
    assert launched == []

    projection._show_new_project()
    controller.set_new_project_location(str(tmp_path))
    projection._choose_location()
    assert projection.active_file_dialog_count == 1
    projection.close()
    assert projection.active_file_dialog_count == 0
    assert document.overlay_count == 0
    tc_ui_document_destroy(document)


def test_default_launcher_module_import_does_not_load_tcgui_widgets() -> None:
    for name in tuple(sys.modules):
        if name == "tcgui" or name.startswith("tcgui."):
            del sys.modules[name]

    from termin.launcher import app

    importlib.reload(app)
    assert not any(name.startswith("tcgui.widgets") for name in sys.modules)


def test_launcher_cli_defaults_to_native_and_rejects_ui_selector(
    monkeypatch, capsys
) -> None:
    from termin.launcher import app

    monkeypatch.setattr(sys, "argv", ["termin_launcher"])
    assert app._parse_launcher_args() is None
    monkeypatch.setattr(sys, "argv", ["termin_launcher", "--ui=native"])
    assert app._parse_launcher_args() == "__error__"
    assert "only supported frontend" in capsys.readouterr().out


def test_launcher_cli_error_exits_nonzero(monkeypatch) -> None:
    from termin.launcher import app

    monkeypatch.setattr(sys, "argv", ["termin_launcher", "--ui=tcgui"])
    with pytest.raises(SystemExit, match="1"):
        app.run()
