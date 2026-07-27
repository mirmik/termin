#!/usr/bin/env python3
"""Run the repository scene through the installed D3D11 editor host."""

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
    execute_script,
    make_work_root,
    parse_marked_json,
    prepare_project,
    print_log_tail,
    repo_root,
    require_clean_d3d11_log,
    require_non_empty_rgba8_png,
    rpc_call,
    stop_process,
    tool_call,
    wait_for_session,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep-temp", action="store_true")
    parser.add_argument("--timeout", type=float, default=90.0)
    args = parser.parse_args()
    if os.name != "nt":
        raise SmokeError("the D3D11 editor smoke requires Windows")
    if args.timeout <= 0:
        raise SmokeError("--timeout must be positive")

    root = repo_root()
    editor = root / "sdk" / "bin" / "termin_editor.exe"
    if not editor.is_file():
        raise SmokeError(f"installed editor is missing: {editor}")

    work_root = make_work_root("termin-windows-d3d11-editor-")
    project = prepare_project(work_root)
    session_file = work_root / "editor-session.json"
    capture_file = work_root / "editor-framegraph.png"
    screenshot_file = work_root / "editor-ui.png"
    log_file = work_root / "editor.log"
    environment = os.environ.copy()
    environment.update(
        {
            "TERMIN_SDK": str(root / "sdk"),
            "TERMIN_EDITOR_MCP": "1",
            "TERMIN_EDITOR_MCP_PORT": "0",
            "TERMIN_EDITOR_MCP_SESSION_FILE": str(session_file),
            "TERMIN_D3D11_DEBUG": "1",
            "TERMIN_D3D11_LOG_INFO_QUEUE": "1",
        }
    )
    layout_check = subprocess.run(
        [str(editor), "--termin-python-layout-smoke"],
        cwd=root,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=min(args.timeout, 30.0),
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if layout_check.returncode != 0:
        raise SmokeError(
            "installed editor Python layout check failed:\n"
            + (layout_check.stdout or "").rstrip()
        )
    if '"termin_editor"' not in (layout_check.stdout or ""):
        raise SmokeError(
            "installed editor Python layout check returned no editor payload evidence"
        )
    command = [
        str(editor),
        str(project / "WindowsD3D11Smoke.terminproj"),
        "--headless",
        "--offscreen-size",
        "640x360",
        "--offscreen-backend",
        "d3d11",
        "--frames",
        "1000000",
    ]
    success = False
    process: subprocess.Popen[str] | None = None
    try:
        with log_file.open("w", encoding="utf-8") as log_stream:
            process = subprocess.Popen(
                command,
                cwd=root,
                env=environment,
                stdout=log_stream,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            session = wait_for_session(session_file, process, args.timeout)
            rpc_call(
                session,
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "windows-d3d11-editor-smoke",
                        "version": "1",
                    },
                },
            )
            probe_output = execute_script(
                session,
                "\n".join(
                    [
                        "import json",
                        "_serialized = scene.serialize()",
                        "_cube = next(item for item in _serialized['entities'] if item['name'] == 'D3D11 Smoke Cube')",
                        "_payload = {",
                        "    'backend': editor.window.backend,",
                        "    'composition': type(editor.composition).__name__,",
                        "    'scene_name': scene.name,",
                        "    'entities': sorted(entity.name for entity in scene.entities),",
                        "    'cube_components': _cube['components'],",
                        "}",
                        "print('__TERMIN_D3D11_EDITOR__' + json.dumps(_payload))",
                        "request_render_update()",
                    ]
                ),
            )
            probe = parse_marked_json(probe_output, "__TERMIN_D3D11_EDITOR__")
            if probe.get("backend") != "d3d11":
                raise SmokeError(f"editor selected the wrong backend: {probe}")
            if probe.get("composition") != "OffscreenGuiComposition":
                raise SmokeError(f"editor selected the wrong composition: {probe}")
            expected_entities = {
                "D3D11 Smoke Cube",
                "Key Light",
                "Main Camera",
            }
            entities = set(probe.get("entities", []))
            if not expected_entities.issubset(entities):
                raise SmokeError(f"editor did not load the fixture scene: {probe}")
            components = {
                item.get("type"): item.get("data", {})
                for item in probe.get("cube_components", [])
                if isinstance(item, dict)
            }
            mesh_ref = components.get("MeshComponent", {}).get("mesh", {})
            material_ref = components.get("MeshRenderer", {}).get("material", {})
            if mesh_ref.get("type") == "none" or material_ref.get("type") == "none":
                raise SmokeError(
                    "editor fixture resource references did not resolve: "
                    f"mesh={mesh_ref}, material={material_ref}"
                )

            framegraph_text, _result = tool_call(
                session,
                "inspect_framegraph",
                {"include_pass_json": False, "timeout": 30.0},
            )
            try:
                framegraph = json.loads(framegraph_text)
            except json.JSONDecodeError as error:
                raise SmokeError("editor framegraph response is not JSON") from error
            if not framegraph.get("ok") or not framegraph.get("targets"):
                raise SmokeError(f"editor has no renderable framegraph: {framegraph}")
            if not framegraph.get("passes"):
                selected_index = framegraph.get("current_target_index")
                if selected_index is None:
                    selected_index = framegraph["targets"][0]["index"]
                framegraph_text, _result = tool_call(
                    session,
                    "inspect_framegraph",
                    {
                        "target_index": int(selected_index),
                        "include_pass_json": False,
                        "timeout": 30.0,
                    },
                )
                try:
                    framegraph = json.loads(framegraph_text)
                except json.JSONDecodeError as error:
                    raise SmokeError(
                        "selected editor framegraph response is not JSON"
                    ) from error
            pass_names = {
                item.get("name")
                for item in framegraph.get("passes", [])
                if isinstance(item, dict)
            }
            if not {"Color", "Present"}.issubset(pass_names):
                raise SmokeError(f"editor framegraph lacks scene presentation: {pass_names}")
            print(
                "[windows-d3d11-editor-smoke] framegraph "
                f"target={framegraph.get('current_target_label')} "
                f"resources={framegraph.get('resources')} "
                f"stats={framegraph.get('render_stats')}",
                flush=True,
            )
            resources = set(framegraph.get("resources", []))
            capture_resource = next(
                (
                    resource
                    for resource in ("color_scene", "color_opaque", "color", "OUTPUT")
                    if resource in resources
                ),
                None,
            )
            if capture_resource is None:
                raise SmokeError(
                    f"editor framegraph has no capturable color output: {resources}"
                )

            capture_text, _result = tool_call(
                session,
                "capture_framegraph_resource",
                {
                    "target_index": int(framegraph["current_target_index"]),
                    "resource": capture_resource,
                    "path": str(capture_file),
                    "include_image": False,
                    "capture_kind": "main",
                    "channel_mode": 0,
                    "highlight_hdr": False,
                    "timeout": 35.0,
                },
                timeout=45.0,
            )
            if "Captured framegraph resource" not in capture_text:
                raise SmokeError(f"editor framegraph capture failed: {capture_text}")
            require_non_empty_rgba8_png(capture_file)

            screenshot_text, _result = tool_call(
                session,
                "capture_editor_screenshot",
                {
                    "path": str(screenshot_file),
                    "include_image": False,
                    "timeout": 30.0,
                },
            )
            if "Captured editor screenshot" not in screenshot_text:
                raise SmokeError(f"editor screenshot failed: {screenshot_text}")
            require_non_empty_rgba8_png(
                screenshot_file,
                expected_width=640,
                expected_height=360,
            )

            execute_script(
                session,
                "request_editor_close(); print('editor close requested')",
            )
            try:
                return_code = process.wait(timeout=25.0)
            except subprocess.TimeoutExpired as error:
                raise SmokeError("editor did not stop after a clean close request") from error
            if return_code != 0:
                raise SmokeError(f"editor exited with code {return_code}")
        require_clean_d3d11_log(
            log_file,
            require_backend_evidence="D3D11RenderDevice: D3D11 debug layer enabled",
        )
        log_text = log_file.read_text(encoding="utf-8", errors="replace")
        if "[EngineCore] Shutdown complete" not in log_text:
            raise SmokeError("editor log lacks clean engine shutdown evidence")
        success = True
        print(
            "[windows-d3d11-editor-smoke] PASS: "
            "D3D11 scene framegraph, readback, UI presentation, and shutdown",
            flush=True,
        )
        return 0
    except Exception:
        print_log_tail(log_file)
        raise
    finally:
        if process is not None:
            stop_process(process)
        cleanup_work_root(work_root, keep=args.keep_temp or not success)

