from __future__ import annotations

from dataclasses import dataclass, field

from termin.launcher.controller import (
    LaunchResult,
    LauncherController,
    LauncherScreen,
    LauncherServices,
)


@dataclass
class FakeRecentProjects:
    projects: list[dict]
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)

    def list(self) -> list[dict]:
        return list(self.projects)

    def add(self, project_path: str) -> None:
        self.added.append(project_path)
        self.projects = [entry for entry in self.projects if entry["path"] != project_path]
        self.projects.insert(0, {"name": "Opened", "path": project_path})

    def remove(self, project_path: str) -> None:
        self.removed.append(project_path)
        self.projects = [entry for entry in self.projects if entry["path"] != project_path]


@dataclass
class ServiceCalls:
    chosen_directory: str = ""
    chosen_project: str = ""
    created_project: str = "/projects/New/New.terminproj"
    launch_result: LaunchResult = LaunchResult(started=True, should_quit=True)
    create_calls: list[tuple[str, str]] = field(default_factory=list)
    launch_calls: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def services(self) -> LauncherServices:
        return LauncherServices(
            choose_directory=lambda: self.chosen_directory,
            choose_project_file=lambda: self.chosen_project,
            create_project=self.create,
            launch_editor=self.launch,
            report_error=self.errors.append,
        )

    def create(self, name: str, location: str) -> str:
        self.create_calls.append((name, location))
        return self.created_project

    def launch(self, project_path: str) -> LaunchResult:
        self.launch_calls.append(project_path)
        return self.launch_result


def make_controller(
    projects: list[dict] | None = None,
) -> tuple[LauncherController, FakeRecentProjects, ServiceCalls]:
    recent = FakeRecentProjects(projects or [])
    calls = ServiceCalls()
    return LauncherController(recent, calls.services()), recent, calls


def test_initial_state_and_selection_dependent_actions() -> None:
    path = "/projects/Demo/Demo.terminproj"
    controller, _recent, calls = make_controller([{"name": "Demo", "path": path}])

    assert controller.state.screen is LauncherScreen.MAIN
    assert [project.path for project in controller.state.recent_projects] == [path]
    assert controller.state.can_open_selected is False
    assert controller.open_selected_project() is False

    controller.select_project(path)
    assert controller.state.can_open_selected is True
    assert controller.open_selected_project() is True
    assert calls.launch_calls == [path]
    assert controller.state.should_quit is True


def test_screen_and_directory_picker_state() -> None:
    controller, _recent, calls = make_controller()
    calls.chosen_directory = "/work/projects"

    controller.show_new_project_screen()
    assert controller.state.screen is LauncherScreen.NEW_PROJECT
    assert controller.choose_new_project_location() == "/work/projects"
    assert controller.state.new_project_location == "/work/projects"

    controller.show_main_screen()
    assert controller.state.screen is LauncherScreen.MAIN


def test_project_creation_validates_and_reports_errors() -> None:
    controller, _recent, calls = make_controller()
    controller.show_new_project_screen()

    assert controller.create_new_project() is False
    assert calls.errors == ["Name and location are required"]
    assert calls.create_calls == []

    controller.set_new_project_name("  New  ")
    controller.set_new_project_location("  /projects  ")
    assert controller.create_new_project() is True
    assert calls.create_calls == [("New", "/projects")]
    assert calls.launch_calls == [calls.created_project]


def test_project_creation_service_error_is_exposed() -> None:
    _controller, _recent, calls = make_controller()

    def fail_create(_name: str, _location: str) -> str:
        raise RuntimeError("destination exists")

    services = calls.services()
    controller = LauncherController(
        FakeRecentProjects([]),
        LauncherServices(
            choose_directory=services.choose_directory,
            choose_project_file=services.choose_project_file,
            create_project=fail_create,
            launch_editor=services.launch_editor,
            report_error=services.report_error,
        ),
    )
    controller.set_new_project_name("New")
    controller.set_new_project_location("/projects")

    assert controller.create_new_project() is False
    assert controller.state.last_error == "Failed to create project: destination exists"


def test_remove_selected_project_refreshes_state() -> None:
    path = "/projects/Demo/Demo.terminproj"
    controller, recent, _calls = make_controller([{"name": "Demo", "path": path}])
    controller.select_project(path)

    assert controller.remove_selected_project() is True
    assert recent.removed == [path]
    assert controller.state.recent_projects == ()
    assert controller.state.selected_project_path is None


def test_open_existing_and_failed_launch_dispatch() -> None:
    controller, recent, calls = make_controller()
    calls.chosen_project = "/projects/Broken/Broken.terminproj"
    calls.launch_result = LaunchResult(started=False, error="editor unavailable")

    assert controller.open_existing_project() is False
    assert calls.launch_calls == [calls.chosen_project]
    assert recent.added == []
    assert controller.state.should_quit is False
    assert controller.state.last_error == "editor unavailable"


def test_successful_launch_updates_recent_and_quit_state() -> None:
    controller, recent, calls = make_controller()
    project_path = "/projects/Demo/Demo.terminproj"

    assert controller.open_project(project_path) is True
    assert recent.added == [project_path]
    assert controller.state.recent_projects[0].path == project_path
    assert controller.state.should_quit is True
