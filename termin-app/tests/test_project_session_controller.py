from pathlib import Path

from termin.editor_core import project_session_controller as session_module
from termin.editor_core.project_session_controller import ProjectSessionController


def test_create_project_file_uses_shared_non_destructive_creation(tmp_path, monkeypatch) -> None:
    loaded_paths: list[str] = []
    errors: list[tuple[str, str]] = []
    controller = ProjectSessionController(
        set_project_state=lambda _project_dir, _project_name: None,
        log_to_console=lambda _message: None,
        rescan_file_resources=lambda: None,
        set_project_browser_root=lambda _project_dir: None,
        get_init_script_editor=lambda: None,
        resolve_termin_shaderc=lambda: None,
        resolve_slangc=lambda: None,
        show_error=lambda title, message: errors.append((title, message)),
    )
    monkeypatch.setattr(controller, "load_project", lambda path: loaded_paths.append(path))

    target = tmp_path / "EditorProject.terminproj"
    controller.create_project_file(str(target))
    target.write_text("preserve this project", encoding="utf-8")
    controller.create_project_file(str(target))

    assert loaded_paths == [str(target)]
    assert target.read_text(encoding="utf-8") == "preserve this project"
    assert errors and errors[0][0] == "Create Project Failed"


def test_load_project_syncs_stdlib_before_modules_and_resource_scan(tmp_path, monkeypatch) -> None:
    project_file = tmp_path / "FirstRun.terminproj"
    project_file.write_text("{}", encoding="utf-8")
    calls: list[str] = []

    def sync_stdlib(project_root: Path) -> None:
        assert project_root == tmp_path
        calls.append("sync_stdlib")

    def configure_shader_runtime_for_project(project_root: Path, **_kwargs) -> None:
        assert project_root == tmp_path
        calls.append("configure_shader_runtime")

    def load_project_modules(self, project_root: Path, on_complete=None) -> None:
        assert project_root == tmp_path
        calls.append("load_project_modules")
        if on_complete is not None:
            on_complete(True)

    monkeypatch.setattr(session_module, "sync_stdlib", sync_stdlib)
    monkeypatch.setattr(
        ProjectSessionController,
        "configure_shader_runtime_for_project",
        staticmethod(configure_shader_runtime_for_project),
    )
    monkeypatch.setattr(ProjectSessionController, "load_project_modules", load_project_modules)

    controller = ProjectSessionController(
        set_project_state=lambda _project_dir, _project_name: calls.append("set_project_state"),
        log_to_console=lambda _message: calls.append("log_project"),
        rescan_file_resources=lambda: calls.append("rescan_file_resources"),
        set_project_browser_root=lambda _project_dir: calls.append("set_project_browser_root"),
        get_init_script_editor=lambda: None,
        resolve_termin_shaderc=lambda: None,
        resolve_slangc=lambda: None,
    )

    controller.load_project(str(project_file))

    assert calls == [
        "set_project_state",
        "log_project",
        "sync_stdlib",
        "configure_shader_runtime",
        "load_project_modules",
        "set_project_browser_root",
        "rescan_file_resources",
    ]
