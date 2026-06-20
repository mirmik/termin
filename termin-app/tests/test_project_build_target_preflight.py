import shutil
from pathlib import Path

import pytest

from termin.project_build.build_context import create_build_context
from termin.project_build.diagnostics import BuildDiagnostic
from termin.project_build.target_preflight import (
    TargetPreflightError,
    preflight_desktop_build,
    preflight_project_build_context,
    preflight_android_build,
    preflight_quest_openxr_build,
)


def _write_android_root(tmp_path: Path) -> Path:
    termin_root = tmp_path / "termin-root"
    termin_root.mkdir()
    build_script = termin_root / "build-android-apk.sh"
    build_script.write_text("#!/bin/sh\n", encoding="utf-8")
    build_script.chmod(0o755)
    _write_android_sdk(termin_root)
    return termin_root


def _write_quest_root(tmp_path: Path) -> Path:
    termin_root = tmp_path / "termin-root"
    termin_root.mkdir()
    build_script = termin_root / "build-quest-openxr-apk.sh"
    build_script.write_text("#!/bin/sh\n", encoding="utf-8")
    build_script.chmod(0o755)
    return termin_root


def _write_android_sdk(termin_root: Path, abi: str = "arm64-v8a") -> Path:
    sdk_lib_dir = termin_root / "sdk" / "android" / abi / "lib"
    sdk_lib_dir.mkdir(parents=True)
    return termin_root / "sdk" / "android"


def _write_openxr_sdk(termin_root: Path, abi: str = "arm64-v8a") -> Path:
    sdk_config = (
        termin_root
        / "sdk"
        / "android"
        / abi
        / "lib"
        / "cmake"
        / "termin_openxr"
        / "termin_openxrConfig.cmake"
    )
    sdk_config.parent.mkdir(parents=True)
    sdk_config.write_text("# fake OpenXR CMake package\n", encoding="utf-8")
    return termin_root / "sdk" / "android"


def _write_desktop_sdk(tmp_path: Path) -> Path:
    sdk_root = tmp_path / "desktop-sdk"
    bin_dir = sdk_root / "bin"
    lib_dir = sdk_root / "lib"
    python_home = lib_dir / "python3.10"
    bin_dir.mkdir(parents=True)
    lib_dir.mkdir(parents=True)
    player = bin_dir / "termin_player"
    player.write_text("#!/bin/sh\n", encoding="utf-8")
    player.chmod(0o755)
    (lib_dir / "libtermin_base.so").write_bytes(b"termin")
    python_home.mkdir()
    (python_home / "os.py").write_text("", encoding="utf-8")
    return sdk_root


def _write_fake_gradle(tmp_path: Path) -> Path:
    gradle = tmp_path / "fake-gradle"
    gradle.write_text("# fake gradle\n", encoding="utf-8")
    gradle.chmod(0o755)
    return gradle


def _assert_single_error(exc: TargetPreflightError, path_part: str, message_part: str) -> None:
    assert len(exc.diagnostics) == 1
    diagnostic = exc.diagnostics[0]
    assert isinstance(diagnostic, BuildDiagnostic)
    assert diagnostic.level == "error"
    assert path_part.replace("\\", "/") in diagnostic.path.replace("\\", "/")
    assert message_part in diagnostic.message


def _preflight_project_context(
    project_root: Path,
    entry_scene: str | Path,
    output_dir: Path,
    target_name: str,
):
    context = create_build_context(
        project_root=project_root,
        entry_scene=entry_scene,
        target=target_name.lower().replace("/", "_"),
        output_dir=output_dir,
    )
    return preflight_project_build_context(context, target_name=target_name)


def test_preflight_project_context_accepts_project_dist_output(tmp_path: Path) -> None:
    project = tmp_path / "Game"
    project.mkdir()
    scene = project / "Main.scene"
    scene.write_text("{}", encoding="utf-8")

    result = _preflight_project_context(
        project,
        "Main.scene",
        project / "dist" / "android" / "Game",
        "Android",
    )

    assert result.project_root == project.resolve()
    assert result.entry_scene == scene.resolve()
    assert result.output_dir == (project / "dist" / "android" / "Game").resolve()
    assert result.diagnostics == []


