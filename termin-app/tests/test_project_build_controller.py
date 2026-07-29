from pathlib import Path
from types import SimpleNamespace

import pytest

import termin.project_build as project_build
from termin.editor_core import project_build_controller as controller_module
from termin.editor_core.build_profiles_model import BuildProfileAction
from termin.editor_core.project_build_controller import ProjectBuildController
from termin.project_build import (
    AndroidTarget,
    BuildProfile,
    DesktopTarget,
    ProfileContent,
    ProfileDiagnostic,
    ToolchainContext,
)


def _profile(tmp_path: Path, target="desktop") -> BuildProfile:
    root = tmp_path / "Project"
    scene = root / "Scenes" / "Main.scene"
    scene.parent.mkdir(parents=True)
    scene.write_text("{}", encoding="utf-8")
    (root / "Project.terminproj").write_text(
        '{"name": "Project"}\n',
        encoding="utf-8",
    )
    typed_target = (
        DesktopTarget("linux", "x86_64", ("vulkan",)) if target == "desktop" else AndroidTarget("arm64-v8a", 29)
    )
    return BuildProfile(
        target,
        root,
        typed_target,
        "dev" if target == "desktop" else "debug",
        ProfileContent(
            entry_scene=Path("Scenes/Main.scene"),
            scenes=(Path("Scenes/Main.scene"),),
            modules=(),
            python_requirements=(),
            resource_policy="strict",
            resource_includes=(),
        ),
    )


def _controller(
    logs: list[str],
    saves: list[bool],
    toolchain_settings=None,
) -> ProjectBuildController:
    return ProjectBuildController(
        save_scene=lambda: saves.append(True),
        on_output=logs.append,
        toolchain_settings=toolchain_settings or ToolchainContext,
    )


def _report(context: ToolchainContext, diagnostics=()):
    return SimpleNamespace(context=context, diagnostics=tuple(diagnostics))


def test_dry_run_uses_normalized_profile_request_without_building(monkeypatch, tmp_path) -> None:
    profile = _profile(tmp_path)
    logs: list[str] = []
    saves: list[bool] = []
    monkeypatch.setattr(
        controller_module,
        "inspect_profile_capabilities",
        lambda _profile, **_kwargs: _report(ToolchainContext()),
    )
    monkeypatch.setattr(
        project_build,
        "build_profile_result",
        lambda *_args, **_kwargs: pytest.fail("dry run executed a build"),
    )

    _controller(logs, saves).execute(BuildProfileAction.DRY_RUN, profile)

    assert saves == []
    assert any(line == "Target: desktop" for line in logs)
    expected_scene = (profile.project_root / "Scenes" / "Main.scene").as_posix()
    assert f"Entry scene: {expected_scene}" in logs
    assert logs[-1] == "Dry run complete; build execution skipped."


def test_build_selected_profile_uses_canonical_result_api(monkeypatch, tmp_path) -> None:
    profile = _profile(tmp_path)
    logs: list[str] = []
    saves: list[bool] = []
    result = SimpleNamespace(
        dist_dir=profile.project_root / "dist",
        runtime_result=SimpleNamespace(launcher_path=profile.project_root / "game"),
        diagnostics=[],
    )
    calls = []
    monkeypatch.setattr(
        project_build,
        "build_profile_result",
        lambda selected, **kwargs: calls.append((selected, kwargs)) or result,
    )

    _controller(logs, saves).execute(BuildProfileAction.BUILD, profile)

    assert saves == [True]
    assert calls[0][0] == profile
    calls[0][1]["log_callback"]("streamed output")
    assert "streamed output" in logs
    assert f"Build complete: {result.dist_dir}" in logs


def test_run_selected_desktop_profile_builds_then_launches(monkeypatch, tmp_path) -> None:
    profile = _profile(tmp_path)
    launcher = profile.project_root / "dist" / "game"
    launcher.parent.mkdir()
    launcher.write_text("#!/bin/sh\n", encoding="utf-8")
    result = SimpleNamespace(
        dist_dir=launcher.parent,
        runtime_result=SimpleNamespace(launcher_path=launcher),
        diagnostics=[],
    )
    monkeypatch.setattr(
        project_build,
        "build_profile_result",
        lambda *_args, **_kwargs: result,
    )
    popen_calls = []
    monkeypatch.setattr(
        controller_module.subprocess,
        "Popen",
        lambda command, cwd: popen_calls.append((command, cwd)),
    )

    _controller([], []).execute(BuildProfileAction.RUN, profile)

    assert popen_calls == [([str(launcher)], str(launcher.parent))]


