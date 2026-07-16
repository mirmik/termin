"""Toolkit-neutral state and actions for the Termin project launcher."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import os
from typing import Callable, Protocol


class LauncherScreen(str, Enum):
    MAIN = "main"
    NEW_PROJECT = "new_project"


@dataclass(frozen=True)
class RecentProject:
    name: str
    path: str


@dataclass(frozen=True)
class LaunchResult:
    """Outcome returned by the platform-specific editor launcher."""

    started: bool
    should_quit: bool = False
    error: str | None = None


class RecentProjectStore(Protocol):
    def list(self) -> list[dict]: ...

    def add(self, project_path: str) -> None: ...

    def remove(self, project_path: str) -> None: ...


@dataclass(frozen=True)
class LauncherServices:
    choose_directory: Callable[[], str]
    choose_project_file: Callable[[], str]
    create_project: Callable[[str, str], str]
    launch_editor: Callable[[str], LaunchResult]
    report_error: Callable[[str], None]


@dataclass
class LauncherState:
    screen: LauncherScreen = LauncherScreen.MAIN
    recent_projects: tuple[RecentProject, ...] = ()
    selected_project_path: str | None = None
    new_project_name: str = ""
    new_project_location: str = field(default_factory=lambda: os.path.expanduser("~/projects"))
    should_quit: bool = False
    last_error: str | None = None

    @property
    def can_open_selected(self) -> bool:
        return self.selected_project_path is not None


class LauncherController:
    """Own launcher behavior independently of any widget toolkit."""

    def __init__(self, recent: RecentProjectStore, services: LauncherServices) -> None:
        self._recent = recent
        self._services = services
        self.state = LauncherState()
        self.refresh_recent_projects()

    def refresh_recent_projects(self) -> None:
        projects: list[RecentProject] = []
        for entry in self._recent.list()[:10]:
            path = entry.get("path")
            if not isinstance(path, str) or not path:
                self._report_error("Recent project entry has no valid path")
                continue
            name = entry.get("name")
            projects.append(
                RecentProject(
                    name=name if isinstance(name, str) and name else "???",
                    path=path,
                )
            )
        self.state.recent_projects = tuple(projects)
        available_paths = {project.path for project in projects}
        if self.state.selected_project_path not in available_paths:
            self.state.selected_project_path = None

    def show_main_screen(self) -> None:
        self.state.screen = LauncherScreen.MAIN
        self.state.last_error = None
        self.refresh_recent_projects()

    def show_new_project_screen(self) -> None:
        self.state.screen = LauncherScreen.NEW_PROJECT
        self.state.last_error = None

    def select_project(self, project_path: str | None) -> None:
        available_paths = {project.path for project in self.state.recent_projects}
        self.state.selected_project_path = project_path if project_path in available_paths else None

    def set_new_project_name(self, name: str) -> None:
        self.state.new_project_name = name

    def set_new_project_location(self, location: str) -> None:
        self.state.new_project_location = location

    def choose_new_project_location(self) -> str | None:
        try:
            chosen = self._services.choose_directory()
        except Exception as exc:
            self._report_error(f"Failed to choose project location: {exc}")
            return None
        if not chosen:
            return None
        self.state.new_project_location = chosen
        return chosen

    def open_existing_project(self) -> bool:
        try:
            project_path = self._services.choose_project_file()
        except Exception as exc:
            self._report_error(f"Failed to choose project file: {exc}")
            return False
        if not project_path:
            return False
        return self.open_project(project_path)

    def open_selected_project(self) -> bool:
        project_path = self.state.selected_project_path
        if project_path is None:
            return False
        return self.open_project(project_path)

    def remove_selected_project(self) -> bool:
        project_path = self.state.selected_project_path
        if project_path is None:
            return False
        try:
            self._recent.remove(project_path)
        except Exception as exc:
            self._report_error(f"Failed to remove recent project: {exc}")
            return False
        self.state.selected_project_path = None
        self.refresh_recent_projects()
        return True

    def create_new_project(self) -> bool:
        name = self.state.new_project_name.strip()
        location = self.state.new_project_location.strip()
        if not name or not location:
            self._report_error("Name and location are required")
            return False
        try:
            project_path = self._services.create_project(name, location)
        except Exception as exc:
            self._report_error(f"Failed to create project: {exc}")
            return False
        return self.open_project(project_path)

    def open_project(self, project_path: str) -> bool:
        self.state.last_error = None
        try:
            result = self._services.launch_editor(project_path)
        except Exception as exc:
            self._report_error(f"Failed to launch editor: {exc}")
            return False
        if not result.started:
            self._report_error(result.error or "Failed to launch editor")
            return False
        try:
            self._recent.add(project_path)
        except Exception as exc:
            self._report_error(f"Editor started, but the recent project list could not be updated: {exc}")
        self.refresh_recent_projects()
        self.state.should_quit = result.should_quit
        return True

    def _report_error(self, message: str) -> None:
        self.state.last_error = message
        self._services.report_error(message)
