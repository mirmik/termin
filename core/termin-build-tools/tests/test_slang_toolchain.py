from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from termin_build import slang_toolchain


def test_prepare_slang_toolchain_uses_build_python_and_repository_cache(
    tmp_path: Path, monkeypatch
) -> None:
    repo_root = tmp_path / "termin"
    repo_root.mkdir()
    build_python = tmp_path / "python"
    executable = (
        repo_root / "build" / "toolchains" / "slang-test" / "bin" / "slangc"
    )
    executable.parent.mkdir(parents=True)
    executable.write_text("", encoding="utf-8")
    captured: list[tuple[list[str], Path]] = []

    def run(command, *, cwd, text, stdout, check):
        del text, stdout, check
        captured.append((command, cwd))
        return subprocess.CompletedProcess(command, 0, stdout=f"{executable}\n")

    monkeypatch.setattr(slang_toolchain.subprocess, "run", run)

    result = slang_toolchain.prepare_slang_toolchain(repo_root, build_python)

    assert result == executable.resolve()
    command, cwd = captured[0]
    assert cwd == repo_root
    assert command == [
        str(build_python),
        str(repo_root / "scripts" / "install_slang_toolchain.py"),
        "--install-root",
        str(repo_root / "build" / "toolchains"),
        "--no-configure",
        "--print-path",
    ]


def test_prepare_slang_toolchain_forwards_post_extract_script(
    tmp_path: Path, monkeypatch
) -> None:
    repo_root = tmp_path / "termin"
    repo_root.mkdir()
    executable = repo_root / "slangc"
    executable.write_text("", encoding="utf-8")
    patch_script = repo_root / "patch-slang.py"
    patch_script.write_text("", encoding="utf-8")
    captured: list[str] = []

    def run(command, **_kwargs):
        captured.extend(command)
        return subprocess.CompletedProcess(command, 0, stdout=f"{executable}\n")

    monkeypatch.setattr(slang_toolchain.subprocess, "run", run)

    result = slang_toolchain.prepare_slang_toolchain(
        repo_root,
        tmp_path / "python",
        post_extract_script=patch_script,
    )

    assert result == executable.resolve()
    assert captured[-2:] == ["--post-extract-script", str(patch_script)]


def test_prepare_slang_toolchain_rejects_missing_installer_result(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        slang_toolchain.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 0, stdout=str(tmp_path / "missing-slangc")
        ),
    )

    with pytest.raises(
        slang_toolchain.SlangToolchainError,
        match="missing executable",
    ):
        slang_toolchain.prepare_slang_toolchain(tmp_path, tmp_path / "python")


def test_prepare_slang_toolchain_reports_installer_failure(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        slang_toolchain.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 1, stdout=""),
    )

    with pytest.raises(
        slang_toolchain.SlangToolchainError,
        match="failed to prepare",
    ):
        slang_toolchain.prepare_slang_toolchain(tmp_path, tmp_path / "python")
