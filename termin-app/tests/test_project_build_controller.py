import sys
from pathlib import Path
from types import SimpleNamespace

import termin.project_build as project_build
from termin.editor_tcgui import project_build_controller as project_build_module
from termin.editor_tcgui.project_build_controller import ProjectBuildController


class _SceneManager:
    def __init__(self, scene_paths: dict[str, Path]) -> None:
        self._scene_paths = scene_paths

    def get_scene_path(self, scene_name: str) -> str | None:
        scene_path = self._scene_paths.get(scene_name)
        if scene_path is None:
            return None
        return str(scene_path)


def _make_controller(
    *,
    project_root: Path,
    scene_name: str | None,
    scene_manager: _SceneManager,
    logs: list[str],
    save_calls: list[bool],
) -> ProjectBuildController:
    return ProjectBuildController(
        scene_manager=scene_manager,
        get_current_project_path=lambda: str(project_root),
        get_editor_scene_name=lambda: scene_name,
        get_ui=lambda: None,
        save_scene=lambda: save_calls.append(True),
        log_to_console=logs.append,
    )


def test_run_standalone_launches_canonical_player_entrypoint(monkeypatch, tmp_path) -> None:
    project_root = tmp_path / "Project"
    scene_path = project_root / "Scenes" / "Main.scene"
    scene_path.parent.mkdir(parents=True)
    scene_path.write_text("{}", encoding="utf-8")
    logs: list[str] = []
    save_calls: list[bool] = []
    popen_calls: list[list[str]] = []

    def fake_popen(cmd: list[str]) -> None:
        popen_calls.append(cmd)

    monkeypatch.setattr(project_build_module.subprocess, "Popen", fake_popen)
    controller = _make_controller(
        project_root=project_root,
        scene_name="Main",
        scene_manager=_SceneManager({"Main": scene_path}),
        logs=logs,
        save_calls=save_calls,
    )

    controller.run_standalone()

    assert save_calls == [True]
    assert popen_calls == [
        [
            sys.executable,
            "-m",
            "termin.player",
            str(project_root.resolve()),
            "--scene",
            "Scenes/Main.scene",
        ]
    ]
    assert logs == [
        "Launching standalone: "
        f"{sys.executable} -m termin.player {project_root.resolve()} --scene Scenes/Main.scene"
    ]


def test_run_standalone_rejects_scene_outside_project(monkeypatch, tmp_path) -> None:
    project_root = tmp_path / "Project"
    scene_path = tmp_path / "Other" / "Main.scene"
    scene_path.parent.mkdir(parents=True)
    scene_path.write_text("{}", encoding="utf-8")
    logs: list[str] = []
    save_calls: list[bool] = []
    popen_calls: list[list[str]] = []

    def fake_popen(cmd: list[str]) -> None:
        popen_calls.append(cmd)

    monkeypatch.setattr(project_build_module.subprocess, "Popen", fake_popen)
    controller = _make_controller(
        project_root=project_root,
        scene_name="Main",
        scene_manager=_SceneManager({"Main": scene_path}),
        logs=logs,
        save_calls=save_calls,
    )

    controller.run_standalone()

    assert save_calls == [True]
    assert popen_calls == []
    assert logs == ["Standalone entry scene must be inside the current project."]


def test_build_project_writes_desktop_bundle(monkeypatch, tmp_path) -> None:
    project_root = tmp_path / "Project"
    scene_path = project_root / "Scenes" / "Main.scene"
    scene_path.parent.mkdir(parents=True)
    scene_path.write_text("{}", encoding="utf-8")
    logs: list[str] = []
    save_calls: list[bool] = []
    calls: list[dict] = []

    def fake_build_desktop_project(**kwargs):
        calls.append(kwargs)
        dist_dir = kwargs["output_dir"]
        return SimpleNamespace(
            dist_dir=dist_dir,
            app_manifest_path=dist_dir / "app.json",
            package_result=SimpleNamespace(package_dir=dist_dir / "package"),
            runtime_result=SimpleNamespace(lib_dir=dist_dir / "lib", launcher_path=dist_dir / "Project"),
            diagnostics=[
                SimpleNamespace(level="warning", path="package/mesh", message="test diagnostic"),
            ],
        )

    monkeypatch.setattr(project_build, "build_desktop_project", fake_build_desktop_project)
    controller = _make_controller(
        project_root=project_root,
        scene_name="Main",
        scene_manager=_SceneManager({"Main": scene_path}),
        logs=logs,
        save_calls=save_calls,
    )

    result = controller.build_desktop_bundle_to_default_dist()

    assert result is not None
    assert save_calls == [True]
    assert calls == [
        {
            "project_root": project_root.resolve(),
            "entry_scene": Path("Scenes") / "Main.scene",
            "output_dir": project_root / "dist" / "desktop" / "Project",
        }
    ]
    assert logs == [
        f"Desktop bundle complete: {project_root / 'dist' / 'desktop' / 'Project' / 'app.json'}",
        f"Desktop package: {project_root / 'dist' / 'desktop' / 'Project' / 'package'}",
        f"Desktop runtime: {project_root / 'dist' / 'desktop' / 'Project'}",
        "Desktop diagnostics: 1 diagnostic(s)",
        "Desktop build warning: package/mesh: test diagnostic",
    ]


def test_run_build_launches_desktop_bundle_launcher(monkeypatch, tmp_path) -> None:
    project_root = tmp_path / "Project"
    scene_path = project_root / "Scenes" / "Main.scene"
    scene_path.parent.mkdir(parents=True)
    scene_path.write_text("{}", encoding="utf-8")
    launcher = project_root / "dist" / "desktop" / "Project" / "Project"
    launcher.parent.mkdir(parents=True)
    launcher.write_text("#!/bin/sh\n", encoding="utf-8")
    logs: list[str] = []
    save_calls: list[bool] = []
    popen_calls: list[tuple[list[str], str | None]] = []

    def fake_build_desktop_project(**kwargs):
        dist_dir = kwargs["output_dir"]
        return SimpleNamespace(
            dist_dir=dist_dir,
            app_manifest_path=dist_dir / "app.json",
            package_result=SimpleNamespace(package_dir=dist_dir / "package"),
            runtime_result=SimpleNamespace(lib_dir=dist_dir / "lib", launcher_path=launcher),
            diagnostics=[],
        )

    def fake_popen(cmd: list[str], cwd: str | None = None) -> None:
        popen_calls.append((cmd, cwd))

    monkeypatch.setattr(project_build, "build_desktop_project", fake_build_desktop_project)
    monkeypatch.setattr(project_build_module.subprocess, "Popen", fake_popen)
    controller = _make_controller(
        project_root=project_root,
        scene_name="Main",
        scene_manager=_SceneManager({"Main": scene_path}),
        logs=logs,
        save_calls=save_calls,
    )

    controller.run_build()

    assert save_calls == [True]
    assert popen_calls == [([str(launcher)], str(launcher.parent))]
    assert logs[-1] == f"Launching build: {launcher}"