def test_preflight_project_context_accepts_empty_external_output(tmp_path: Path) -> None:
    project = tmp_path / "Game"
    project.mkdir()
    (project / "Main.scene").write_text("{}", encoding="utf-8")
    output_dir = tmp_path / "external-output"
    output_dir.mkdir()

    result = _preflight_project_context(
        project,
        "Main.scene",
        output_dir,
        "Desktop",
    )

    assert result.output_dir == output_dir.resolve()
    assert result.diagnostics == []


def test_preflight_project_context_reports_missing_entry_scene(tmp_path: Path) -> None:
    project = tmp_path / "Game"
    project.mkdir()

    with pytest.raises(TargetPreflightError) as exc_info:
        _preflight_project_context(
            project,
            "Missing.scene",
            project / "dist" / "android" / "Game",
            "Android",
        )

    _assert_single_error(exc_info.value, "Missing.scene", "Entry scene does not exist")


def test_preflight_project_context_reports_entry_scene_escape(tmp_path: Path) -> None:
    project = tmp_path / "Game"
    project.mkdir()
    outside_scene = tmp_path / "Outside.scene"
    outside_scene.write_text("{}", encoding="utf-8")

    with pytest.raises(TargetPreflightError) as exc_info:
        _preflight_project_context(
            project,
            outside_scene,
            project / "dist" / "android" / "Game",
            "Android",
        )

    _assert_single_error(exc_info.value, "Outside.scene", "Entry scene must stay inside project root")


def test_preflight_project_context_reports_project_root_output(tmp_path: Path) -> None:
    project = tmp_path / "Game"
    project.mkdir()
    (project / "Main.scene").write_text("{}", encoding="utf-8")

    with pytest.raises(TargetPreflightError) as exc_info:
        _preflight_project_context(
            project,
            "Main.scene",
            project,
            "Android",
        )

    _assert_single_error(exc_info.value, str(project), "Refusing to use project root")


def test_preflight_project_context_reports_project_internal_output_outside_dist(tmp_path: Path) -> None:
    project = tmp_path / "Game"
    project.mkdir()
    (project / "Main.scene").write_text("{}", encoding="utf-8")

    with pytest.raises(TargetPreflightError) as exc_info:
        _preflight_project_context(
            project,
            "Main.scene",
            project / "BuildOutput",
            "Android",
        )

    _assert_single_error(exc_info.value, "BuildOutput", "outside dist/")


def test_preflight_project_context_reports_non_empty_external_output(tmp_path: Path) -> None:
    project = tmp_path / "Game"
    project.mkdir()
    (project / "Main.scene").write_text("{}", encoding="utf-8")
    output_dir = tmp_path / "external-output"
    output_dir.mkdir()
    (output_dir / "existing.txt").write_text("keep me\n", encoding="utf-8")

    with pytest.raises(TargetPreflightError) as exc_info:
        _preflight_project_context(
            project,
            "Main.scene",
            output_dir,
            "Desktop",
        )

    _assert_single_error(exc_info.value, "external-output", "non-empty external build output")


