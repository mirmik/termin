import json
from pathlib import Path

import pytest

from termin.editor_core import project_session_controller as session_module
from termin.editor_core.project_session_controller import ProjectSessionController


class _Settings:
    def __init__(self, calls: list[str]) -> None:
        self._calls = calls
        self.last_project_file: Path | None = None

    def get_last_project_file(self) -> Path | None:
        return self.last_project_file

    def set_last_project_file(self, path: Path | str) -> None:
        self._calls.append("editor_settings")
        self.last_project_file = Path(path)


class _ProjectPathManager:
    def __init__(self, label: str, calls: list[str]) -> None:
        self._label = label
        self._calls = calls

    def set_project_path(self, _path: Path) -> None:
        self._calls.append(self._label)


def _write_project(path: Path, *, name: str = "Test Project") -> Path:
    path.write_text(json.dumps({"version": 1, "name": name}), encoding="utf-8")
    return path


def _controller(
    calls: list[str],
    errors: list[tuple[str, str]],
) -> ProjectSessionController:
    return ProjectSessionController(
        set_project_state=lambda _directory, _name: calls.append("project_state"),
        log_to_console=lambda message: calls.append(f"log:{message}"),
        rescan_file_resources=lambda: calls.append("resource_scan"),
        set_project_browser_root=lambda _directory: calls.append("browser_root"),
        get_init_script_editor=lambda: None,
        resolve_termin_shaderc=lambda: None,
        resolve_slangc=lambda: None,
        get_render_engine=lambda: object(),
        show_error=lambda title, message: errors.append((title, message)),
    )


@pytest.fixture
def isolated_publication(monkeypatch):
    calls: list[str] = []
    settings = _Settings(calls)

    monkeypatch.setattr(
        session_module.EditorSettings,
        "instance",
        classmethod(lambda _cls: settings),
    )
    monkeypatch.setattr(
        "termin.editor_core.project_context.set_current_project_path",
        lambda _root: calls.append("project_context"),
    )

    from termin.navmesh.settings import NavigationSettingsManager
    from termin.project.settings import ProjectSettingsManager

    project_settings = _ProjectPathManager("project_settings", calls)
    navigation_settings = _ProjectPathManager("navigation_settings", calls)
    monkeypatch.setattr(
        ProjectSettingsManager,
        "instance",
        classmethod(lambda _cls: project_settings),
    )
    monkeypatch.setattr(
        NavigationSettingsManager,
        "instance",
        classmethod(lambda _cls: navigation_settings),
    )
    return calls, settings


@pytest.mark.parametrize(
    "contents",
    [
        "not json",
        "[]",
        '{"version": 2, "name": "Wrong Version"}',
        '{"version": 1, "name": ""}',
    ],
)
def test_descriptor_validation_fails_before_publishing(
    tmp_path, monkeypatch, contents
) -> None:
    project_file = tmp_path / "Invalid.terminproj"
    project_file.write_text(contents, encoding="utf-8")
    calls: list[str] = []
    errors: list[tuple[str, str]] = []
    monkeypatch.setattr(
        session_module,
        "sync_stdlib",
        lambda _root: calls.append("sync_stdlib"),
    )
    controller = _controller(calls, errors)

    completed: list[bool] = []
    assert controller.initialize_project(str(project_file), completed.append) is False

    assert calls == [f"log:{errors[0][0]}: {errors[0][1]}"]
    assert errors[0][0] == "Project Validation Failed"
    assert completed == [False]
    assert controller.project_file is None


def test_stdlib_failure_fails_before_publishing(tmp_path, monkeypatch) -> None:
    project_file = _write_project(tmp_path / "SyncFailure.terminproj")
    calls: list[str] = []
    errors: list[tuple[str, str]] = []

    def fail_sync(_root: Path) -> None:
        calls.append("sync_stdlib")
        raise RuntimeError("copy failed")

    monkeypatch.setattr(session_module, "sync_stdlib", fail_sync)
    controller = _controller(calls, errors)

    assert controller.initialize_project(str(project_file)) is False

    assert calls[0] == "sync_stdlib"
    assert all(
        marker not in calls
        for marker in ("project_state", "browser_root", "resource_scan")
    )
    assert errors[0][0] == "Standard Library Sync Failed"
    assert controller.project_file is None


