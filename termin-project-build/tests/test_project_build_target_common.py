import os
from pathlib import Path

import pytest

from termin.project_build.target_build_common import read_log_tail, resolve_gradle, resolve_termin_root


def test_resolve_termin_root_requires_target_specific_marker(tmp_path: Path) -> None:
    termin_root = tmp_path / "termin-root"
    termin_root.mkdir()
    (termin_root / "build-android-apk.sh").write_text("# android marker\n", encoding="utf-8")

    assert resolve_termin_root(
        termin_root,
        marker_script_name="build-android-apk.sh",
        target_name="Android",
    ) == termin_root.resolve()

    with pytest.raises(FileNotFoundError, match="build-quest-openxr-apk.sh"):
        resolve_termin_root(
            termin_root,
            marker_script_name="build-quest-openxr-apk.sh",
            target_name="Quest/OpenXR",
        )


def test_resolve_termin_root_uses_environment_candidate_first(tmp_path: Path, monkeypatch) -> None:
    termin_root = tmp_path / "termin-root"
    termin_root.mkdir()
    (termin_root / "build-quest-openxr-apk.sh").write_text("# quest marker\n", encoding="utf-8")
    monkeypatch.setenv("TERMIN_ROOT", str(termin_root))

    assert resolve_termin_root(
        None,
        marker_script_name="build-quest-openxr-apk.sh",
        target_name="Quest/OpenXR",
    ) == termin_root.resolve()


def test_resolve_gradle_prefers_explicit_path_over_environment(tmp_path: Path, monkeypatch) -> None:
    explicit_gradle = tmp_path / "explicit-gradle"
    env_gradle = tmp_path / "env-gradle"
    monkeypatch.setenv("GRADLE_BIN", str(env_gradle))

    assert resolve_gradle(explicit_gradle) == explicit_gradle.resolve()


def test_resolve_gradle_reads_environment_path(tmp_path: Path, monkeypatch) -> None:
    env_gradle = tmp_path / "env-gradle"
    monkeypatch.setenv("GRADLE_BIN", str(env_gradle))

    assert resolve_gradle(None) == env_gradle.resolve()


def test_resolve_gradle_falls_back_to_path(tmp_path: Path, monkeypatch) -> None:
    path_gradle = tmp_path / ("gradle.exe" if os.name == "nt" else "gradle")
    path_gradle.write_text("#!/bin/sh\n", encoding="utf-8")
    path_gradle.chmod(0o755)
    monkeypatch.delenv("GRADLE_BIN", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path))

    assert resolve_gradle(None) == path_gradle.resolve()


def test_read_log_tail_limits_output(tmp_path: Path) -> None:
    log_path = tmp_path / "build.log"
    log_path.write_text("\n".join(f"line-{index}" for index in range(6)), encoding="utf-8")

    assert read_log_tail(log_path, max_lines=3) == "line-3\nline-4\nline-5"


def test_read_log_tail_reports_empty_log(tmp_path: Path) -> None:
    log_path = tmp_path / "build.log"
    log_path.write_text("", encoding="utf-8")

    assert read_log_tail(log_path) == "Build log is empty."
