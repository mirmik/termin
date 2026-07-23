from pathlib import Path
from types import SimpleNamespace

import termin.project_build as project_build

from termin.editor_core.quest_openxr_build_model import QuestOpenXRBuildController

def test_quest_openxr_controller_build_install_launch_sequence(monkeypatch, tmp_path) -> None:
    events = []
    apk_path = tmp_path / "dist" / "app.apk"
    build_result = SimpleNamespace(
        apk_path=apk_path,
        application_id="com.example.quest",
        application_label="Example Quest",
        version_code=5,
        version_name="1.5",
        launch_activity="android.app.NativeActivity",
        package_result=SimpleNamespace(package_dir=tmp_path / "package"),
        log_path=tmp_path / "build.log",
        diagnostics=[SimpleNamespace(level="warning", path="asset", message="notice")],
    )
    monkeypatch.setattr(
        project_build,
        "build_quest_openxr_project",
        lambda **kwargs: (
            events.append(("build", kwargs)),
            kwargs["log_callback"]("build output"),
            build_result,
        )[-1],
    )
    monkeypatch.setattr(
        project_build,
        "install_quest_openxr_apk",
        lambda apk, **kwargs: (
            events.append(("install", Path(apk))),
            kwargs["log_callback"]("install output"),
            SimpleNamespace(log_path=tmp_path / "deploy.log"),
        )[-1],
    )
    monkeypatch.setattr(
        project_build,
        "launch_quest_openxr_app",
        lambda application_id, **kwargs: (
            events.append(("launch", application_id, kwargs["log_path"])),
            kwargs["log_callback"]("launch output"),
        ),
    )
    controller = QuestOpenXRBuildController(
        tmp_path,
        "Scenes/Main.scene",
        tmp_path / "out",
    )

    assert controller.build_install_launch()
    snapshot = controller.snapshot
    assert not snapshot.busy
    assert snapshot.status == "Launch complete"
    assert snapshot.last_apk_path == str(apk_path)
    assert [event[0] for event in events] == ["build", "install", "launch"]
    assert events[-1][1] == "com.example.quest"
    assert "build output" in snapshot.log_text
    assert "Build warning: asset: notice" in snapshot.log_text
    assert "Launch command sent." in snapshot.log_text


def test_quest_openxr_controller_reports_worker_failure(monkeypatch, tmp_path) -> None:
    def fail_build(**_kwargs):
        raise RuntimeError("compiler missing")

    monkeypatch.setattr(project_build, "build_quest_openxr_project", fail_build)
    controller = QuestOpenXRBuildController(
        tmp_path,
        "Main.scene",
    )

    assert controller.build_only()
    assert not controller.snapshot.busy
    assert controller.snapshot.status == "Build failed"
    assert "Build failed: compiler missing" in controller.snapshot.log_text
