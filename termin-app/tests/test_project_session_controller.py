from pathlib import Path

from termin.editor_tcgui import project_session_controller as session_module
from termin.editor_tcgui.project_session_controller import ProjectSessionController


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
        get_ui=lambda: None,
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
        "rescan_file_resources",
        "set_project_browser_root",
    ]
