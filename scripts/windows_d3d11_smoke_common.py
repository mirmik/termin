"""Shared process helpers for the Windows D3D11 scene smokes."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import time
from typing import Any
import urllib.error
import urllib.request
import uuid
import zlib


class SmokeError(RuntimeError):
    pass


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def prepare_project(work_root: Path) -> Path:
    source = repo_root() / "tests" / "fixtures" / "windows-d3d11-scene"
    project = work_root / "project"
    shutil.copytree(source, project, ignore=shutil.ignore_patterns(".termin", "stdlib"))
    from termin.stdlib import sync_stdlib

    sync_stdlib(project)
    scene = (project / "Main.scene").resolve()
    editor_state = project / "project_settings" / ".editor_state.json"
    editor_state.write_text(
        json.dumps({"last_scene": str(scene)}, indent=2),
        encoding="utf-8",
    )
    return project


def make_work_root(prefix: str) -> Path:
    directory = repo_root() / "build" / "process-smoke" / "work"
    directory.mkdir(parents=True, exist_ok=True)
    # Python 3.14 gives tempfile.mkdtemp(mode=0o700) a restrictive Windows
    # DACL. A separately launched editor/player can then be unable to traverse
    # the directory in isolated runners, despite sharing the same user.
    for _attempt in range(10):
        work_root = directory / f"{prefix}{uuid.uuid4().hex}"
        try:
            work_root.mkdir()
        except FileExistsError:
            continue
        return work_root
    raise SmokeError(f"failed to allocate a unique smoke work directory in {directory}")


def wait_for_session(
    session_file: Path,
    process: subprocess.Popen[str],
    timeout: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last_error = ""
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise SmokeError(
                f"process exited before MCP became ready, code={process.returncode}"
            )
        try:
            session = json.loads(session_file.read_text(encoding="utf-8"))
            if (
                isinstance(session, dict)
                and session.get("url")
                and session.get("token")
                and int(session.get("pid", -1)) == process.pid
            ):
                return session
        except (OSError, ValueError, json.JSONDecodeError) as error:
            last_error = str(error)
        time.sleep(0.2)
    raise SmokeError(
        f"MCP session was not published within {timeout:.1f}s"
        + (f": {last_error}" if last_error else "")
    )


def rpc_call(
    session: dict[str, Any],
    method: str,
    params: dict[str, Any] | None = None,
    *,
    timeout: float = 40.0,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
    }
    if params is not None:
        payload["params"] = params
    request = urllib.request.Request(
        str(session["url"]),
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {session['token']}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise SmokeError(f"MCP returned HTTP {error.code}: {detail}") from error
    except urllib.error.URLError as error:
        raise SmokeError(f"MCP endpoint is unavailable: {error}") from error
    try:
        result = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SmokeError("MCP returned invalid JSON") from error
    if not isinstance(result, dict):
        raise SmokeError("MCP returned a non-object response")
    if result.get("error"):
        raise SmokeError(f"MCP call {method} failed: {result['error']}")
    return result


def tool_call(
    session: dict[str, Any],
    name: str,
    arguments: dict[str, Any],
    *,
    timeout: float = 40.0,
) -> tuple[str, dict[str, Any]]:
    response = rpc_call(
        session,
        "tools/call",
        {"name": name, "arguments": arguments},
        timeout=timeout,
    )
    result = response.get("result")
    if not isinstance(result, dict):
        raise SmokeError(f"MCP tool {name} returned no result object")
    if result.get("isError"):
        raise SmokeError(f"MCP tool {name} reported an error: {result}")
    content = result.get("content")
    if not isinstance(content, list):
        raise SmokeError(f"MCP tool {name} returned no content list")
    text = "\n".join(
        str(item["text"])
        for item in content
        if isinstance(item, dict) and isinstance(item.get("text"), str)
    )
    return text, result


def execute_script(
    session: dict[str, Any],
    script: str,
    *,
    timeout: float = 40.0,
) -> str:
    text, _result = tool_call(
        session,
        "execute_python_script",
        {"script": script, "timeout": timeout},
        timeout=timeout + 5.0,
    )
    return text


def parse_marked_json(output: str, marker: str) -> dict[str, Any]:
    line = next(
        (candidate for candidate in output.splitlines() if candidate.startswith(marker)),
        None,
    )
    if line is None:
        raise SmokeError(f"probe marker {marker!r} is absent:\n{output}")
    try:
        payload = json.loads(line[len(marker) :])
    except json.JSONDecodeError as error:
        raise SmokeError(f"probe marker {marker!r} has invalid JSON") from error
    if not isinstance(payload, dict):
        raise SmokeError(f"probe marker {marker!r} payload is not an object")
    return payload


def require_non_empty_rgba8_png(
    path: Path,
    *,
    expected_width: int | None = None,
    expected_height: int | None = None,
) -> None:
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise SmokeError(f"capture is not a PNG: {path}")
    offset = 8
    idat = bytearray()
    width = height = bit_depth = color_type = interlace = -1
    while offset < len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8]
        payload_start = offset + 8
        payload_end = payload_start + length
        if payload_end + 4 > len(data):
            raise SmokeError(f"capture has a truncated PNG chunk: {path}")
        payload = data[payload_start:payload_end]
        if kind == b"IHDR":
            width, height, bit_depth, color_type, _compression, _filter, interlace = (
                struct.unpack(">IIBBBBB", payload)
            )
        elif kind == b"IDAT":
            idat.extend(payload)
        elif kind == b"IEND":
            break
        offset = payload_end + 4
    if width <= 0 or height <= 0:
        raise SmokeError(f"capture has invalid extent {width}x{height}: {path}")
    if (
        expected_width is not None
        and expected_height is not None
        and (width, height) != (expected_width, expected_height)
    ):
        raise SmokeError(
            f"capture extent is {width}x{height}, expected "
            f"{expected_width}x{expected_height}: {path}"
        )
    if (bit_depth, color_type, interlace) != (8, 6, 0):
        raise SmokeError(
            "capture must be a non-interlaced RGBA8 PNG, got "
            f"depth={bit_depth}, type={color_type}, interlace={interlace}"
        )
    try:
        raw = zlib.decompress(bytes(idat))
    except zlib.error as error:
        raise SmokeError(f"capture has invalid compressed pixels: {path}") from error
    stride = width * 4
    if len(raw) != height * (stride + 1):
        raise SmokeError(f"capture has an unexpected decoded size: {path}")

    previous = bytearray(stride)
    colors: set[bytes] = set()
    visible = False
    for row_index in range(height):
        start = row_index * (stride + 1)
        filter_type = raw[start]
        encoded = raw[start + 1 : start + 1 + stride]
        reconstructed = bytearray(stride)
        for index, value in enumerate(encoded):
            left = reconstructed[index - 4] if index >= 4 else 0
            up = previous[index]
            upper_left = previous[index - 4] if index >= 4 else 0
            if filter_type == 0:
                filtered = value
            elif filter_type == 1:
                filtered = value + left
            elif filter_type == 2:
                filtered = value + up
            elif filter_type == 3:
                filtered = value + ((left + up) // 2)
            elif filter_type == 4:
                prediction = left + up - upper_left
                distances = (
                    abs(prediction - left),
                    abs(prediction - up),
                    abs(prediction - upper_left),
                )
                neighbor = (left, up, upper_left)[distances.index(min(distances))]
                filtered = value + neighbor
            else:
                raise SmokeError(f"capture uses unsupported PNG filter {filter_type}")
            reconstructed[index] = filtered & 0xFF
        for index in range(0, stride, 4):
            pixel = bytes(reconstructed[index : index + 4])
            colors.add(pixel)
            visible = visible or pixel[3] != 0
        previous = reconstructed
    if not visible or len(colors) < 4:
        raise SmokeError(
            f"capture has no useful presentation signal ({len(colors)} colors): {path}"
        )


def require_clean_d3d11_log(path: Path, *, require_backend_evidence: str) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    if require_backend_evidence not in text:
        raise SmokeError(
            f"log lacks D3D11 backend evidence {require_backend_evidence!r}: {path}"
        )
    forbidden = (
        "vertex .cso artifact missing",
        "fragment .cso artifact missing",
        "missing shader artifact",
        "fallback backend",
    )
    found = [marker for marker in forbidden if marker.lower() in text.lower()]
    error_lines = [
        line
        for line in text.splitlines()
        if "[ERROR]" in line or "severity=error" in line or "severity=corruption" in line
    ]
    if found or error_lines:
        details = "\n".join(error_lines[-20:])
        raise SmokeError(
            f"D3D11 log contains forbidden diagnostics {found}: {path}"
            + (f"\n{details}" if details else "")
        )


def stop_process(
    process: subprocess.Popen[str],
    *,
    timeout: float = 20.0,
) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5.0)


def print_log_tail(path: Path, *, lines: int = 160) -> None:
    if not path.is_file():
        return
    print(f"[d3d11-smoke] log tail ({path}):")
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]:
        print(line)


def cleanup_work_root(path: Path, *, keep: bool) -> None:
    if keep:
        print(f"[d3d11-smoke] kept artifacts: {path}")
    else:
        shutil.rmtree(path)
