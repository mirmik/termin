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
        "from termin.project.creation import create_project, write_default_scene\n"
        "from pathlib import Path\n"
        "import sys\n"
        "project_file = Path(create_project('NativePlayerMcpSmoke', sys.argv[1]))\n"
        "write_default_scene(str(project_file.parent / 'secondary.scene'))\n"
        "print(project_file)\n"
    )
    result = _run(
        [str(sdk_python), "-c", code, str(temp_root)],
        cwd=temp_root,
    )
    project_file = Path(result.stdout.strip().splitlines()[-1])
    project_root = project_file.parent
    settings = project_root / "project_settings"
    settings.mkdir(exist_ok=True)
    project_settings_path = settings / "project.json"
    project_settings = json.loads(project_settings_path.read_text(encoding="utf-8"))
    project_settings["world_controller"] = {
        "module": "game",
        "type": "SmokeDirector",
    }
    project_settings_path.write_text(
        json.dumps(project_settings, indent=2),
        encoding="utf-8",
    )
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
                    "scenes": ["scene.scene", "secondary.scene"],
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

    for identity, label, entity_uuid in (
        ("scene.scene", "entry", "10000000-0000-0000-0000-000000000001"),
        ("secondary.scene", "secondary", "20000000-0000-0000-0000-000000000001"),
    ):
        scene_path = project_root / identity
        document = json.loads(scene_path.read_text(encoding="utf-8"))
        document["scene"]["entities"].append(
            {
                "uuid": entity_uuid,
                "name": f"{label.title()} Runtime Probe",
                "priority": 0,
                "visible": True,
                "enabled": True,
                "pickable": False,
                "selectable": False,
                "layer": 0,
                "flags": 0,
                "pose": {
                    "position": [0.0, 0.0, 0.0],
                    "rotation": [0.0, 0.0, 0.0, 1.0],
                },
                "scale": [1.0, 1.0, 1.0],
                "components": [
                    {
                        "type": "SmokeProbe",
                        "data": {"label": label},
                    }
                ],
            }
        )
        scene_path.write_text(json.dumps(document, indent=2), encoding="utf-8")

    (project_root / "game.pymodule").write_text(
        json.dumps(
            {
                "name": "game",
                "type": "python",
                "root": ".",
                "packages": ["Game"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    game_package = project_root / "Game"
    game_package.mkdir()
    (game_package / "__init__.py").write_text(
        '''from __future__ import annotations

import os

from tcbase import log
from termin.engine import WorldController, require_world_context
from termin.inspect import InspectField
from termin.scene import PythonComponent


def _event(name: str) -> None:
    message = f"[WorldControllerSmoke] {name}"
    log.info(message)
    path = os.environ.get("TERMIN_WORLD_CONTROLLER_SMOKE_EVENTS")
    if path:
        with open(path, "a", encoding="utf-8") as stream:
            stream.write(name + "\\n")


class SmokeDirector(WorldController):
    def __init__(self) -> None:
        self.context = None
        self.started = False
        _event("controller:create")

    def start(self, context) -> None:
        self.context = context
        self.started = True
        _event("controller:start")

    def stop(self, context) -> None:
        assert context == self.context
        _event("controller:stop")
        self.started = False
        self.context = None

    def rotate(self, scene) -> bool:
        assert self.started and self.context is not None
        return self.context.request_primary_scene(scene)

    def __del__(self) -> None:
        _event("controller:destroy")


class SmokeProbe(PythonComponent):
    inspect_fields = {
        "label": InspectField(path="label", label="Label", kind="string"),
    }

    def __init__(self) -> None:
        super().__init__()
        self.label = ""
        self.started = False
        self.updates = 0

    def start(self) -> None:
        context = require_world_context(self.scene, f"SmokeProbe[{self.label}]")
        controller = context.controller
        if controller is not None:
            assert controller.started
        self.started = True
        _event(f"probe:{self.label}:start")

    def update(self, dt: float) -> None:
        self.updates += 1

    def on_scene_active(self) -> None:
        _event(f"probe:{self.label}:active")

    def on_scene_inactive(self) -> None:
        _event(f"probe:{self.label}:inactive")

    def on_destroy(self) -> None:
        _event(f"probe:{self.label}:destroy")
''',
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
    expected_controller = {"module": "game", "type": "SmokeDirector"}
    if manifest["runtime"]["world_controller"] != expected_controller:
        raise SmokeError("app manifest did not preserve the selected WorldController")
    if package_manifest["world_controller"] != expected_controller:
        raise SmokeError("package manifest did not preserve the selected WorldController")
    if package_manifest["entry_scene"] != "scene.scene":
        raise SmokeError("package manifest changed the entry scene identity")
    packaged_scenes = {item["identity"] for item in package_manifest["scenes"]}
    if packaged_scenes != {"scene.scene", "secondary.scene"}:
        raise SmokeError(f"unexpected packaged scene table: {sorted(packaged_scenes)!r}")
    module_manifest_path = manifest_path.parent / manifest["runtime"]["modules"]["manifest"]
    module_manifest = json.loads(module_manifest_path.read_text(encoding="utf-8"))
    module_names = {item["name"] for item in module_manifest["modules"]}
    if "game" not in module_names:
        raise SmokeError("selected WorldController owner module was not auto-packaged")
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


def _player_command(
    launcher: Path,
    *,
    mcp: bool,
    exit_after_frames: int | None = None,
) -> list[str]:
    command = [str(launcher), "--backend", "opengl", "--windowed"]
    if mcp:
        command.append("--mcp")
    if exit_after_frames is not None:
        command.append(f"--exit-after-frames={exit_after_frames}")
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


def _rewrite_world_controller(
    app_manifest_path: Path,
    selection: dict[str, str] | None,
) -> None:
    app_manifest = json.loads(app_manifest_path.read_text(encoding="utf-8"))
    app_manifest["runtime"]["world_controller"] = selection
    app_manifest_path.write_text(json.dumps(app_manifest, indent=2), encoding="utf-8")

    package_manifest_path = app_manifest_path.parent / app_manifest["package"]["manifest"]
    package_manifest = json.loads(package_manifest_path.read_text(encoding="utf-8"))
    package_manifest["world_controller"] = selection
    package_manifest_path.write_text(
        json.dumps(package_manifest, indent=2),
        encoding="utf-8",
    )


def _player_environment(
    *,
    event_path: Path,
    session_file: Path | None = None,
) -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("LD_LIBRARY_PATH", None)
    environment["TERMIN_WORLD_CONTROLLER_SMOKE_EVENTS"] = str(event_path)
    if session_file is not None:
        environment["TERMIN_PLAYER_MCP_SESSION_FILE"] = str(session_file)
        environment["TERMIN_PLAYER_MCP_PORT"] = "0"
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        environment["LP_NUM_THREADS"] = "2"
    return environment


def _run_non_mcp_case(
    launcher: Path,
    *,
    bundle_root: Path,
    event_path: Path,
    expected_exit_code: int,
) -> str:
    result = run_managed_process(
        _player_command(launcher, mcp=False, exit_after_frames=2),
        cwd=bundle_root,
        env=_player_environment(event_path=event_path),
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if result.returncode != expected_exit_code:
        raise SmokeError(
            f"player exited with {result.returncode}, expected {expected_exit_code}\n"
            f"Player log tail:\n{result.stdout[-12000:]}"
        )
    return result.stdout


def _assert_log_order(log_text: str, *fragments: str) -> None:
    cursor = -1
    for fragment in fragments:
        position = log_text.find(fragment, cursor + 1)
        if position < 0:
            raise SmokeError(f"player log is missing lifecycle event: {fragment!r}")
        cursor = position


def _assert_clean_runtime_log(log_text: str) -> None:
    forbidden = (
        "RuntimeSession shutdown reported lifecycle failures",
        "project module shutdown failed",
        "Failed to prepare registered component",
        "Entity is invalid",
    )
    found = [fragment for fragment in forbidden if fragment in log_text]
    if found:
        raise SmokeError(f"player reported dirty runtime cleanup: {found!r}")


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
        built_bundle_root = manifest_path.parent
        launcher_relative = launcher.relative_to(built_bundle_root)
        manifest_relative = manifest_path.relative_to(built_bundle_root)

        selected_root = temp_root / "relocated-selected"
        shutil.copytree(built_bundle_root, selected_root)
        shutil.rmtree(project_file.parent)
        selected_launcher = selected_root / launcher_relative
        _verify_linux_launcher_linkage(selected_launcher, selected_root)

        null_root = temp_root / "relocated-null"
        invalid_root = temp_root / "relocated-invalid"
        shutil.copytree(selected_root, null_root)
        shutil.copytree(selected_root, invalid_root)
        _rewrite_world_controller(null_root / manifest_relative, None)
        _rewrite_world_controller(
            invalid_root / manifest_relative,
            {"module": "game", "type": "MissingSmokeDirector"},
        )

        null_events = temp_root / "null-events.txt"
        null_log = _run_non_mcp_case(
            null_root / launcher_relative,
            bundle_root=null_root,
            event_path=null_events,
            expected_exit_code=0,
        )
        if "controller:create" in null_events.read_text(encoding="utf-8"):
            raise SmokeError("null selection unexpectedly constructed a WorldController")
        _assert_clean_runtime_log(null_log)
        _assert_log_order(
            null_log,
            "[WorldControllerSmoke] probe:entry:start",
            "[WorldControllerSmoke] probe:entry:destroy",
            "termin_player: module game unloaded",
        )

        invalid_events = temp_root / "invalid-events.txt"
        invalid_log = _run_non_mcp_case(
            invalid_root / launcher_relative,
            bundle_root=invalid_root,
            event_path=invalid_events,
            expected_exit_code=1,
        )
        expected_invalid = (
            "failed to create selected WorldController 'MissingSmokeDirector' "
            "from module 'game'"
        )
        if expected_invalid not in invalid_log:
            raise SmokeError(
                "invalid exact WorldController selection did not produce an actionable fatal error"
            )
        if invalid_events.exists() and "probe:entry:start" in invalid_events.read_text(encoding="utf-8"):
            raise SmokeError("invalid WorldController selection fell back to a running null session")

        session_file = temp_root / "player-mcp-session.json"
        screenshot = temp_root / "player.png"
        log_path = temp_root / "player.log"
        selected_events = temp_root / "selected-events.txt"
        environment = _player_environment(
            event_path=selected_events,
            session_file=session_file,
        )

        with log_path.open("w", encoding="utf-8") as log:
            managed = ManagedProcess.start(
                _player_command(selected_launcher, mcp=True),
                cwd=selected_root,
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
                            "from termin.display import _viewport_get_input_manager\n"
                            "from termin.engine import require_world_context\n"
                            "from termin.engine import scene as engine_scene\n"
                            "entry_scene = scene\n"
                            "entry_probe = scene.get_components_of_type('SmokeProbe')[0]\n"
                            "director = require_world_context(scene, 'packaged smoke').controller\n"
                            "secondary_key = engine_scene.SceneKey('secondary.scene', engine_scene.SceneRole.RUNTIME)\n"
                            "secondary_scene = runtime._engine.scene_manager.get_scene(secondary_key)\n"
                            "print(scene_name)\n"
                            "print(entry_probe.label)\n"
                            "print(entry_probe.started)\n"
                            "print(entry_probe.updates > 0)\n"
                            "print(director.started)\n"
                            "print(runtime.rendering_manager.topology.is_attached(entry_scene))\n"
                            "print(not runtime.rendering_manager.topology.is_attached(secondary_scene))\n"
                            "print(_viewport_get_input_manager(*viewport._viewport_handle()) != 0)\n"
                            "print(director.rotate(secondary_scene))"
                        )
                    },
                )
                context_lines = context["output"].splitlines()
                if context_lines != [
                    "scene.scene",
                    "entry",
                    "True",
                    "True",
                    "True",
                    "True",
                    "True",
                    "True",
                    "True",
                ]:
                    raise SmokeError(f"unexpected live runtime context: {context_lines!r}")

                secondary = _rpc(
                    session,
                    2,
                    "termin/execute_python",
                    {
                        "script": (
                            "secondary_probe = scene.get_components_of_type('SmokeProbe')[0]\n"
                            "print(scene_name)\n"
                            "print(secondary_probe.label)\n"
                            "print(secondary_probe.started)\n"
                            "print(secondary_probe.updates > 0)\n"
                            "print(entry_scene.get_mode() == engine_scene.SceneMode.INACTIVE)\n"
                            "print(scene.get_mode() == engine_scene.SceneMode.PLAY)\n"
                            "print(not runtime.rendering_manager.topology.is_attached(entry_scene))\n"
                            "print(runtime.rendering_manager.topology.is_attached(scene))\n"
                            "print(_viewport_get_input_manager(*viewport._viewport_handle()) != 0)\n"
                            "print(director.rotate(entry_scene))"
                        )
                    },
                )
                secondary_lines = secondary["output"].splitlines()
                if secondary_lines != [
                    "secondary.scene",
                    "secondary",
                    "True",
                    "True",
                    "True",
                    "True",
                    "True",
                    "True",
                    "True",
                    "True",
                ]:
                    raise SmokeError(
                        f"unexpected secondary scene runtime state: {secondary_lines!r}"
                    )

                returned = _rpc(
                    session,
                    3,
                    "termin/execute_python",
                    {
                        "script": (
                            "print(scene_name)\n"
                            "print(scene.equal(entry_scene))\n"
                            "print(scene.get_components_of_type('SmokeProbe')[0] is entry_probe)\n"
                            "print(scene.get_mode() == engine_scene.SceneMode.PLAY)\n"
                            "print(secondary_scene.get_mode() == engine_scene.SceneMode.INACTIVE)\n"
                            "print(runtime.rendering_manager.topology.is_attached(scene))\n"
                            "print(not runtime.rendering_manager.topology.is_attached(secondary_scene))\n"
                            "print(_viewport_get_input_manager(*viewport._viewport_handle()) != 0)"
                        )
                    },
                )
                returned_lines = returned["output"].splitlines()
                if returned_lines != [
                    "scene.scene",
                    "True",
                    "True",
                    "True",
                    "True",
                    "True",
                    "True",
                    "True",
                ]:
                    raise SmokeError(
                        f"unexpected retained entry scene runtime state: {returned_lines!r}"
                    )

                captured = _rpc(
                    session,
                    4,
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
                    5,
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

        selected_log = log_path.read_text(encoding="utf-8", errors="replace")
        _assert_clean_runtime_log(selected_log)
        _assert_log_order(
            selected_log,
            "[WorldControllerSmoke] controller:create",
            "[WorldControllerSmoke] controller:start",
            "[WorldControllerSmoke] probe:entry:start",
        )
        _assert_log_order(
            selected_log,
            "[WorldControllerSmoke] controller:stop",
            "[WorldControllerSmoke] controller:destroy",
            "[WorldControllerSmoke] probe:entry:destroy",
            "[WorldControllerSmoke] probe:secondary:destroy",
            "termin_player: module game unloaded",
        )

        print(
            "[native-player-mcp-smoke] PASS "
            f"null/exact-failure/selected lifecycle; retained scene round-trip; "
            f"PNG={screenshot.stat().st_size} bytes; cleanup clean"
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SmokeError as exc:
        print(f"[native-player-mcp-smoke] FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