def test_mobile_install_and_launch_use_selected_profile_request(monkeypatch, tmp_path) -> None:
    profile = _profile(tmp_path, "android")
    adb = tmp_path / "adb"
    adb.write_text("", encoding="utf-8")
    context = ToolchainContext(adb=adb)
    monkeypatch.setattr(
        controller_module,
        "inspect_profile_capabilities",
        lambda _profile, **_kwargs: _report(context),
    )
    request = project_build.compile_profile_build_request(profile, context)
    apk = request.context.dist_dir / "apk" / f"{request.context.project_name}-debug.apk"
    apk.parent.mkdir(parents=True)
    apk.write_text("apk", encoding="utf-8")
    install_calls = []
    launch_calls = []
    monkeypatch.setattr(
        project_build,
        "install_android_apk",
        lambda *args, **kwargs: install_calls.append((args, kwargs)),
    )
    monkeypatch.setattr(
        project_build,
        "launch_android_app",
        lambda *args, **kwargs: launch_calls.append((args, kwargs)),
    )
    controller = _controller([], [])

    controller.execute(BuildProfileAction.INSTALL, profile)
    controller.execute(BuildProfileAction.LAUNCH, profile)

    assert install_calls[0][0] == (apk,)
    assert install_calls[0][1]["adb"] == adb
    assert launch_calls[0][0][0] == "org.termin.builds.project"
    assert launch_calls[0][1]["adb"] == adb


def test_install_capability_requires_adb_and_exact_profile_apk(monkeypatch, tmp_path) -> None:
    profile = _profile(tmp_path, "android")
    monkeypatch.setattr(
        controller_module,
        "inspect_profile_capabilities",
        lambda _profile, **_kwargs: _report(ToolchainContext()),
    )

    diagnostics = _controller([], []).capability_diagnostics(
        BuildProfileAction.INSTALL,
        profile,
    )

    assert {diagnostic.code for diagnostic in diagnostics} == {
        "capability.adb",
        "capability.apk",
    }


def test_build_capability_forwards_structured_toolchain_diagnostics(monkeypatch, tmp_path) -> None:
    profile = _profile(tmp_path)
    expected = ProfileDiagnostic("capability.sdk", "toolchain.sdk", "missing")
    monkeypatch.setattr(
        controller_module,
        "inspect_profile_capabilities",
        lambda _profile, **_kwargs: _report(ToolchainContext(), (expected,)),
    )

    diagnostics = _controller([], []).capability_diagnostics(
        BuildProfileAction.BUILD,
        profile,
    )

    assert diagnostics == (expected,)


def test_editor_toolchain_settings_reach_capabilities_and_build(monkeypatch, tmp_path) -> None:
    profile = _profile(tmp_path)
    configured = ToolchainContext(
        sdk_root=tmp_path / "sdk",
        gradle=tmp_path / "gradle-8" / "bin" / "gradle",
    )
    inspected = []
    monkeypatch.setattr(
        controller_module,
        "inspect_profile_capabilities",
        lambda selected, **kwargs: inspected.append((selected, kwargs)) or _report(configured),
    )
    result = SimpleNamespace(
        dist_dir=profile.project_root / "dist",
        runtime_result=SimpleNamespace(launcher_path=profile.project_root / "game"),
        diagnostics=[],
    )
    built = []
    monkeypatch.setattr(
        project_build,
        "build_profile_result",
        lambda selected, **kwargs: built.append((selected, kwargs)) or result,
    )
    controller = _controller([], [], lambda: configured)

    assert controller.capability_diagnostics(BuildProfileAction.BUILD, profile) == ()
    controller.execute(BuildProfileAction.BUILD, profile)

    assert inspected == [(profile, {"user_settings": configured})]
    assert built[0][0] == profile
    assert built[0][1]["user_settings"] == configured
