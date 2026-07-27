#!/usr/bin/env python3
"""Build and run the repository scene through the packaged D3D11 player."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from windows_d3d11_smoke_common import (
    SmokeError,
    cleanup_work_root,
    make_work_root,
    prepare_project,
    print_log_tail,
    repo_root,
    require_clean_d3d11_log,
    stop_process,
)


def _build_bundle(
    root: Path,
    project: Path,
    log_file: Path,
    timeout: float,
) -> Path:
    python = root / "sdk" / "bin" / "termin_python.exe"
    if not python.is_file():
        raise SmokeError(f"bundled SDK Python is missing: {python}")
    output_dir = project / "dist" / "WindowsD3D11Smoke"
    command = [
        str(python),
        "-m",
        "termin.project_build.profile_build",
        "desktop",
        "--project-root",
        str(project),
        "--entry-scene",
        "Main.scene",
        "--output-dir",
        str(output_dir),
        "--shader-target",
        "d3d11",
    ]
    try:
        result = subprocess.run(
            command,
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except subprocess.TimeoutExpired as error:
        output = error.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        log_file.write_text(output, encoding="utf-8")
        raise SmokeError(f"desktop bundle build timed out after {timeout:.1f}s") from error
    log_file.write_text(result.stdout or "", encoding="utf-8")
    if result.returncode != 0:
        raise SmokeError(
            f"desktop bundle build exited with code {result.returncode}: {log_file}"
        )
    app_manifest = output_dir / "app.json"
    if not app_manifest.is_file():
        raise SmokeError(f"desktop bundle did not produce app.json: {app_manifest}")
    return app_manifest


def _validate_bundle(app_manifest: Path) -> Path:
    try:
        app = json.loads(app_manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SmokeError(f"invalid player app manifest: {error}") from error
    runtime = app.get("runtime")
    if not isinstance(runtime, dict) or runtime.get("backends") != ["d3d11"]:
        raise SmokeError(f"bundle backend contract is not D3D11-only: {runtime}")
    launcher_value = runtime.get("launcher")
    if not isinstance(launcher_value, str) or not launcher_value:
        raise SmokeError("bundle app manifest has no runtime launcher")
    launcher = app_manifest.parent / Path(launcher_value)
    if not launcher.is_file():
        raise SmokeError(f"bundle-local player launcher is missing: {launcher}")
    artifacts = list((app_manifest.parent / "package" / "shaders" / "d3d11").glob("*.cso"))
    if not artifacts:
        raise SmokeError("bundle contains no compiled D3D11 shader artifacts")
    return launcher


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep-temp", action="store_true")
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()
    if os.name != "nt":
        raise SmokeError("the D3D11 player smoke requires Windows")
    if args.timeout <= 0:
        raise SmokeError("--timeout must be positive")

    root = repo_root()
    work_root = make_work_root("termin-windows-d3d11-player-")
    project = prepare_project(work_root)
    build_log = work_root / "bundle-build.log"
    player_log = work_root / "player.log"
    success = False
    process: subprocess.Popen[str] | None = None
    try:
        app_manifest = _build_bundle(root, project, build_log, args.timeout)
        launcher = _validate_bundle(app_manifest)
        environment = os.environ.copy()
        environment.update(
            {
                "TERMIN_D3D11_DEBUG": "1",
                "TERMIN_D3D11_LOG_INFO_QUEUE": "1",
            }
        )
        command = [
            str(launcher),
            "--bundle",
            str(app_manifest),
            "--backend",
            "d3d11",
            "--windowed",
            "--width",
            "640",
            "--height",
            "360",
            "--exit-after-frames",
            "30",
        ]
        with player_log.open("w", encoding="utf-8") as log_stream:
            process = subprocess.Popen(
                command,
                cwd=app_manifest.parent,
                env=environment,
                stdout=log_stream,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            try:
                return_code = process.wait(timeout=args.timeout)
            except subprocess.TimeoutExpired as error:
                raise SmokeError(
                    "player did not stop after the requested presented-frame count"
                ) from error
            if return_code != 0:
                raise SmokeError(f"player exited with code {return_code}")

        require_clean_d3d11_log(
            player_log,
            require_backend_evidence="termin_player: initialized packaged backend 'd3d11'",
        )
        log_text = player_log.read_text(encoding="utf-8", errors="replace")
        if "termin_player: attached scene rendering: 1 viewport(s)" not in log_text:
            raise SmokeError("player log lacks attached viewport evidence")
        if "RuntimePackageLoader: loaded package" not in log_text or "entities=3" not in log_text:
            raise SmokeError("player log lacks fixture scene entity evidence")
        if "termin_player: input configured for 1 viewport(s)" not in log_text:
            raise SmokeError("player log lacks a configured presentation viewport")
        if "[EngineCore] Shutdown complete" not in log_text:
            raise SmokeError("player log lacks clean engine shutdown evidence")
        success = True
        print(
            "[windows-d3d11-player-smoke] PASS: "
            "D3D11-only strict bundle, 30 presented frames, and clean shutdown",
            flush=True,
        )
        return 0
    except Exception:
        print_log_tail(build_log, lines=80)
        print_log_tail(player_log)
        raise
    finally:
        if process is not None:
            stop_process(process)
        cleanup_work_root(work_root, keep=args.keep_temp or not success)