def test_initialization_order_and_init_script_after_modules(
    tmp_path, monkeypatch, isolated_publication
) -> None:
    calls, settings = isolated_publication
    errors: list[tuple[str, str]] = []
    project_file = _write_project(tmp_path / "FirstRun.terminproj", name="Manifest Name")

    monkeypatch.setattr(
        session_module,
        "sync_stdlib",
        lambda root: calls.append("sync_stdlib") if root == tmp_path else None,
    )
    monkeypatch.setattr(
        ProjectSessionController,
        "configure_shader_runtime_for_project",
        staticmethod(lambda _root, **_kwargs: calls.append("shader_runtime")),
    )
    controller = _controller(calls, errors)
    monkeypatch.setattr(
        controller,
        "load_project_modules",
        lambda _root, on_complete: (calls.append("modules"), on_complete(True)),
    )
    monkeypatch.setattr(
        controller,
        "run_project_init_script",
        lambda _root: calls.append("init_script"),
    )

    completed: list[bool] = []
    assert controller.initialize_project(str(project_file), completed.append) is True

    assert calls == [
        "sync_stdlib",
        "project_context",
        "shader_runtime",
        "project_settings",
        "navigation_settings",
        "editor_settings",
        "project_state",
        "browser_root",
        "resource_scan",
        f"log:Project: {tmp_path}",
        "modules",
        "init_script",
    ]
    assert completed == [True]
    assert errors == []
    assert controller.project_file == project_file.resolve()
    assert settings.last_project_file == project_file.resolve()


def test_repeated_initialization_is_rejected_without_mutation(
    tmp_path, monkeypatch, isolated_publication
) -> None:
    calls, _settings = isolated_publication
    errors: list[tuple[str, str]] = []
    first = _write_project(tmp_path / "First.terminproj")
    second = _write_project(tmp_path / "Second.terminproj")
    monkeypatch.setattr(session_module, "sync_stdlib", lambda _root: None)
    monkeypatch.setattr(
        ProjectSessionController,
        "configure_shader_runtime_for_project",
        staticmethod(lambda _root, **_kwargs: None),
    )
    controller = _controller(calls, errors)
    monkeypatch.setattr(
        controller,
        "load_project_modules",
        lambda _root, on_complete: on_complete(True),
    )
    monkeypatch.setattr(controller, "run_project_init_script", lambda _root: None)
    assert controller.initialize_project(str(first)) is True
    calls.clear()

    completed: list[bool] = []
    assert controller.initialize_project(str(second), completed.append) is False

    assert completed == [False]
    assert controller.project_file == first.resolve()
    assert errors[-1][0] == "Project Already Initialized"
    assert len(calls) == 1
    assert calls[0].startswith("log:Project Already Initialized:")


def test_module_failure_keeps_repairable_project_without_running_init_script(
    tmp_path, monkeypatch, isolated_publication
) -> None:
    calls, _settings = isolated_publication
    errors: list[tuple[str, str]] = []
    project_file = _write_project(tmp_path / "Degraded.terminproj")
    monkeypatch.setattr(session_module, "sync_stdlib", lambda _root: None)
    monkeypatch.setattr(
        ProjectSessionController,
        "configure_shader_runtime_for_project",
        staticmethod(lambda _root, **_kwargs: None),
    )
    controller = _controller(calls, errors)
    monkeypatch.setattr(
        controller,
        "load_project_modules",
        lambda _root, on_complete: (calls.append("modules"), on_complete(False)),
    )
    monkeypatch.setattr(
        controller,
        "run_project_init_script",
        lambda _root: calls.append("init_script"),
    )

    completed: list[bool] = []
    assert controller.initialize_project(str(project_file), completed.append) is True

    assert completed == [False]
    assert "browser_root" in calls
    assert "resource_scan" in calls
    assert "init_script" not in calls
    assert errors[-1][0] == "Project Module Load Failed"
    assert controller.project_file == project_file.resolve()
