"""Shared ADB install and launch operations for Android-family targets."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass
class AndroidDeployResult:
    command: list[str]
    log_path: Path | None
    output: str


def install_android_apk(
    apk_path: str | Path,
    adb: str | Path | None = None,
    log_path: str | Path | None = None,
    log_callback: Callable[[str], None] | None = None,
) -> AndroidDeployResult:
    apk = Path(apk_path).resolve()
    if not apk.exists():
        raise FileNotFoundError(f"Android APK does not exist: {apk}")
    adb_bin = resolve_adb(adb)
    return run_deploy_command(
        [str(adb_bin), "install", "-r", str(apk)],
        log_path,
        log_callback,
    )


def launch_android_app(
    application_id: str,
    adb: str | Path | None = None,
    log_path: str | Path | None = None,
    log_callback: Callable[[str], None] | None = None,
    *,
    wake_device: bool = False,
) -> list[AndroidDeployResult]:
    adb_bin = resolve_adb(adb)
    commands = []
    if wake_device:
        commands.append(
            [str(adb_bin), "shell", "input", "keyevent", "KEYCODE_WAKEUP"]
        )
    commands.append([str(adb_bin), "shell", "monkey", "-p", application_id, "1"])
    return [
        run_deploy_command(command, log_path, log_callback)
        for command in commands
    ]


def resolve_adb(adb: str | Path | None) -> Path:
    if adb is not None:
        adb_text = str(adb)
        adb_path = Path(adb_text).expanduser()
        if adb_path.exists():
            return adb_path.resolve()
        found_adb = shutil.which(adb_text)
        if found_adb is not None:
            return Path(found_adb).resolve()
        raise FileNotFoundError(f"adb executable does not exist: {adb_text}")

    env_adb = os.environ.get("ADB")
    if env_adb:
        adb_path = Path(env_adb).expanduser()
        if adb_path.exists():
            return adb_path.resolve()
        found_adb = shutil.which(env_adb)
        if found_adb is not None:
            return Path(found_adb).resolve()
        raise FileNotFoundError(f"ADB points to a missing executable: {env_adb}")

    found = shutil.which("adb")
    if found is None:
        raise FileNotFoundError("adb executable not found. Set ADB or add adb to PATH.")
    return Path(found).resolve()


def run_deploy_command(
    cmd: list[str],
    log_path: str | Path | None,
    log_callback: Callable[[str], None] | None,
) -> AndroidDeployResult:
    resolved_log_path: Path | None = None
    if log_path is not None:
        resolved_log_path = Path(log_path).resolve()
        resolved_log_path.parent.mkdir(parents=True, exist_ok=True)
    output, returncode = _run_logged_process_capture(
        cmd,
        resolved_log_path,
        log_callback,
    )
    if returncode != 0:
        raise RuntimeError(
            f"Android deploy command failed with exit code {returncode}: "
            f"{' '.join(cmd)}\n{output}"
        )
    return AndroidDeployResult(cmd, resolved_log_path, output)


def _run_logged_process_capture(
    cmd: list[str],
    log_path: Path | None,
    log_callback: Callable[[str], None] | None,
) -> tuple[str, int]:
    output_lines: list[str] = []
    log_file = None
    try:
        if log_path is not None:
            log_file = open(log_path, "a", encoding="utf-8")
            log_file.write("$ " + " ".join(cmd) + "\n")
            log_file.flush()
        if log_callback is not None:
            log_callback("$ " + " ".join(cmd))
        process = subprocess.Popen(
            cmd,
            text=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if process.stdout is not None:
            for line in process.stdout:
                stripped = line.rstrip("\n")
                output_lines.append(stripped)
                if log_file is not None:
                    log_file.write(line)
                    log_file.flush()
                if log_callback is not None:
                    log_callback(stripped)
        returncode = process.wait()
    finally:
        if log_file is not None:
            log_file.close()
    output = "\n".join(output_lines)
    return output + ("\n" if output else ""), returncode


__all__ = [
    "AndroidDeployResult",
    "install_android_apk",
    "launch_android_app",
    "resolve_adb",
    "run_deploy_command",
]
