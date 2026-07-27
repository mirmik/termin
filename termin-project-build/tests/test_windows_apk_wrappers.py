from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell wrapper smoke")


def _copy_wrappers(tmp_path: Path) -> Path:
    repository_root = Path(__file__).resolve().parents[2]
    termin_root = tmp_path / "termin"
    (termin_root / "build-system").mkdir(parents=True)
    for name in ("build-android-apk.ps1", "build-quest-openxr-apk.ps1"):
        shutil.copy2(repository_root / name, termin_root / name)
    shutil.copy2(
        repository_root / "build-system/android-apk-wrapper.ps1",
        termin_root / "build-system/android-apk-wrapper.ps1",
    )
    (termin_root / "termin-android/platform").mkdir(parents=True)
    (termin_root / "termin-openxr/platform").mkdir(parents=True)
    return termin_root


def _write_fake_gradle(tmp_path: Path) -> tuple[Path, Path]:
    log_path = tmp_path / "gradle-arguments.txt"
    gradle = tmp_path / "fake-gradle.cmd"
    gradle.write_text(
        "@echo off\n"
        'if "%~1"=="--version" (\n'
        "  echo Gradle 8.11\n"
        "  exit /b 0\n"
        ")\n"
        'echo %*>>"%FAKE_GRADLE_LOG%"\n',
        encoding="utf-8",
    )
    return gradle, log_path


@pytest.mark.parametrize(
    ("wrapper_name", "expected_task", "product_args"),
    [
        ("build-android-apk.ps1", "assembleDebug", ()),
        (
            "build-quest-openxr-apk.ps1",
            "assembleDebug",
            ("--application-id", "org.example.quest"),
        ),
    ],
)
def test_checked_in_windows_wrapper_reaches_gradle(
    tmp_path: Path,
    wrapper_name: str,
    expected_task: str,
    product_args: tuple[str, ...],
) -> None:
    termin_root = _copy_wrappers(tmp_path)
    gradle, log_path = _write_fake_gradle(tmp_path)
    sdk_root = termin_root / "sdk/android"
    openxr_config = (
        sdk_root
        / "arm64-v8a/lib/cmake/termin_openxr/termin_openxrConfig.cmake"
    )
    openxr_config.parent.mkdir(parents=True)
    openxr_config.write_text("# fake package\n", encoding="utf-8")
    assets_dir = tmp_path / "runtime package"
    assets_dir.mkdir()
    env = os.environ.copy()
    env["FAKE_GRADLE_LOG"] = str(log_path)

    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(termin_root / wrapper_name),
            "--assets-dir",
            str(assets_dir),
            "--sdk-root",
            str(sdk_root),
            "--abi",
            "arm64-v8a",
            "--platform",
            "android-26",
            "--gradle",
            str(gradle),
            "--variant",
            "debug",
            *product_args,
        ],
        cwd=termin_root,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    gradle_arguments = log_path.read_text(encoding="utf-8")
    assert expected_task in gradle_arguments
    assert f"-PterminAndroidSdkRoot={sdk_root}" in gradle_arguments
    assert "-PterminAndroidAbi=arm64-v8a" in gradle_arguments
    assert "-PterminAndroidPlatform=android-26" in gradle_arguments
    assert str(assets_dir) in gradle_arguments


def test_windows_release_wrapper_rejects_missing_signing_before_gradle(
    tmp_path: Path,
) -> None:
    termin_root = _copy_wrappers(tmp_path)
    gradle, log_path = _write_fake_gradle(tmp_path)
    env = os.environ.copy()
    env["FAKE_GRADLE_LOG"] = str(log_path)
    for name in (
        "TERMIN_ANDROID_SIGNING_KEYSTORE",
        "TERMIN_ANDROID_SIGNING_KEY_ALIAS",
        "TERMIN_ANDROID_SIGNING_STORE_PASSWORD",
        "TERMIN_ANDROID_SIGNING_KEY_PASSWORD",
    ):
        env.pop(name, None)

    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(termin_root / "build-android-apk.ps1"),
            "--gradle",
            str(gradle),
            "--variant",
            "release",
        ],
        cwd=termin_root,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )

    assert result.returncode != 0
    assert "release builds require signing configuration" in result.stderr
    assert not log_path.exists()
