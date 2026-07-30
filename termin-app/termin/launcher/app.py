"""Termin Launcher: native project selection and editor dispatch."""

from __future__ import annotations

import ctypes
import logging
import os
import subprocess
import sys

from termin.launcher.controller import (
    LaunchResult,
    LauncherController,
    LauncherServices,
)
from termin.launcher.recent import RecentProjects, write_launch_project
from termin.project import create_project


log = logging.getLogger(__name__)


def _find_editor_executable() -> str | None:
    """Find the termin_editor executable next to this launcher."""
    candidate_names = (
        ["termin_editor.exe", "termin_editor"]
        if os.name == "nt"
        else ["termin_editor"]
    )
    candidate_dirs: list[str] = []

    termin_sdk = os.environ.get("TERMIN_SDK")
    if termin_sdk:
        candidate_dirs.append(os.path.join(termin_sdk, "bin"))

    if os.name == "nt":
        try:
            buffer = ctypes.create_unicode_buffer(32768)
            size = ctypes.windll.kernel32.GetModuleFileNameW(
                None, buffer, len(buffer)
            )
            if size:
                candidate_dirs.append(os.path.dirname(buffer.value))
        except Exception:
            log.debug("Cannot resolve executable path via GetModuleFileNameW")
    else:
        try:
            candidate_dirs.append(os.path.dirname(os.readlink("/proc/self/exe")))
        except (OSError, AttributeError):
            log.debug("Cannot resolve /proc/self/exe")

    argv0 = sys.argv[0] if sys.argv else ""
    if argv0 and argv0 not in {"-c", ""}:
        candidate_dirs.append(os.path.dirname(os.path.abspath(argv0)))

    seen_dirs = set()
    for candidate_dir in candidate_dirs:
        if not candidate_dir:
            continue
        normalized_dir = os.path.normcase(os.path.abspath(candidate_dir))
        if normalized_dir in seen_dirs:
            continue
        seen_dirs.add(normalized_dir)
        for name in candidate_names:
            editor = os.path.join(candidate_dir, name)
            if os.path.isfile(editor):
                return editor

    import shutil

    for name in candidate_names:
        editor = shutil.which(name)
        if editor:
            return editor
    return None


def _editor_launch_env(editor_exe: str) -> dict[str, str]:
    env = os.environ.copy()
    lib_dir = os.path.normpath(
        os.path.join(os.path.dirname(editor_exe), "..", "lib")
    )
    variable = "PATH" if os.name == "nt" else "LD_LIBRARY_PATH"
    previous = env.get(variable, "")
    env[variable] = (
        f"{lib_dir}{os.pathsep}{previous}" if previous else lib_dir
    )
    return env


def _launcher_mode() -> str:
    mode = os.environ.get("TERMIN_LAUNCHER_MODE", "").strip().lower()
    if not mode:
        return "spawn" if os.name == "nt" else "exec"
    if mode not in {"exec", "spawn"}:
        log.warning(f"Unsupported TERMIN_LAUNCHER_MODE={mode!r}, using spawn")
        return "spawn"
    if mode == "exec" and os.name == "nt":
        log.warning(
            "TERMIN_LAUNCHER_MODE=exec is not supported on Windows, using spawn"
        )
        return "spawn"
    return mode


def _launch_editor_process(editor_exe: str, project_path: str) -> bool:
    """Transfer control to termin_editor."""
    env = _editor_launch_env(editor_exe)
    args = [editor_exe, project_path]
    mode = _launcher_mode()
    log.info(
        f"Launching editor: {editor_exe} for project {project_path} mode={mode}"
    )
    if mode == "exec":
        sys.stdout.flush()
        sys.stderr.flush()
        try:
            os.execvpe(editor_exe, args, env)
        except OSError as exc:
            log.error(f"Failed to exec termin_editor: {exc}")
        return False
    subprocess.Popen(args, env=env)
    return True


def _dispatch_editor(project_path: str) -> LaunchResult:
    """Platform adapter used by the toolkit-neutral launcher controller."""
    editor_exe = _find_editor_executable()
    if editor_exe is None:
        return LaunchResult(
            started=False,
            error="Cannot find termin_editor executable",
        )
    write_launch_project(project_path)
    started = _launch_editor_process(editor_exe, project_path)
    if not started:
        return LaunchResult(started=False, error="Failed to launch termin_editor")
    return LaunchResult(started=True, should_quit=True)


def _create_launcher_controller() -> LauncherController:
    return LauncherController(
        RecentProjects(),
        LauncherServices(
            create_project=create_project,
            launch_editor=_dispatch_editor,
            report_error=log.error,
        ),
    )


def _parse_launcher_args() -> str | None:
    """Parse launcher arguments and reject the retired frontend selector."""
    from termin.launcher.recent import resolve_project_path

    args = sys.argv[1:]
    if "-h" in args or "--help" in args:
        print("Usage: termin_launcher [OPTIONS] [PROJECT]")
        print()
        print("Termin project launcher.")
        print()
        print("Arguments:")
        print("  PROJECT         Path to .terminproj file or project directory")
        print()
        print("Without PROJECT, opens the launcher UI.")
        print()
        print("Options:")
        print("  -h, --help      Show this help message and exit")
        print()
        print("Environment:")
        print("  TERMIN_LAUNCHER_MODE=exec|spawn")
        print(
            "                  Linux default is exec, keeping debugger/profiler attached"
        )
        print("                  to the same process. Windows default is spawn.")
        sys.stdout.flush()
        return "__help__"

    positional: list[str] = []
    for argument in args:
        if argument.startswith("--ui"):
            print(
                "Error: the --ui option was removed; "
                "the native launcher is the only supported frontend.",
                flush=True,
            )
            return "__error__"
        if not argument.startswith("-"):
            positional.append(argument)

    if not positional:
        return None
    project = resolve_project_path(positional[0])
    if project is None:
        print(
            f"Error: cannot find .terminproj at '{positional[0]}'",
            flush=True,
        )
        return "__error__"
    return project


def run() -> None:
    """Open a project directly or run the native launcher."""
    project = _parse_launcher_args()
    if project == "__help__":
        return
    if project == "__error__":
        raise SystemExit(1)
    if project is not None:
        _create_launcher_controller().open_project(project)
        return

    from termin.launcher.native_app import run_native_launcher

    run_native_launcher(_create_launcher_controller())


if __name__ == "__main__":
    run()