def test_preflight_desktop_accepts_sdk_capabilities(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("TERMIN_SDK", raising=False)
    sdk_root = _write_desktop_sdk(tmp_path)

    result = preflight_desktop_build(sdk_root=sdk_root)

    assert result.sdk_root == sdk_root.resolve()
    assert result.capabilities.desktop.player is True
    assert result.capabilities.desktop.python_runtime is True
    assert result.diagnostics == []


def test_preflight_desktop_reports_missing_python_runtime(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("TERMIN_SDK", raising=False)
    sdk_root = _write_desktop_sdk(tmp_path)
    (sdk_root / "lib" / "python3.10" / "os.py").unlink()

    with pytest.raises(TargetPreflightError) as exc_info:
        preflight_desktop_build(sdk_root=sdk_root)

    _assert_single_error(exc_info.value, "lib/python", "Bundled Python stdlib was not found")


def test_preflight_android_accepts_valid_environment(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GRADLE_BIN", raising=False)
    termin_root = _write_android_root(tmp_path)
    gradle = _write_fake_gradle(tmp_path)

    result = preflight_android_build(
        termin_root=termin_root,
        build_script=None,
        gradle=gradle,
    )

    assert result.termin_root == termin_root.resolve()
    assert result.build_script == termin_root.resolve() / "build-android-apk.sh"
    assert result.android_sdk_root == termin_root.resolve() / "sdk" / "android"
    assert result.gradle == gradle.resolve()
    assert result.capabilities.android.has_abi("arm64-v8a")
    assert result.diagnostics == []


def test_preflight_android_reports_missing_root_marker(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GRADLE_BIN", raising=False)
    termin_root = tmp_path / "termin-root"
    termin_root.mkdir()

    with pytest.raises(TargetPreflightError) as exc_info:
        preflight_android_build(
            termin_root=termin_root,
            build_script=None,
            gradle=None,
        )

    _assert_single_error(exc_info.value, "termin_root", "build-android-apk.sh")


def test_preflight_android_reports_missing_explicit_build_script(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GRADLE_BIN", raising=False)
    termin_root = _write_android_root(tmp_path)

    with pytest.raises(TargetPreflightError) as exc_info:
        preflight_android_build(
            termin_root=termin_root,
            build_script=tmp_path / "missing-build-android-apk.sh",
            gradle=None,
        )

    _assert_single_error(exc_info.value, "missing-build-android-apk.sh", "build script does not exist")


def test_preflight_android_reports_missing_explicit_gradle(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GRADLE_BIN", raising=False)
    termin_root = _write_android_root(tmp_path)

    with pytest.raises(TargetPreflightError) as exc_info:
        preflight_android_build(
            termin_root=termin_root,
            build_script=None,
            gradle=tmp_path / "missing-gradle",
        )

    _assert_single_error(exc_info.value, "missing-gradle", "Gradle executable does not exist")


def test_preflight_android_reports_missing_sdk_root(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GRADLE_BIN", raising=False)
    monkeypatch.delenv("TERMIN_ANDROID_SDK_ROOT", raising=False)
    termin_root = _write_android_root(tmp_path)
    shutil.rmtree(termin_root / "sdk" / "android")

    with pytest.raises(TargetPreflightError) as exc_info:
        preflight_android_build(
            termin_root=termin_root,
            build_script=None,
            gradle=None,
            abi="arm64-v8a",
            platform="android-26",
        )

    _assert_single_error(exc_info.value, "sdk/android", "Termin Android SDK is not installed")


def test_preflight_android_reports_missing_abi(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GRADLE_BIN", raising=False)
    monkeypatch.delenv("TERMIN_ANDROID_SDK_ROOT", raising=False)
    termin_root = _write_android_root(tmp_path)

    with pytest.raises(TargetPreflightError) as exc_info:
        preflight_android_build(
            termin_root=termin_root,
            build_script=None,
            gradle=None,
            abi="x86_64",
            platform="android-26",
        )

    _assert_single_error(exc_info.value, "x86_64", "missing the requested ABI")


def test_preflight_quest_openxr_accepts_valid_environment(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GRADLE_BIN", raising=False)
    monkeypatch.delenv("TERMIN_ANDROID_SDK_ROOT", raising=False)
    termin_root = _write_quest_root(tmp_path)
    sdk_root = _write_openxr_sdk(termin_root)
    gradle = _write_fake_gradle(tmp_path)

    result = preflight_quest_openxr_build(
        termin_root=termin_root,
        build_script=None,
        gradle=gradle,
        abi="arm64-v8a",
        platform="android-26",
    )

    assert result.termin_root == termin_root.resolve()
    assert result.build_script == termin_root.resolve() / "build-quest-openxr-apk.sh"
    assert result.android_sdk_root == sdk_root.resolve()
    assert result.gradle == gradle.resolve()
    assert result.diagnostics == []


def test_preflight_quest_openxr_reports_missing_root_marker(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GRADLE_BIN", raising=False)
    termin_root = tmp_path / "termin-root"
    termin_root.mkdir()

    with pytest.raises(TargetPreflightError) as exc_info:
        preflight_quest_openxr_build(
            termin_root=termin_root,
            build_script=None,
            gradle=None,
            abi="arm64-v8a",
            platform="android-26",
        )

    _assert_single_error(exc_info.value, "termin_root", "build-quest-openxr-apk.sh")


def test_preflight_quest_openxr_reports_missing_sdk_root(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GRADLE_BIN", raising=False)
    monkeypatch.delenv("TERMIN_ANDROID_SDK_ROOT", raising=False)
    termin_root = _write_quest_root(tmp_path)

    with pytest.raises(TargetPreflightError) as exc_info:
        preflight_quest_openxr_build(
            termin_root=termin_root,
            build_script=None,
            gradle=None,
            abi="arm64-v8a",
            platform="android-26",
        )

    _assert_single_error(exc_info.value, "sdk/android", "Termin Android SDK is not installed")


def test_preflight_quest_openxr_reports_missing_abi(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GRADLE_BIN", raising=False)
    monkeypatch.delenv("TERMIN_ANDROID_SDK_ROOT", raising=False)
    termin_root = _write_quest_root(tmp_path)
    (termin_root / "sdk" / "android").mkdir(parents=True)

    with pytest.raises(TargetPreflightError) as exc_info:
        preflight_quest_openxr_build(
            termin_root=termin_root,
            build_script=None,
            gradle=None,
            abi="arm64-v8a",
            platform="android-26",
        )

    _assert_single_error(exc_info.value, "arm64-v8a", "missing the requested ABI")


def test_preflight_quest_openxr_reports_missing_lib_dir(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GRADLE_BIN", raising=False)
    monkeypatch.delenv("TERMIN_ANDROID_SDK_ROOT", raising=False)
    termin_root = _write_quest_root(tmp_path)
    (termin_root / "sdk" / "android" / "arm64-v8a").mkdir(parents=True)

    with pytest.raises(TargetPreflightError) as exc_info:
        preflight_quest_openxr_build(
            termin_root=termin_root,
            build_script=None,
            gradle=None,
            abi="arm64-v8a",
            platform="android-26",
        )

    _assert_single_error(exc_info.value, "arm64-v8a/lib", "lib directory is missing")


def test_preflight_quest_openxr_reports_missing_openxr_config(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GRADLE_BIN", raising=False)
    monkeypatch.delenv("TERMIN_ANDROID_SDK_ROOT", raising=False)
    termin_root = _write_quest_root(tmp_path)
    (termin_root / "sdk" / "android" / "arm64-v8a" / "lib").mkdir(parents=True)

    with pytest.raises(TargetPreflightError) as exc_info:
        preflight_quest_openxr_build(
            termin_root=termin_root,
            build_script=None,
            gradle=None,
            abi="arm64-v8a",
            platform="android-26",
        )

    _assert_single_error(exc_info.value, "termin_openxrConfig.cmake", "OpenXR support is missing")


def test_preflight_quest_openxr_reports_missing_explicit_gradle(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GRADLE_BIN", raising=False)
    monkeypatch.delenv("TERMIN_ANDROID_SDK_ROOT", raising=False)
    termin_root = _write_quest_root(tmp_path)
    _write_openxr_sdk(termin_root)

    with pytest.raises(TargetPreflightError) as exc_info:
        preflight_quest_openxr_build(
            termin_root=termin_root,
            build_script=None,
            gradle=tmp_path / "missing-gradle",
            abi="arm64-v8a",
            platform="android-26",
        )

    _assert_single_error(exc_info.value, "missing-gradle", "Gradle executable does not exist")
