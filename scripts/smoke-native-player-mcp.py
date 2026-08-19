#!/usr/bin/env python3
"""Build a starter bundle and exercise native player MCP end to end."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_TOOLS_ROOT = REPO_ROOT / "core" / "termin-build-tools"
sys.path.insert(0, str(BUILD_TOOLS_ROOT))

from termin_build.managed_process import (  # noqa: E402
    ManagedProcess,
    run_managed_process,
)


class SmokeError(RuntimeError):
    pass


FORCE_MCP_FAILURE_ENV = "TERMIN_NATIVE_PLAYER_SMOKE_FORCE_FAILURE_AFTER_MCP_READY"
PROCESS_STATE_FILE_ENV = "TERMIN_NATIVE_PLAYER_SMOKE_PROCESS_STATE_FILE"


def _repo_root() -> Path:
    return REPO_ROOT


def _record_managed_player_state(
    managed: ManagedProcess,
    temp_root: Path,
) -> None:
    raw_state_path = os.environ.get(PROCESS_STATE_FILE_ENV)
    if not raw_state_path:
        return
    state_path = Path(raw_state_path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "player_pid": managed.process.pid,
                "process_group_id": managed.process_group_id,
                "temp_root": str(temp_root),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    result = run_managed_process(
        command,
        cwd=cwd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if result.returncode != 0:
        raise SmokeError(
            f"command failed with exit code {result.returncode}: {' '.join(command)}\n"
            f"{result.stdout}"
        )
    return result


def _create_project(sdk_python: Path, temp_root: Path) -> Path:
    code = (
        "from termin.project.creation import create_project\n"
        "import sys\n"
        "print(create_project('NativePlayerMcpSmoke', sys.argv[1]))\n"
    )
    result = _run(
        [str(sdk_python), "-c", code, str(temp_root)],
        cwd=temp_root,
    )
    project_file = Path(result.stdout.strip().splitlines()[-1])
    project_root = project_file.parent
    settings = project_root / "project_settings"
    settings.mkdir(exist_ok=True)
    profiles = {
        "version": 2,
        "profiles": {
            "smoke": {
                "target": {
                    "kind": "desktop",
                    "os": "linux",
                    "arch": "x86_64",
                },
                "configuration": "dev",
                "content": {
                    "entry_scene": "scene.scene",
                    "scenes": ["scene.scene"],
                    "modules": [],
                    "python": {"requirements": []},
                    "resources": {"policy": "strict", "include": []},
                },
                "runtime": {
                    "backends": ["opengl"],
                    "python_package_policy": "minimal_strict",
                },
            }
        },
    }
    (settings / "build_profiles.json").write_text(
        json.dumps(profiles, indent=2),
        encoding="utf-8",
    )
    return project_file


def _find_bundle(project_root: Path) -> tuple[Path, Path]:
    manifests = list((project_root / "dist").glob("**/app.json"))
    if len(manifests) != 1:
        raise SmokeError(f"expected one built app.json, found {len(manifests)}")
    manifest_path = manifests[0]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    launcher_name = manifest["runtime"]["launcher"]
    launcher = manifest_path.parent / launcher_name
    if not launcher.is_file():
        raise SmokeError(f"packaged native player launcher is missing: {launcher}")
    package_manifest_path = manifest_path.parent / manifest["package"]["manifest"]
    package_manifest = json.loads(package_manifest_path.read_text(encoding="utf-8"))
    packaged_resources = {
        (item["type"], item["uuid"])
        for item in package_manifest["resources"]
    }
    required_resources = {
        ("mesh", "00000000-0000-0000-0003-000000000001"),
        ("mesh", "00000000-0000-0000-0003-000000000003"),
        ("material", "00000000-0001-0000-0001-000000000003"),
    }
    missing_resources = required_resources - packaged_resources
    if missing_resources:
        raise SmokeError(
            f"strict starter package is missing builtin resources: {sorted(missing_resources)!r}"
        )
    return launcher, manifest_path


def _verify_linux_launcher_linkage(launcher: Path, bundle_root: Path) -> None:
    readelf = shutil.which("readelf")
    ldd = shutil.which("ldd")
    if readelf is None or ldd is None:
        raise SmokeError("readelf and ldd are required for Linux bundle linkage verification")

    dynamic = _run([readelf, "-d", str(launcher)], cwd=bundle_root).stdout
    runpath_lines = [
        line for line in dynamic.splitlines() if "RPATH" in line or "RUNPATH" in line
    ]
    if len(runpath_lines) != 1:
        raise SmokeError(f"expected one launcher RUNPATH entry, found: {runpath_lines!r}")
    runpath = runpath_lines[0]
    if "$ORIGIN/lib" not in runpath:
        raise SmokeError(f"launcher RUNPATH does not resolve bundled lib/: {runpath}")
    if str(_repo_root() / "sdk" / "lib") in runpath:
        raise SmokeError(f"launcher RUNPATH leaks the build SDK path: {runpath}")

    linkage = _run([ldd, str(launcher)], cwd=bundle_root).stdout
    bundle_lib = (bundle_root / "lib").resolve()
    for line in linkage.splitlines():
        if "libtermin_" not in line and "libnanobind" not in line:
            continue
        if "=>" not in line:
            raise SmokeError(f"bundled Termin library is unresolved: {line}")
        resolved = Path(line.split("=>", 1)[1].strip().split(" ", 1)[0]).resolve()
        if not resolved.is_relative_to(bundle_lib):
            raise SmokeError(
                f"launcher resolved a Termin library outside bundle/lib: {line}"
            )


def _player_command(launcher: Path) -> list[str]:
    command = [str(launcher), "--backend", "opengl", "--windowed", "--mcp"]
    if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        return command
    xvfb_run = shutil.which("xvfb-run")
    if xvfb_run is None:
        raise SmokeError("no display is available and xvfb-run was not found")
    return [xvfb_run, "-a", *command]


def _wait_for_json(path: Path, process: subprocess.Popen[str], timeout: float) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise SmokeError(f"player exited before publishing MCP session: {process.returncode}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            time.sleep(0.05)
            continue
        if isinstance(payload, dict):
            return payload
        time.sleep(0.05)
    raise SmokeError("timed out waiting for native player MCP session")


def _rpc(session: dict, request_id: int, method: str, params: dict) -> dict:
    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }
    ).encode("utf-8")
    request = Request(
        session["url"],
        data=body,
        headers={
            "Authorization": f"Bearer {session['token']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=15.0) as response:
        payload = json.loads(response.read())
    if "error" in payload:
        raise SmokeError(f"MCP request failed: {payload['error']}")
    return payload["result"]


def _wait_for_cleanup(
    process: subprocess.Popen[str],
    session_file: Path,
    *,
    timeout: float,
) -> None:
    try:
        exit_code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise SmokeError("native player did not exit after request_quit") from exc
    if exit_code != 0:
        raise SmokeError(f"native player exited with code {exit_code}")
    deadline = time.monotonic() + 2.0
    while session_file.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    if session_file.exists():
        raise SmokeError("native player left its owned MCP session file behind")


def main() -> int:
    root = _repo_root()
    sdk = root / "sdk"
    sdk_python = sdk / "bin" / "termin_python"
    termin = sdk / "bin" / "termin"
    if not sdk_python.is_file() or not termin.is_file():
        raise SmokeError("installed SDK is missing; run 'task build'")

    with tempfile.TemporaryDirectory(prefix="termin-native-player-mcp-smoke-") as raw_temp:
        temp_root = Path(raw_temp)
        project_file = _create_project(sdk_python, temp_root)
        _run(
            [
                str(termin),
                "build",
                "smoke",
                "--project",
                str(project_file),
            ],
            cwd=root,
        )
        launcher, manifest_path = _find_bundle(project_file.parent)
        _verify_linux_launcher_linkage(launcher, manifest_path.parent)
        session_file = temp_root / "player-mcp-session.json"
        screenshot = temp_root / "player.png"
        log_path = temp_root / "player.log"
        environment = os.environ.copy()
        environment.pop("LD_LIBRARY_PATH", None)
        environment["TERMIN_PLAYER_MCP_SESSION_FILE"] = str(session_file)
        environment["TERMIN_PLAYER_MCP_PORT"] = "0"
        if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
            environment["LP_NUM_THREADS"] = "2"

        with log_path.open("w", encoding="utf-8") as log:
            managed = ManagedProcess.start(
                _player_command(launcher),
                cwd=manifest_path.parent,
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
            )
            process = managed.process
            try:
                _record_managed_player_state(managed, temp_root)
                session = _wait_for_json(session_file, process, 20.0)
                if os.environ.get(FORCE_MCP_FAILURE_ENV) == "1":
                    raise SmokeError("injected failure after MCP session publication")
                context = _rpc(
                    session,
                    1,
                    "termin/execute_python",
                    {
                        "script": (
                            "from termin.collision import CollisionWorld\n"
                            "from termin.colliders.collider_component import ColliderComponent\n"
                            "print(type(scene).__name__)\n"
                            "print(type(window).__name__)\n"
                            "print(type(display).__name__)\n"
                            "print(scene.is_alive())\n"
                            "collision_world = CollisionWorld.from_scene(scene)\n"
                            "print(collision_world is not None)\n"
                            "collider_count = collision_world.size()\n"
                            "collider_entity = scene.create_entity('NativePlayerSmokeCollider')\n"
                            "collider_entity.add_component(ColliderComponent())\n"
                            "print(collision_world.size() == collider_count + 1)"
                        )
                    },
                )
                context_lines = context["output"].splitlines()
                if context_lines != [
                    "TcScene",
                    "NativePlayerWindow",
                    "Display",
                    "True",
                    "True",
                    "True",
                ]:
                    raise SmokeError(f"unexpected live runtime context: {context_lines!r}")

                captured = _rpc(
                    session,
                    2,
                    "tools/call",
                    {
                        "name": "capture_player_screenshot",
                        "arguments": {
                            "path": str(screenshot),
                            "timeout": 10,
                        },
                    },
                )
                structured = captured["structuredContent"]
                if captured["isError"] or not structured["ok"]:
                    raise SmokeError(f"screenshot MCP call failed: {captured!r}")
                if not screenshot.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
                    raise SmokeError("player screenshot is not a PNG")
                if screenshot.stat().st_size <= 8:
                    raise SmokeError("player screenshot is empty")

                _rpc(
                    session,
                    3,
                    "termin/execute_python",
                    {"script": "request_quit(0)"},
                )
                _wait_for_cleanup(process, session_file, timeout=15.0)
            except SmokeError as exc:
                log.flush()
                log_text = log_path.read_text(encoding="utf-8", errors="replace")
                raise SmokeError(
                    f"{exc}\nPlayer log tail:\n{log_text[-12000:]}"
                ) from exc
            finally:
                managed.close()

        print(
            "[native-player-mcp-smoke] PASS "
            f"scene/window/display/collision live; PNG={screenshot.stat().st_size} bytes; "
            "request_quit/session cleanup clean"
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SmokeError as exc:
        print(f"[native-player-mcp-smoke] FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
