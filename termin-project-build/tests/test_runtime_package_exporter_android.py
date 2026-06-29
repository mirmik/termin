import os
from pathlib import Path

from termin.project_build import android_build, quest_openxr_build
from termin.project_build.runtime_package_exporter import RuntimePackageExportDiagnostic

from test_runtime_package_exporter import (
    _write_fake_shader_compiler,
    _write_json,
    full_runtime_package_exporter,
)


@full_runtime_package_exporter
def test_build_android_project_exports_package_and_copies_apk(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "AndroidGame"
    project.mkdir()
    _write_json(project / "AndroidGame.terminproj", {"version": 1, "name": "AndroidGame"})
    _write_json(project / "Main.scene", {"uuid": "root-scene", "entities": []})

    termin_root = tmp_path / "termin-root"
    apk_source = termin_root / "build" / "android-gradle" / "app" / "outputs" / "apk" / "debug" / "app-debug.apk"
    (termin_root / "sdk" / "android" / "arm64-v8a" / "lib").mkdir(parents=True)
    build_script = termin_root / ("build-android-apk.cmd" if os.name == "nt" else "build-android-apk.sh")
    marker_script = termin_root / "build-android-apk.sh"
    build_script.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        marker_script.write_text("# marker for termin root discovery\n", encoding="utf-8")
        build_script.write_text(
            "@echo off\n"
            f"mkdir \"{apk_source.parent}\" >NUL 2>NUL\n"
            f"<NUL set /p dummy=APK>\"{apk_source}\"\n"
            "echo %*\n",
            encoding="utf-8",
        )
    else:
        build_script.write_text(
            "#!/bin/sh\n"
            "set -e\n"
            f"mkdir -p '{apk_source.parent}'\n"
            f"printf APK > '{apk_source}'\n"
            "printf '%s\\n' \"$@\"\n",
            encoding="utf-8",
        )
    build_script.chmod(0o755)
    fake_gradle = tmp_path / "fake-gradle"
    fake_gradle.write_text("# fake gradle\n", encoding="utf-8")
    fake_gradle.chmod(0o755)

    validation_diagnostic = RuntimePackageExportDiagnostic(
        "warning",
        "manifest.json",
        "synthetic validator diagnostic",
    )
    validated_package_dirs: list[Path] = []

    def fake_validate_runtime_package(package_dir: Path) -> list[RuntimePackageExportDiagnostic]:
        validated_package_dirs.append(package_dir)
        return [validation_diagnostic]

    monkeypatch.setattr(android_build, "validate_runtime_package", fake_validate_runtime_package)

    result = android_build.build_android_project(
        project_root=project,
        entry_scene="Main.scene",
        termin_root=termin_root,
        build_script=build_script,
        gradle=fake_gradle,
        shader_compiler=_write_fake_shader_compiler(tmp_path),
    )

    assert result.apk_path == project / "dist" / "android" / "AndroidGame" / "apk" / "AndroidGame-debug.apk"
    assert result.apk_path.read_bytes() == b"APK"
    assert result.application_id == "org.termin.builds.androidgame"
    assert result.launch_activity == "org.termin.android.TerminActivity"
    assert result.package_result.manifest_path.exists()
    log_text = result.log_path.read_text(encoding="utf-8")
    assert "--assets-dir" in log_text
    assert str(result.package_result.package_dir) in log_text
    assert "--sdk-root" in log_text
    assert str(termin_root / "sdk" / "android") in log_text
    assert "--application-id" in log_text
    assert "org.termin.builds.androidgame" in log_text
    assert "--app-label" in log_text
    assert "AndroidGame" in log_text
    assert validated_package_dirs == [result.package_result.package_dir]
    assert validation_diagnostic in result.diagnostics


@full_runtime_package_exporter
def test_build_quest_openxr_project_exports_package_and_copies_apk(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "QuestGame"
    project.mkdir()
    _write_json(project / "QuestGame.terminproj", {"version": 1, "name": "QuestGame"})
    _write_json(project / "Main.scene", {"uuid": "root-scene", "entities": []})

    termin_root = tmp_path / "termin-root"
    apk_source = (
        termin_root
        / "build"
        / "android-gradle-openxr"
        / "app"
        / "outputs"
        / "apk"
        / "debug"
        / "app-debug.apk"
    )
    sdk_config = (
        termin_root
        / "sdk"
        / "android"
        / "arm64-v8a"
        / "lib"
        / "cmake"
        / "termin_openxr"
        / "termin_openxrConfig.cmake"
    )
    sdk_config.parent.mkdir(parents=True)
    sdk_config.write_text("# fake OpenXR CMake package\n", encoding="utf-8")

    build_script = termin_root / ("build-quest-openxr-apk.cmd" if os.name == "nt" else "build-quest-openxr-apk.sh")
    if os.name == "nt":
        build_script.write_text(
            "@echo off\n"
            f"mkdir \"{apk_source.parent}\" >NUL 2>NUL\n"
            f"<NUL set /p dummy=QUESTAPK>\"{apk_source}\"\n"
            "echo %*\n",
            encoding="utf-8",
        )
    else:
        build_script.write_text(
            "#!/bin/sh\n"
            "set -e\n"
            f"mkdir -p '{apk_source.parent}'\n"
            f"printf QUESTAPK > '{apk_source}'\n"
            "printf '%s\\n' \"$@\"\n",
            encoding="utf-8",
        )
    build_script.chmod(0o755)
    fake_gradle = tmp_path / "fake-gradle"
    fake_gradle.write_text("# fake gradle\n", encoding="utf-8")
    fake_gradle.chmod(0o755)

    validation_diagnostic = RuntimePackageExportDiagnostic(
        "warning",
        "manifest.json",
        "synthetic quest validator diagnostic",
    )
    validated_package_dirs: list[Path] = []

    def fake_validate_runtime_package(package_dir: Path) -> list[RuntimePackageExportDiagnostic]:
        validated_package_dirs.append(package_dir)
        return [validation_diagnostic]

    monkeypatch.setattr(quest_openxr_build, "validate_runtime_package", fake_validate_runtime_package)

    result = quest_openxr_build.build_quest_openxr_project(
        project_root=project,
        entry_scene="Main.scene",
        termin_root=termin_root,
        build_script=build_script,
        gradle=fake_gradle,
        shader_compiler=_write_fake_shader_compiler(tmp_path),
    )

    assert result.apk_path == project / "dist" / "quest_openxr" / "QuestGame" / "apk" / "QuestGame-quest-openxr-debug.apk"
    assert result.apk_path.read_bytes() == b"QUESTAPK"
    assert result.application_id == "org.termin.openxr"
    assert result.launch_activity == "android.app.NativeActivity"
    assert result.package_result.manifest_path.exists()
    log_text = result.log_path.read_text(encoding="utf-8")
    assert "--assets-dir" in log_text
    assert str(result.package_result.package_dir) in log_text
    assert "--sdk-root" in log_text
    assert str(termin_root / "sdk" / "android") in log_text
    assert validated_package_dirs == [result.package_result.package_dir]
    assert validation_diagnostic in result.diagnostics
