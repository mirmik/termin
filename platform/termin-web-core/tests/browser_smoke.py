#!/usr/bin/env python3
import argparse
import base64
import functools
import gzip
import hashlib
import http.server
import json
import math
import os
import shutil
import socket
import struct
import subprocess
import tempfile
import threading
import time
import urllib.request
import zlib
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


SUCCESS_MARKER = "TERMIN_WEB_CORE_SMOKE_PASSED"
FAILURE_MARKER = "TERMIN_WEB_CORE_SMOKE_FAILED"
FRAME_READY_MARKER = "TERMIN_WEB_CORE_FRAME_READY"
TEXTURE_OPS_READY_MARKER = "TERMIN_WEB_CORE_TEXTURE_OPS_READY"


def artifact_measurements(output_directory: str) -> dict:
    root = Path(output_directory).resolve()

    def measure(path: Path) -> dict[str, int | str]:
        content = path.read_bytes()
        return {
            "path": path.relative_to(root).as_posix(),
            "bytes": len(content),
            "gzip_bytes": len(gzip.compress(content, compresslevel=9, mtime=0)),
        }

    primary_names = (
        "termin_web_core.wasm",
        "termin_web_core.mjs",
        "termin-web-core.mjs",
        "termin-web-host.mjs",
        "termin-web-input.mjs",
        "termin-web-chart.mjs",
        "termin-web-chart2d.mjs",
        "termin-web-chart3d.mjs",
        "graphics.trpkg",
        "chart2d.html",
        "chart3d.html",
        "viewer.html",
        "visual-scene.html",
    )
    primary = [measure(root / name) for name in primary_names]
    package_root = root / "fixtures" / "render-package"
    package_files = sorted(
        path for path in package_root.rglob("*")
        if path.is_file() and path.name != "package.trpkg"
    )
    package = [measure(path) for path in package_files]
    package_blob = measure(package_root / "package.trpkg")
    return {
        "artifacts": primary,
        "artifact_bytes": sum(item["bytes"] for item in primary),
        "artifact_gzip_bytes": sum(item["gzip_bytes"] for item in primary),
        "standalone_html_bytes": {
            name: (root / name).stat().st_size for name in (
                "Termin-Chart3D.html", "Termin-InteractiveScene.html", "Termin-PhysicsScene.html", "Termin-UiScene.html",
            )
        },
        "package_files": len(package),
        "package_bytes": sum(item["bytes"] for item in package),
        "package_gzip_bytes": sum(item["gzip_bytes"] for item in package),
        "package_blob": package_blob,
    }


def write_report(path: str, report: dict) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(destination)


def find_browser() -> str:
    configured = os.environ.get("TERMIN_WEB_BROWSER")
    if configured:
        if not os.path.isfile(configured):
            raise RuntimeError(f"TERMIN_WEB_BROWSER does not exist: {configured}")
        return configured
    for candidate in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise RuntimeError("No Chromium browser found; set TERMIN_WEB_BROWSER to its executable")


def available_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


class DevToolsSocket:
    def __init__(self, url: str):
        parsed = urlparse(url)
        self.socket = socket.create_connection((parsed.hostname, parsed.port), timeout=5)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        path = parsed.path or "/"
        if parsed.query:
            path += f"?{parsed.query}"
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {parsed.hostname}:{parsed.port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.socket.sendall(request.encode("ascii"))
        response = self._receive_until(b"\r\n\r\n")
        expected = base64.b64encode(hashlib.sha1(
            (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")
        ).digest())
        if not response.startswith(b"HTTP/1.1 101") or expected not in response:
            raise RuntimeError(f"DevTools WebSocket handshake failed: {response!r}")
        self.next_id = 1
        self.events: list[dict] = []

    def _receive_exactly(self, size: int) -> bytes:
        chunks = bytearray()
        while len(chunks) < size:
            chunk = self.socket.recv(size - len(chunks))
            if not chunk:
                raise RuntimeError("DevTools WebSocket closed unexpectedly")
            chunks.extend(chunk)
        return bytes(chunks)

    def _receive_until(self, marker: bytes) -> bytes:
        data = bytearray()
        while marker not in data:
            chunk = self.socket.recv(4096)
            if not chunk:
                raise RuntimeError("DevTools WebSocket closed during handshake")
            data.extend(chunk)
        return bytes(data)

    def _send_frame(self, opcode: int, payload: bytes) -> None:
        mask = os.urandom(4)
        size = len(payload)
        header = bytearray([0x80 | opcode])
        if size < 126:
            header.append(0x80 | size)
        elif size <= 0xFFFF:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", size))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", size))
        header.extend(mask)
        header.extend(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        self.socket.sendall(header)

    def _receive_json(self) -> dict:
        while True:
            first, second = self._receive_exactly(2)
            opcode = first & 0x0F
            size = second & 0x7F
            if size == 126:
                size = struct.unpack("!H", self._receive_exactly(2))[0]
            elif size == 127:
                size = struct.unpack("!Q", self._receive_exactly(8))[0]
            masked = bool(second & 0x80)
            mask = self._receive_exactly(4) if masked else b""
            payload = self._receive_exactly(size)
            if masked:
                payload = bytes(
                    byte ^ mask[index % 4] for index, byte in enumerate(payload)
                )
            if opcode == 0x8:
                raise RuntimeError("DevTools WebSocket sent a close frame")
            if opcode == 0x9:
                self._send_frame(0xA, payload)
                continue
            if opcode == 0x1:
                return json.loads(payload.decode("utf-8"))

    def call(self, method: str, params: dict | None = None) -> dict:
        message_id = self.next_id
        self.next_id += 1
        message = {"id": message_id, "method": method}
        if params is not None:
            message["params"] = params
        self._send_frame(0x1, json.dumps(message).encode("utf-8"))
        while True:
            response = self._receive_json()
            if response.get("id") != message_id:
                self.events.append(response)
                continue
            if "error" in response:
                raise RuntimeError(f"DevTools {method} failed: {response['error']}")
            return response.get("result", {})

    def close(self) -> None:
        try:
            self._send_frame(0x8, b"")
        finally:
            self.socket.close()


def wait_for_page(debug_port: int, page_url: str, timeout: float = 30.0) -> dict:
    deadline = time.monotonic() + timeout
    endpoint = f"http://127.0.0.1:{debug_port}/json"
    observed_urls = set()
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(endpoint, timeout=1) as response:
                targets = json.load(response)
            for target in targets:
                if target.get("type") == "page" and target.get("url"):
                    observed_urls.add(target["url"])
                if target.get("type") == "page" and target.get("url") == page_url:
                    return target
        except (OSError, ValueError):
            pass
        time.sleep(0.05)
    raise RuntimeError(
        "Chrome DevTools did not expose the smoke page within "
        f"{timeout:.1f}s; observed page targets: {sorted(observed_urls)}"
    )


def wait_for_result(devtools: DevToolsSocket, timeout: float = 30.0) -> str:
    deadline = time.monotonic() + timeout
    expression = "document.querySelector('#result')?.textContent ?? ''"
    while time.monotonic() < deadline:
        result = devtools.call("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
        })
        value = result.get("result", {}).get("value", "")
        if value in (SUCCESS_MARKER, FRAME_READY_MARKER, TEXTURE_OPS_READY_MARKER) or \
                value.startswith(FAILURE_MARKER):
            return value
        time.sleep(0.05)
    diagnostics = devtools.call("Runtime.evaluate", {
        "expression": "JSON.stringify({result: document.querySelector('#result')?.textContent, gpu: Boolean(navigator.gpu), asyncError: globalThis.__terminSmokeAsyncError, renderStatus: globalThis.__terminSmokeModule?._termin_web_render_smoke_status?.(), renderError: globalThis.__terminSmokeModule?globalThis.__terminSmokeModule.UTF8ToString(globalThis.__terminSmokeModule._termin_web_render_smoke_error()):''})",
        "returnByValue": True,
    }).get("result", {}).get("value", "")
    raise RuntimeError(
        f"browser smoke page did not publish a terminal result: {diagnostics}"
    )


def wait_for_viewer(
    devtools: DevToolsSocket,
    timeout: float = 30.0,
    *,
    expected_url: str | None = None,
) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = devtools.call("Runtime.evaluate", {
            "expression": "JSON.stringify({url:location.href,state:globalThis.__terminViewer?.host?.state ?? '',hostError:globalThis.__terminViewer?.host?.error ?? '',errorPanel:document.querySelector('#error')?.textContent ?? '',frames:globalThis.__terminViewer?.host?.frameCount?.() ?? 0,hostMetrics:globalThis.__terminViewer?.host?.metrics ?? null,inputMetrics:globalThis.__terminViewer?.input?.metrics ?? null})",
            "returnByValue": True,
        }).get("result", {}).get("value", "")
        if result:
            state = json.loads(result)
            if expected_url is not None and state["url"] != expected_url:
                time.sleep(0.05)
                continue
            if state["state"] == "running" and state["frames"] >= 2:
                return state
            if state["state"] == "error":
                raise RuntimeError(f"viewer entered error state: {state}")
        time.sleep(0.05)
    raise RuntimeError("viewer did not reach running state")


def navigate_to_viewer(
    devtools: DevToolsSocket,
    viewer_url: str,
    *,
    attempts: int = 2,
) -> dict:
    failures = []
    for attempt in range(1, attempts + 1):
        attempt_url = f"{viewer_url}?gate_attempt={attempt}"
        devtools.call("Page.navigate", {"url": attempt_url})
        try:
            return wait_for_viewer(devtools, expected_url=attempt_url)
        except RuntimeError as error:
            failures.append(str(error))
    raise RuntimeError(
        f"viewer failed after {attempts} isolated page loads: {failures}; "
        f"console={console_diagnostics(devtools)}"
    )


def wait_for_visual_scene_example(devtools: DevToolsSocket, timeout: float = 30.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = devtools.call("Runtime.evaluate", {
            "expression": "JSON.stringify(globalThis.__terminVisualSceneExample ? {status:globalThis.__terminVisualSceneExample.status,error:globalThis.__terminVisualSceneExample.error ?? '',backend:globalThis.__terminVisualSceneExample.backend ?? ''} : null)",
            "returnByValue": True,
        }).get("result", {}).get("value", "")
        if result and result != "null":
            state = json.loads(result)
            if state.get("status") == "ready":
                return state
            if state.get("status") == "error":
                raise RuntimeError(f"VisualScene2D example failed: {state}")
        time.sleep(0.05)
    raise RuntimeError("VisualScene2D example did not reach ready state")


def decode_png(content: bytes) -> tuple[int, int, int, list[bytearray]]:
    if not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError("DevTools canvas screenshot is not a PNG")
    offset = 8
    width = height = color_type = bit_depth = interlace = 0
    compressed = bytearray()
    while offset + 12 <= len(content):
        size = struct.unpack("!I", content[offset:offset + 4])[0]
        kind = content[offset + 4:offset + 8]
        payload = content[offset + 8:offset + 8 + size]
        offset += 12 + size
        if kind == b"IHDR":
            width, height, bit_depth, color_type, _compression, _filter, interlace = struct.unpack(
                "!IIBBBBB", payload
            )
        elif kind == b"IDAT":
            compressed.extend(payload)
        elif kind == b"IEND":
            break
    channels = {2: 3, 6: 4}.get(color_type)
    if bit_depth != 8 or channels is None or interlace != 0:
        raise RuntimeError(
            f"unsupported screenshot PNG layout: depth={bit_depth} color={color_type} interlace={interlace}"
        )
    raw = zlib.decompress(compressed)
    stride = width * channels
    previous = bytearray(stride)
    rows: list[bytearray] = []
    cursor = 0
    for _row in range(height):
        filter_type = raw[cursor]
        cursor += 1
        scanline = bytearray(raw[cursor:cursor + stride])
        cursor += stride
        for index in range(stride):
            left = scanline[index - channels] if index >= channels else 0
            up = previous[index]
            upper_left = previous[index - channels] if index >= channels else 0
            if filter_type == 1:
                scanline[index] = (scanline[index] + left) & 0xFF
            elif filter_type == 2:
                scanline[index] = (scanline[index] + up) & 0xFF
            elif filter_type == 3:
                scanline[index] = (scanline[index] + ((left + up) // 2)) & 0xFF
            elif filter_type == 4:
                estimate = left + up - upper_left
                distances = (abs(estimate - left), abs(estimate - up), abs(estimate - upper_left))
                predictor = (left, up, upper_left)[distances.index(min(distances))]
                scanline[index] = (scanline[index] + predictor) & 0xFF
            elif filter_type != 0:
                raise RuntimeError(f"unsupported PNG filter {filter_type}")
        rows.append(scanline)
        previous = scanline
    return width, height, channels, rows


def analyze_png(
    content: bytes,
    probes: dict[str, tuple[int, int]] | None = None,
) -> dict:
    width, height, channels, rows = decode_png(content)
    bright_pixels = 0
    colors: set[tuple[int, int, int]] = set()
    channel_min = [255, 255, 255]
    channel_max = [0, 0, 0]
    pixel_bytes = bytearray()
    for row in rows:
        pixel_bytes.extend(row)
        for offset in range(0, len(row), channels):
            red, green, blue = row[offset:offset + 3]
            if max(red, green, blue) > 120:
                bright_pixels += 1
            for index, value in enumerate((red, green, blue)):
                channel_min[index] = min(channel_min[index], value)
                channel_max[index] = max(channel_max[index], value)
            colors.add((red >> 4, green >> 4, blue >> 4))
    metrics = {
        "width": width,
        "height": height,
        "bright_pixels": bright_pixels,
        "quantized_colors": len(colors),
        "channel_min": channel_min,
        "channel_max": channel_max,
        "pixel_sha256": hashlib.sha256(pixel_bytes).hexdigest(),
    }
    if probes:
        sampled = {}
        for name, (x, y) in probes.items():
            if x < 0 or y < 0 or x >= width or y >= height:
                raise RuntimeError(f"PNG probe {name} is outside {width}x{height}: {(x, y)}")
            offset = x * channels
            sampled[name] = list(rows[y][offset:offset + 3])
        metrics["probes"] = sampled
    return metrics


def console_diagnostics(devtools: DevToolsSocket) -> list[str]:
    messages: list[str] = []
    seen: set[str] = set()
    for event in devtools.events:
        if event.get("method") != "Runtime.consoleAPICalled":
            continue
        args = event.get("params", {}).get("args", [])
        text = " ".join(str(arg.get("value", arg.get("description", ""))) for arg in args)
        if text and text not in seen:
            seen.add(text)
            messages.append(text)
    return messages[-100:]


def evaluate(devtools: DevToolsSocket, expression: str):
    response = devtools.call("Runtime.evaluate", {
        "expression": expression, "returnByValue": True, "awaitPromise": True,
    })
    if "exceptionDetails" in response:
        raise RuntimeError(f"Chart script failed: {response['exceptionDetails']}")
    return response["result"].get("value")


def chart_screenshot(devtools: DevToolsSocket, width_fraction: float = 1.0) -> tuple[dict, bytes]:
    # Synchronize with a scheduled chart redraw and Chromium's compositor.
    evaluate(devtools, "new Promise(done => requestAnimationFrame(() => requestAnimationFrame(() => done(true))))")
    bounds = evaluate(devtools, """(() => {
        const c = document.querySelector('canvas'), r = c.getBoundingClientRect();
        return {x:r.x, y:r.y, width:r.width, height:r.height, bufferWidth:c.width, bufferHeight:c.height};
    })()""")
    screenshot = devtools.call("Page.captureScreenshot", {
        "format": "png",
        "clip": {"x": round(bounds["x"] + bounds["width"] * (1 - width_fraction) / 2),
                 "y": round(bounds["y"]), "width": round(bounds["width"] * width_fraction),
                 "height": round(bounds["height"]), "scale": 1},
        "captureBeyondViewport": True,
    })
    return bounds, base64.b64decode(screenshot["data"])


def chart_frame(devtools: DevToolsSocket) -> dict:
    # The central half of the canvas contains both the plotted series and the X-axis caption.
    bounds, png = chart_screenshot(devtools, width_fraction=0.5)
    width, height, channels, rows = decode_png(png)
    series_rows = []
    series_colors = Counter()
    plot_colors = Counter()
    caption_pixels = 0
    for y, row in enumerate(rows):
        if height // 10 < y < height * 9 // 10:
            if y % 7 == 0:
                plot_colors.update(tuple(row[i:i + 3]) for i in range(0, len(row), channels * 7))
            # The native line is teal; axes, grids, and label glyphs are gray.
            teal = sum(1 for i in range(0, len(row), channels)
                       if row[i + 1] > 120 and row[i + 1] > row[i] + 45 and row[i + 2] > row[i] + 35)
            if teal >= width * 0.75:
                series_rows.append(y)
                series_colors.update(tuple(row[i:i + 3]) for i in range(0, len(row), channels))
        if height - 26 <= y < height - 5:
            caption_pixels += sum(1 for i in range(0, len(row), channels)
                                  if min(row[i:i + 3]) > 130)
    if not series_rows or caption_pixels < 12:
        raise RuntimeError(f"RetainedChart2D native pixel probes failed: "
                           f"{bounds=}, {series_rows=}, {caption_pixels=}; console={console_diagnostics(devtools)}")
    color = series_colors.most_common(1)[0][0]
    background = plot_colors.most_common(1)[0][0]
    for feature, sampled, expected in (
        ("line", color, (15, 209, 168)), ("plot background", background, (31, 33, 41)),
    ):
        if max(abs(a - b) for a, b in zip(sampled, expected, strict=True)) > 3:
            raise RuntimeError(f"RetainedChart2D {feature} sRGB mismatch: expected {expected}, got {sampled}")
    return {"bounds": bounds, "line_y": sum(series_rows) / len(series_rows),
            "line_rgb": color, "plot_rgb": background, "caption_pixels": caption_pixels}


def open_chart(devtools: DevToolsSocket, url: str, backend: str | None, name: str) -> str:
    chart_url = f"{url}?backend={backend}" if backend else url
    devtools.call("Page.navigate", {"url": chart_url})
    state = None
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        state = evaluate(devtools, f"""(() => {{
            const page = globalThis.__termin{name};
            return page && {{url:location.href, status:page.status, backend:page.backend, error:page.error}};
        }})()""")
        if state and state["url"] == chart_url and state["status"] in ("ready", "error"):
            break
        time.sleep(0.05)
    expected = (backend,) if backend else ("webgpu", "webgl2")
    if not state or state["url"] != chart_url or state["status"] != "ready" or state["backend"] not in expected:
        raise RuntimeError(f"Retained{name} failed to initialize on {backend}: {state}; "
                           f"console={console_diagnostics(devtools)}")
    return f"globalThis.__termin{name}.chart"


def check_chart(devtools: DevToolsSocket, url: str, backend: str) -> dict:
    chart = open_chart(devtools, url, backend, "Chart2D")
    initial = evaluate(devtools, f"{chart}.getRange()")
    x_min, x_max = initial["xMin"], initial["xMax"]
    y_span = initial["yMax"] - initial["yMin"]
    if not (x_max > x_min and y_span > 0):
        raise RuntimeError(f"Invalid initial chart range: {initial}")

    frames = []
    for fraction in (0.75, 0.25):
        y = initial["yMin"] + fraction * y_span
        evaluate(devtools, f"{chart}.setData(new Float64Array([{x_min},{x_max}]), [{y},{y}]); true")
        frames.append(chart_frame(devtools))
    bounds = frames[1]["bounds"]
    if frames[1]["line_y"] - frames[0]["line_y"] < bounds["height"] * 0.25:
        raise RuntimeError(f"Replacing the chart series didn't move it down the plot: {frames}")

    x, y = bounds["x"] + bounds["width"] * 0.55, bounds["y"] + bounds["height"] * 0.45
    devtools.call("Input.dispatchMouseEvent", {
        "type": "mouseWheel", "x": x, "y": y, "deltaX": 0, "deltaY": -100,
    })
    zoomed = chart_frame(devtools)
    zoom_range = evaluate(devtools, f"{chart}.getRange()")
    zoom_span = zoom_range["xMax"] - zoom_range["xMin"]
    if not (0 < zoom_span < x_max - x_min) or abs(zoomed["line_y"] - frames[1]["line_y"]) < 2:
        raise RuntimeError(f"Wheel zoom failed: {initial=}, {zoom_range=}, {zoomed=}")

    for action, dx, dy, buttons in (
        ("mousePressed", 0, 0, 4), ("mouseMoved", 36, -18, 4), ("mouseReleased", 36, -18, 0),
    ):
        devtools.call("Input.dispatchMouseEvent", {
            "type": action, "x": x + dx, "y": y + dy, "button": "middle", "buttons": buttons,
        })
    panned = chart_frame(devtools)
    pan_range = evaluate(devtools, f"{chart}.getRange()")
    if (not math.isclose(pan_range["xMax"] - pan_range["xMin"], zoom_span)
        or pan_range["xMin"] >= zoom_range["xMin"] or panned["line_y"] >= zoomed["line_y"] - 5):
        raise RuntimeError(f"Pointer pan failed: {zoom_range=}, {pan_range=}, {panned=}")

    width, height = round(bounds["width"] * 0.85), round(bounds["height"] * 0.8)
    evaluate(devtools, f"""Object.assign(document.querySelector('canvas').style,
        {{ width:'{width}px', height:'{height}px' }}); true""")
    resized = chart_frame(devtools)
    if (resized["bounds"]["bufferWidth"], resized["bounds"]["bufferHeight"]) != (width, height):
        raise RuntimeError(f"Chart framebuffer did not follow CSS resize to {width}x{height}: {resized}")
    invalid_range_error = evaluate(devtools, f"""(async () => {{
        await {chart}.dispose();
        const canvas = document.querySelector('canvas');
        canvas.removeAttribute('id');
        const {{createTerminChart2D}} = await import('./termin-web-chart2d.mjs');
        const remounted = await createTerminChart2D(canvas, {{backend:'{backend}'}});
        const before = remounted.getRange();
        let invalidRangeError;
        try {{
            remounted.setRange({{...before, xMin:before.xMax}});
        }} catch (error) {{
            invalidRangeError = error;
        }}
        if (!(invalidRangeError instanceof Error) || !/range/i.test(invalidRangeError.message))
            throw new Error('Invalid chart range did not produce an actionable JS Error: ' + invalidRangeError);
        if (JSON.stringify(remounted.getRange()) !== JSON.stringify(before))
            throw new Error('Invalid chart range changed the previous range');
        remounted.setData([0, 1], [0, 1]);
        await remounted.dispose();
        if (canvas.id) throw new Error('Chart disposal left its generated canvas ID behind');
        return invalidRangeError.message;
    }})()""")
    return {"series_frames": frames, "zoom_range": zoom_range, "pan_range": pan_range,
            "resized": resized, "invalid_range_error": invalid_range_error}


def surface_frame(devtools: DevToolsSocket, *, check_axes: bool = False) -> tuple[dict, list[tuple[int, ...]]]:
    bounds, png = chart_screenshot(devtools)
    width, height, channels, rows = decode_png(png)
    samples = [tuple(row[i:i + 3]) for row in rows[::4] for i in range(0, width * channels, channels * 4)]
    # The native mesh uses a colormap. Grid lines, axes, labels and background are neutral.
    surface = [rgb for rgb in samples if max(rgb) - min(rgb) > 35]
    bins = {tuple(c >> 4 for c in rgb) for rgb in surface}
    if len(surface) < len(samples) * 0.02 or len(bins) < 6:
        raise RuntimeError(f"Missing 3D surface in {width}x{height} canvas: {len(surface)} colored samples, "
                           f"{len(bins)} colors; console={console_diagnostics(devtools)}")
    metrics = {"bounds": bounds, "mesh_samples": len(surface), "mesh_colors": len(bins)}
    if check_axes:
        background = Counter(samples).most_common(1)[0][0]
        if max(abs(a - b) for a, b in zip(background, (20, 23, 28), strict=True)) > 3:
            raise RuntimeError(f"RetainedChart3D background sRGB mismatch: {background}")
        # The default 3D grid is blue-gray; its tick and axis glyphs are brighter and neutral.
        grid = sum(90 <= r <= 125 and 0 < g - r < 14 and 10 < b - r < 33 for r, g, b in samples)
        glyphs = sum(min(rgb) >= 148 and max(rgb) - min(rgb) < 8 for rgb in samples)
        if grid < 30 or glyphs < 4:
            raise RuntimeError(f"Missing native 3D axes or labels in {width}x{height}: {grid=}, {glyphs=}")
        metrics.update(grid_samples=grid, glyph_samples=glyphs, background=background)
    return metrics, samples


def surface_change(before: list, after: list, action: str) -> int:
    changed = sum(max(abs(a - b) for a, b in zip(first, second, strict=True)) > 24
                  for first, second in zip(before, after, strict=True))
    if changed < len(before) * 0.01:
        raise RuntimeError(f"RetainedChart3D {action} changed just {changed} of {len(before)} sampled pixels")
    return changed


def check_chart3d(devtools: DevToolsSocket, url: str, backend: str) -> dict:
    chart = open_chart(devtools, url, backend, "Chart3D")
    first, original = surface_frame(devtools, check_axes=True)
    invalid_errors = evaluate(devtools, f"""(() => {{
        const errors = [];
        for (const z of [[0, 1, 2], [0, 1, Infinity, 0]]) {{
            try {{ {chart}.setSurface([0, 1], [0, 1], z); }}
            catch (error) {{ if (error instanceof Error && error.message) errors.push(error.message); }}
        }}
        {chart}.render();
        return errors;
    }})()""")
    _, after_invalid = surface_frame(devtools)
    if len(invalid_errors) != 2 or after_invalid != original:
        raise RuntimeError(f"Invalid 3D surface input was accepted or changed the previous frame: {invalid_errors}")

    # A non-square replacement grid exercises the layout of the packed axis and elevation data.
    evaluate(devtools, f"""(() => {{
        const x = Float64Array.from({{length: 31}}, (_, i) => (i - 15) / 7);
        const y = Array.from({{length: 17}}, (_, j) => (j - 8) / 5);
        {chart}.setSurface(x, y, y.flatMap(v => Array.from(x, u => Math.sin(2*u + v) + 0.5*v)), {{fit:true}});
    }})()""")
    updated, replacement = surface_frame(devtools)
    replaced_pixels = surface_change(original, replacement, "data replacement")
    camera = evaluate(devtools, f"{chart}.getCamera()")
    bounds = updated["bounds"]
    x, y = bounds["x"] + bounds["width"] / 2, bounds["y"] + bounds["height"] / 2
    for action, dx, dy, buttons in (
        ("mousePressed", 0, 0, 1), ("mouseMoved", 62, -28, 1), ("mouseReleased", 62, -28, 0),
    ):
        devtools.call("Input.dispatchMouseEvent", {
            "type": action, "x": x + dx, "y": y + dy, "button": "left", "buttons": buttons,
        })
    _, orbited = surface_frame(devtools)
    after_orbit = evaluate(devtools, f"{chart}.getCamera()")
    if all(math.isclose(camera[k], after_orbit[k]) for k in ("azimuth", "elevation")):
        raise RuntimeError(f"Pointer drag did not orbit the camera: {camera} -> {after_orbit}")
    orbit_pixels = surface_change(replacement, orbited, "orbit")

    devtools.call("Input.dispatchMouseEvent", {
        "type": "mouseWheel", "x": x, "y": y, "deltaX": 0, "deltaY": -160,
    })
    _, zoomed = surface_frame(devtools)
    after_zoom = evaluate(devtools, f"{chart}.getCamera()")
    if not (0 < after_zoom["distance"] < after_orbit["distance"]):
        raise RuntimeError(f"Wheel did not zoom the camera: {after_orbit} -> {after_zoom}")
    zoom_pixels = surface_change(orbited, zoomed, "zoom")

    width, height = round(bounds["width"] * 0.85), round(bounds["height"] * 0.8)
    evaluate(devtools, f"""Object.assign(document.querySelector('canvas').style,
        {{ width:'{width}px', height:'{height}px' }}); true""")
    resized, _ = surface_frame(devtools)
    if (resized["bounds"]["bufferWidth"], resized["bounds"]["bufferHeight"]) != (width, height):
        raise RuntimeError(f"3D chart framebuffer did not follow CSS resize to {width}x{height}: {resized}")

    evaluate(devtools, f"""(async () => {{
        await {chart}.dispose();
        const canvas = document.querySelector('canvas');
        canvas.removeAttribute('id');
        const {{createTerminChart3D}} = await import('./termin-web-chart3d.mjs');
        const again = await createTerminChart3D(canvas, {{backend:'{backend}'}});
        again.setSurface([0, 1, 2], [0, 1], [0, 1, 0, -1, 0, 1]);
        globalThis.__terminChart3D.chart = again;
    }})()""")
    remounted, _ = surface_frame(devtools)
    evaluate(devtools, f"""(async () => {{
        await {chart}.dispose();
        if (document.querySelector('canvas').id) throw Error('Chart disposal left a generated canvas ID');
    }})()""")
    return {"initial": first, "replacement": updated, "resized": resized, "remounted": remounted,
            "invalid_errors": invalid_errors, "replaced_pixels": replaced_pixels,
            "orbit_pixels": orbit_pixels, "zoom_pixels": zoom_pixels}


@contextmanager
def offline_page(devtools: DevToolsSocket, artifact: Path):
    with tempfile.TemporaryDirectory(prefix="termin-offline-") as folder:
        # The delivered file has no sibling JS, Wasm or shader package to load.
        page = Path(folder) / f"Проверка {artifact.name}"
        shutil.copyfile(artifact, page)
        timeout = devtools.socket.gettimeout()
        devtools.socket.settimeout(30)
        devtools.call("Network.enable")
        try:
            devtools.call("Network.setCacheDisabled", {"cacheDisabled": True})
            devtools.call("Network.emulateNetworkConditions", {
                "offline": True, "latency": 0, "downloadThroughput": 0, "uploadThroughput": 0,
            })
            yield page.as_uri()
        finally:
            devtools.call("Network.emulateNetworkConditions", {
                "offline": False, "latency": 0, "downloadThroughput": -1, "uploadThroughput": -1,
            })
            devtools.call("Network.setCacheDisabled", {"cacheDisabled": False})
            devtools.call("Network.disable")
            devtools.socket.settimeout(timeout)


def check_standalone_chart3d(devtools: DevToolsSocket, artifact: Path) -> dict:
    with offline_page(devtools, artifact) as url:
        chart = open_chart(devtools, url, None, "Chart3D")
        before, wave = surface_frame(devtools, check_axes=True)
        evaluate(devtools, "document.querySelector('#change-surface').click()")
        after, saddle = surface_frame(devtools)
        changed = surface_change(wave, saddle, "offline example button")
        backend = evaluate(devtools, f"{chart}.backend")
        evaluate(devtools, f"{chart}.dispose()")
        return {"backend": backend, "initial": before, "replacement": after, "changed_samples": changed}


def dispatch_gesture(devtools: DevToolsSocket, touch: bool, start: tuple, *moves: tuple):
    if touch:
        devtools.call("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [
            {"id": 1, "x": start[0], "y": start[1]}]})
        for x, y in moves:
            devtools.call("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [
                {"id": 1, "x": x, "y": y}]})
        devtools.call("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    else:
        devtools.call("Input.dispatchMouseEvent", {
            "type": "mousePressed", "x": start[0], "y": start[1], "button": "left", "buttons": 1, "clickCount": 1})
        for x, y in moves:
            devtools.call("Input.dispatchMouseEvent", {
                "type": "mouseMoved", "x": x, "y": y, "button": "left", "buttons": 1})
        x, y = moves[-1] if moves else start
        devtools.call("Input.dispatchMouseEvent", {
            "type": "mouseReleased", "x": x, "y": y, "button": "left", "buttons": 0, "clickCount": 1})


def aces_to_srgb8(radiance: float) -> int:
    # The default framegraph applies the ACES fitted curve, then the sRGB output transfer.
    linear = min(1, radiance * (2.51 * radiance + 0.03) / (radiance * (2.43 * radiance + 0.59) + 0.14))
    srgb = 12.92 * linear if linear <= 0.0031308 else 1.055 * linear ** (1 / 2.4) - 0.055
    return round(255 * srgb)


def check_lamp_silhouette(devtools: DevToolsSocket, center: tuple[float, float], radius: float) -> dict:
    # Each horizontal scanline crosses only the bulb's left edge, from sky to lit glass.
    # Capture at native device resolution: shrinking the screenshot would antialias it.
    cx, cy = center
    clip = {"x": round(cx - 1.45 * radius), "y": round(cy - 0.65 * radius),
            "width": round(1.05 * radius), "height": round(1.3 * radius), "scale": 1}
    shot = devtools.call("Page.captureScreenshot", {"format": "png", "clip": clip})
    _, height, channels, rows = decode_png(base64.b64decode(shot["data"]))
    # At the amber bulb's silhouette the lit material emits about 0.65–0.75 red.
    # The 4x resolve mixes 1, 2 or 3 covered samples with dark sky in linear HDR.
    # Bound those intermediate values before applying the nonlinear display transform.
    low, high = aces_to_srgb8(0.20 * 0.65), aces_to_srgb8(0.80 * 0.75)
    partial = sum(any(low <= red <= high for red in row[::channels]) for row in rows)
    if partial < 0.20 * height:
        raise RuntimeError(f"Lamp silhouette has partial pixel coverage on only {partial}/{height} rows")
    return {"partially_covered_rows": partial, "sampled_rows": height}


def check_interactive_scene(devtools: DevToolsSocket, artifact: Path, backend: str, *, touch: bool) -> dict:
    with offline_page(devtools, artifact) as url:
        devtools.call("Emulation.setDeviceMetricsOverride", {
            "width": 412 if touch else 800, "height": 730 if touch else 560,
            "mobile": touch, "deviceScaleFactor": 2 if touch else 1})
        devtools.call("Emulation.setTouchEmulationEnabled", {"enabled": touch})
        try:
            first_event = len(devtools.events)
            url += f"?backend={backend}"
            devtools.call("Page.navigate", {"url": url})
            wait_for_viewer(devtools, expected_url=url)
            if evaluate(devtools, "__terminViewer.host.graphicsBackend") != backend:
                raise RuntimeError(f"Interactive scene did not start on {backend}")
            x, y, width, height = evaluate(devtools, """(async () => {
                // Pixel-align the canvas so the compositor cannot smooth a single-sample frame.
                const canvas = document.querySelector('canvas');
                const box = canvas.getBoundingClientRect();
                Object.assign(canvas.style, {position:'relative',
                    left:(Math.round(box.x)-box.x)+'px', top:(Math.round(box.y)-box.y)+'px',
                    width:Math.round(box.width)+'px', height:Math.round(box.height)+'px'});
                await __terminViewer.host.waitForFrames(__terminViewer.host.frameCount()+3);
                const r = canvas.getBoundingClientRect();
                return [r.x, r.y, r.width, r.height];
            })()""")
            cx, cy = x + width / 2, y + height / 2

            # Project the demo's known lamp centres independently of the native picking implementation.
            focal_length = width / (2 * math.tan(math.radians(60) / 2))
            pixels_per_unit = focal_length / (5.5 - 0.65)
            amber = (cx - 1.06 * pixels_per_unit, cy - 0.18 * pixels_per_unit)
            cyan = (cx + 1.06 * pixels_per_unit, amber[1])

            def state(amber_on, cyan_on):
                actual = evaluate(devtools, """['amber', 'cyan'].map(id =>
                    document.getElementById(id).getAttribute('aria-pressed') === 'true')""")
                if actual != [amber_on, cyan_on]:
                    raise RuntimeError(f"Interactive scene on {backend}: expected {[amber_on, cyan_on]}, got {actual}")

            def sphere_pixels():
                # Sample a patch containing only the lit sphere. DOM and switch indicators lie outside it.
                evaluate(devtools, "new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done)))")
                w, h = width * 0.24, width * 0.10
                data = devtools.call("Page.captureScreenshot", {"format": "png", "clip": {
                    "x": cx - w / 2, "y": cy - h / 2, "width": w, "height": h, "scale": 0.5}})
                w, _, channels, rows = decode_png(base64.b64decode(data["data"]))
                return [row[i:i+3] for row in rows[::2] for i in range(0, w * channels, channels * 2)]

            def lamp_frame():
                image = devtools.call("Page.captureScreenshot", {"format": "png", "clip": {
                    "x": x, "y": y, "width": width, "height": height, "scale": 0.5}})
                return decode_png(base64.b64decode(image["data"]))

            def check_darkened(before, after, channel):
                darker = sum(a[channel] - b[channel] > 24 for a, b in zip(before, after, strict=True))
                if darker < 0.08 * len(before):
                    raise RuntimeError(f"Switch {channel} on {backend} dimmed only {darker}/{len(before)} sphere samples")
                return darker

            state(True, True)
            lit = sphere_pixels()
            silhouette = check_lamp_silhouette(devtools, amber, 0.23 * pixels_per_unit)
            fw, fh, channels, before_rows = lamp_frame()
            lamp_colors = []
            for px, py in (amber, cyan):
                column = round((px - x) * fw / width) * channels
                lamp_colors.append(before_rows[round((py - y) * fh / height)][column:column + 3])
            dispatch_gesture(devtools, touch, (cx, cy))  # an unbound, visible mesh
            state(True, True)
            dispatch_gesture(devtools, touch, (x + 0.06 * width, cy))  # empty background
            state(True, True)
            dispatch_gesture(devtools, touch, amber)
            state(False, True)
            blue = sphere_pixels()
            dispatch_gesture(devtools, touch, cyan)
            state(False, False)
            dark = sphere_pixels()
            changed_amber = check_darkened(lit, blue, 0)
            changed_cyan = check_darkened(blue, dark, 2)

            dispatch_gesture(devtools, touch, cyan)
            dispatch_gesture(devtools, touch, amber)
            state(True, True)
            restored = sphere_pixels()
            if any(abs(a[c] - b[c]) > 3 for a, b in zip(lit, restored, strict=True) for c in range(3)):
                raise RuntimeError(f"Restoring the lights on {backend} did not restore the sphere")
            # A drag that returns to the lamp must still suppress the release tap.
            dispatch_gesture(devtools, touch, amber, (amber[0] + 30, amber[1]), amber)
            state(True, True)
            dispatch_gesture(devtools, touch, amber, (amber[0] + 160, amber[1] + 45))
            state(True, True)
            moved = sphere_pixels()
            changed_orbit = sum(max(abs(a[c] - b[c]) for c in range(3)) > 12
                                for a, b in zip(restored, moved, strict=True))
            if changed_orbit < 0.05 * len(restored):
                raise RuntimeError("Dragging from a lamp did not orbit the camera")
            # Locate a moved bulb by the colour of its glowing centre in the rendered image.
            # Requiring displacement beyond its original radius catches a picker using stale matrices.
            fw, fh, channels, rows = lamp_frame()
            candidates = []
            for lamp, color, (px, py) in zip(("amber", "cyan"), lamp_colors, (amber, cyan), strict=True):
                origin_x, origin_y = (px - x) * fw / width, (py - y) * fh / height
                radius = 0.23 * pixels_per_unit * fw / width
                distances = (
                    (sum(abs(row[col * channels + c] - color[c]) for c in range(3)), col, r)
                    for r, row in enumerate(rows)
                    for col in range(1, fw, 2)
                    if (col - origin_x)**2 + (r - origin_y)**2 > (1.2 * radius)**2
                )
                error, col, r = min(distances)
                candidates.append((error, lamp, x + (col + 0.5) * width / fw, y + (r + 0.5) * height / fh))
            error, lamp, click_x, click_y = min(candidates)
            if error > 20:
                raise RuntimeError(f"No moved light matched its rendered colour after orbit: {candidates}")
            dispatch_gesture(devtools, touch, (click_x, click_y))
            state(lamp != "amber", lamp != "cyan")
            for event in devtools.events[first_event:]:
                if event.get("method") == "Network.requestWillBeSent":
                    requested = event["params"]["request"]["url"]
                    if requested != url and not requested.startswith(("data:", "blob:")):
                        raise RuntimeError(f"Standalone scene requested another file: {requested[:200]}")
            return {"touch": touch, "silhouette": silhouette, "sphere_samples": len(lit), "amber_darkened": changed_amber,
                    "cyan_darkened": changed_cyan, "orbit_changed": changed_orbit, "picked_after_orbit": lamp}
        finally:
            devtools.call("Emulation.setTouchEmulationEnabled", {"enabled": False})
            devtools.call("Emulation.clearDeviceMetricsOverride")


def check_ui_scene(devtools: DevToolsSocket, artifact: Path, backend: str) -> dict:
    with offline_page(devtools, artifact) as url:
        dpr = 2 if backend == "webgl2" else 1
        devtools.call("Emulation.setDeviceMetricsOverride", {
            "width": 400 if dpr == 2 else 800, "height": 560, "mobile": dpr == 2, "deviceScaleFactor": dpr})
        devtools.call("Emulation.setTouchEmulationEnabled", {"enabled": True})
        try:
            url += f"?backend={backend}"
            devtools.call("Page.navigate", {"url": url})
            wait_for_viewer(devtools, expected_url=url)
            if evaluate(devtools, "__terminViewer.host.graphicsBackend") != backend:
                raise RuntimeError(f"UI scene did not start on {backend}")

            def frame():
                bounds, png = chart_screenshot(devtools)
                w, h, channels, rows = decode_png(png)
                # Count light glyph pixels, excluding the checkbox's focus border.
                def ink(left, top, right, bottom):
                    left, right = (round(x * w / bounds["width"]) for x in (left, right))
                    top, bottom = (round(y * h / bounds["height"]) for y in (top, bottom))
                    return sum(min(row[i:i+3]) > 170 for row in rows[top:bottom]
                               for i in range(left * channels, right * channels, channels))

                scene = [row[w//3*channels:w*2//3*channels] for row in rows[h//3:h*2//3:3]]
                return bounds, ink(31, 119, 65, 154), ink(80, 112, 250, 160), scene

            bounds, unchecked, label, initial_scene = frame()
            if unchecked > 5 or label < 30:
                raise RuntimeError(f"UI scene on {backend}: empty checkbox ink={unchecked}, label ink={label}")
            center = (bounds["x"] + 48, bounds["y"] + 136)
            # Drag within the control. It must consume the gesture before the orbit camera.
            dispatch_gesture(devtools, False, center, (center[0] + 12, center[1] + 8))
            _, checked, _, after_mouse = frame()
            if checked < 20 or initial_scene != after_mouse:
                raise RuntimeError(f"UI scene on {backend}: mouse check ink={checked}, "
                                   f"camera moved={initial_scene != after_mouse}")
            dispatch_gesture(devtools, True, center)
            _, after_tap, _, after_touch = frame()
            if after_tap > 5 or initial_scene != after_touch:
                raise RuntimeError(f"UI scene on {backend}: touch uncheck ink={after_tap}, "
                                   f"camera moved={initial_scene != after_touch}")
            for event in ("mousePressed", "mouseReleased"):
                devtools.call("Input.dispatchMouseEvent", {
                    "type": event, "x": center[0], "y": center[1], "button": "right", "clickCount": 1})
            if frame()[1] > 5:
                raise RuntimeError(f"UI scene on {backend}: right mouse click activated the checkbox")
            return {"device_scale_factor": dpr, "label_pixels": label, "checked_pixels": checked,
                    "unchecked_after_tap": after_tap}
        finally:
            devtools.call("Emulation.setTouchEmulationEnabled", {"enabled": False})
            devtools.call("Emulation.clearDeviceMetricsOverride")


def check_native_animation_loop(devtools: DevToolsSocket):
    # Drive the actual Wasm renderer with controlled browser-timestamp gaps.
    evaluate(devtools, """(() => {
        const m = __terminViewer.core.module;
        const request = window.requestAnimationFrame, cancel = window.cancelAnimationFrame;
        const pending = new Map();
        let id = 0;
        window.requestAnimationFrame = callback => {
            pending.set(++id, callback);
            return id;
        };
        window.cancelAnimationFrame = id => pending.delete(id);
        try {
            m._termin_web_host_loop_start();
            m._termin_web_host_loop_stop();
            m._termin_web_host_loop_start();
            for (const timestamp of [100, 1400, 1400]) {
                if (pending.size !== 1) throw Error("Expected exactly one native frame request");
                const callback = pending.values().next().value;
                pending.clear();
                const before = m._termin_web_host_frame_count();
                callback(timestamp);
                if (m._termin_web_host_frame_count() !== before + 1) throw Error("Native frame loop stalled");
            }
        } finally {
            m._termin_web_host_loop_stop();
            window.requestAnimationFrame = request;
            window.cancelAnimationFrame = cancel;
        }
        if (pending.size) throw Error("Native frame request survived stop");
    })()""")


def check_physics_scene(devtools: DevToolsSocket, artifact: Path, backend: str) -> dict:
    with offline_page(devtools, artifact) as url:
        url += f"?backend={backend}"
        devtools.call("Page.navigate", {"url": url})
        def wait_for_preview(state="ready"):
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if evaluate(devtools, f"location.href === {json.dumps(url)} && "
                            f"globalThis.__terminViewer?.host.state === {json.dumps(state)} && "
                            "document.getElementById('status').hidden && document.getElementById('reset').disabled"):
                    return
                time.sleep(0.05)
            raise RuntimeError(f"Physics scene did not reach its suspended preview: {console_diagnostics(devtools)}")

        wait_for_preview()
        check_native_animation_loop(devtools)
        if evaluate(devtools, "__terminViewer.host.graphicsBackend") != backend:
            raise RuntimeError(f"Physics scene failed to select {backend}")

        def tick(dt):
            evaluate(devtools, f"""(() => {{
                const mod = __terminViewer.core.module;
                if (!mod._termin_web_host_tick({dt}))
                    throw Error(mod.UTF8ToString(mod._termin_web_host_error()));
            }})()""")

        def ball_height():
            # The camera is horizontal, six units from the centre line, with a
            # fixed 40 degree vertical field of view.
            row = evaluate(devtools, """(() => {
                const {host} = __terminViewer;
                const canvas = document.querySelector('canvas');
                const hits = [];
                for (let i = 0; i < 80; ++i) {
                    const y = (i + 0.5) / 80;
                    if (host.pickEntity(canvas.width / 2, y * canvas.height) === "drop-ball") hits.push(y);
                }
                if (!hits.length) throw Error("Falling rigid body disappeared");
                return (hits[0] + hits[hits.length - 1]) / 2;
            })()""")
            return (0.5 - row) * 12 * math.tan(math.radians(20))

        def height_after(dt):
            tick(dt)
            return ball_height()

        def frame_probes():
            _, png = chart_screenshot(devtools)
            w, h, channels, rows = decode_png(png)
            scale = h / (12 * math.tan(math.radians(20)))  # pixels per world unit at y = 0

            def rgb_at(world_x, world_z):
                x, y = round(w / 2 + world_x * scale), round(h / 2 - world_z * scale)
                return [
                    round(sum(rows[row][col * channels + c]
                              for row in range(y - 1, y + 2) for col in range(x - 1, x + 2)) / 9, 1)
                    for c in range(3)
                ]

            # The key's rays travel in (+0.48, 0, -1). Project the initial umbra
            # onto the top face at z = -1.03, and mirror it for a lit control.
            shadow_x = (1.05 + 1.03) * 0.48
            # At the camera target, an 8x8 patch contains only the solid sky.
            # Early UNORM8 quantization can make this dark area dither visibly.
            for c in range(3):
                sky = [rows[y][x * channels + c]
                       for y in range(h // 2 - 4, h // 2 + 4) for x in range(w // 2 - 4, w // 2 + 4)]
                if max(sky) - min(sky) > 2:
                    raise RuntimeError(f"Nonuniform sky on {backend}: channel {c} ranges from {min(sky)} to {max(sky)}")
            return {"ball": rgb_at(0, 1.05), "shadow": rgb_at(shadow_x, -1.03), "lit": rgb_at(-shadow_x, -1.03)}

        def key_contribution(lit):
            # Measure only the directional light. The emissive ball also has a
            # moving point light which changes the platform colour during the drop.
            evaluate(devtools, "__terminViewer.host.setLightEnabled('key-light', false)")
            tick(0)
            unlit = frame_probes()
            evaluate(devtools, "__terminViewer.host.setLightEnabled('key-light', true)")
            tick(0)
            return [round(lit[p][2] - unlit[p][2], 1) for p in ("shadow", "lit")]

        initial = height_after(0)
        before = frame_probes()
        # Viewed head-on, the lit demo material emits linear RGB (1, .34, .05) + .24.
        # With the default ACES filmic curve at unit exposure and one sRGB encoding
        # this gives (237, 213, 175) on the displayed canvas.
        expected = [aces_to_srgb8(c + 0.24) for c in (1.0, 0.34, 0.05)]
        if max(abs(a - b) for a, b in zip(before["ball"], expected, strict=True)) > 4:
            raise RuntimeError(f"Wrong displayed ball colour on {backend}: {before['ball']}, expected sRGB {expected}")
        initial_key = key_contribution(before)
        bounds, png = chart_screenshot(devtools)
        w, h, channels, rows = decode_png(png)
        # Count bright lettering inside the native release button, excluding its border.
        sx, sy = w / bounds["width"], h / bounds["height"]
        label_ink = sum(min(row[i:i+3]) > 155 for row in rows[round(20*sy):round(48*sy)]
                        for i in range(round(18*sx)*channels, round(153*sx)*channels, channels))
        if label_ink < 30:
            raise RuntimeError(f"Missing native release caption on {backend}: {label_ink} bright pixels")
        release = (bounds["x"] + 86, bounds["y"] + 34)

        # A ball reset must preserve the loaded package and its input subscriptions.
        evaluate(devtools, """(() => {
            globalThis.physicsMetrics = __terminViewer.host.metrics;
            globalThis.hudClicks = 0;
            __terminViewer.host.onUiButtonClick('physics-hud', 'release', () => ++globalThis.hudClicks);
        })()""")
        dispatch_gesture(devtools, False, release)
        evaluate(devtools, """(() => {
            if (__terminViewer.host.state !== 'running' || document.getElementById('reset').disabled)
                throw Error('Native release button did not start physics and enable the HTML reset');
            __terminViewer.host.stop();
        })()""")
        falling = height_after(0.35)
        contact = height_after(0.25)
        rebound = height_after(0.30)
        resting = [height_after(1.0) for _ in range(5)]
        settled = resting[-1]
        after = frame_probes()
        settled_key = key_contribution(after)
        if not (abs(initial - 1.05) < 0.1 and initial - falling > 0.3 and
                contact < falling - 0.5 and rebound > contact + 0.12 and
                abs(resting[-2] - settled) < 0.06 and abs(settled + 0.67) < 0.12):
            raise RuntimeError(f"Unexpected drop heights on {backend}: {initial}, {falling}, {contact}, {rebound}, {settled}")
        if max(abs(a - b) for a, b in zip(before["ball"], after["ball"], strict=True)) < 35:
            raise RuntimeError(f"Ball moved without updating its rendered pixels: {before} -> {after}")
        # The suspended ball blocks the key at +x. When it lands, the same
        # patch must receive direct light again. The -x control stays lit.
        if (min(initial_key[1], settled_key[1]) < 24 or initial_key[0] > 0.35 * initial_key[1]
                or settled_key[0] < 0.65 * settled_key[1]):
            raise RuntimeError(f"Unexpected cast shadow on {backend}: key contribution at "
                               f"[initial shadow, lit control] = {initial_key} -> {settled_key}")
        dispatch_gesture(devtools, False, release)
        if evaluate(devtools, "hudClicks") != 1:
            raise RuntimeError(f"Release button still accepts clicks after the drop on {backend}")
        reset = evaluate(devtools, """(() => {
            const r = document.getElementById('reset').getBoundingClientRect();
            return [r.x + r.width/2, r.y + r.height/2];
        })()""")
        devtools.call("Emulation.setTouchEmulationEnabled", {"enabled": True})
        def wait_for_live_drop():
            deadline = time.monotonic() + 5
            while initial - ball_height() < 0.3:
                if time.monotonic() >= deadline:
                    raise RuntimeError(f"Native release did not start live physics on {backend}")
                time.sleep(0.04)

        try:
            dispatch_gesture(devtools, True, reset)
            wait_for_preview("stopped")
            restarted = height_after(0)
            if abs(initial - restarted) > 0.12:
                raise RuntimeError(f"HTML reset did not suspend the ball on {backend}: {restarted}")
            # Reset successive drops while the browser frame loop is still active.
            for expected_clicks in (2, 3, 4):
                dispatch_gesture(devtools, True, release)
                wait_for_live_drop()
                if evaluate(devtools, "hudClicks") != expected_clicks:
                    raise RuntimeError(f"UI listener was lost or duplicated on {backend}")
                dispatch_gesture(devtools, True, reset)
                wait_for_preview("stopped")
                if abs(ball_height() - initial) > 0.12 or not evaluate(
                        devtools, "physicsMetrics === __terminViewer.host.metrics"):
                    raise RuntimeError(f"Ball reset during live physics failed or reloaded the package on {backend}")

            devtools.call("Page.reload", {"ignoreCache": True})
            wait_for_preview()
            if abs(ball_height() - initial) > 0.12:
                raise RuntimeError(f"Reload did not restore the suspended ball on {backend}")
            dispatch_gesture(devtools, True, release)
            wait_for_live_drop()
            dispatch_gesture(devtools, True, reset)
            wait_for_preview("stopped")
            if abs(ball_height() - initial) > 0.12:
                raise RuntimeError(f"First reset after reload failed on {backend}")
        finally:
            devtools.call("Emulation.setTouchEmulationEnabled", {"enabled": False})
        return {"initial": initial, "falling": falling, "contact": contact, "rebound": rebound,
                "settled": settled, "restarted": restarted, "initial_key_blue": initial_key,
                "settled_key_blue": settled_key, "initial_srgb": before, "release_label_pixels": label_ink}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Termin Web core browser smoke test")
    parser.add_argument("output_directory")
    parser.add_argument(
        "--report",
        help="write the machine-readable gate report (default: OUTPUT/browser-gate-report.json)",
    )
    args = parser.parse_args()

    report_path = args.report or os.environ.get("TERMIN_WEB_GATE_REPORT") or \
        os.path.join(args.output_directory, "browser-gate-report.json")
    started_at = time.monotonic()
    report = {
        "schema_version": 1,
        "status": "running",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "platform_gate": "chromium",
        "artifacts": artifact_measurements(args.output_directory),
    }

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=args.output_directory)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    browser = None
    devtools = None
    stderr = ""
    failure = None
    try:
        page_url = f"http://127.0.0.1:{server.server_port}/smoke.html"
        debug_port = available_port()
        with tempfile.TemporaryDirectory(prefix="termin-web-chrome-") as profile:
            browser = subprocess.Popen(
                [
                    find_browser(),
                    "--disable-background-timer-throttling",
                    "--disable-backgrounding-occluded-windows",
                    "--disable-renderer-backgrounding",
                    "--no-first-run",
                    "--disable-default-apps",
                    "--enable-unsafe-webgpu",
                    "--enable-unsafe-swiftshader",
                    "--use-webgpu-adapter=swiftshader",
                    "--enable-dawn-features=allow_unsafe_apis",
                    "--disable-dawn-features=use_dxc",
                    "--enable-webgpu-developer-features",
                    "--use-gpu-in-tests",
                    "--enable-accelerated-2d-canvas",
                    "--no-sandbox",
                    "--remote-allow-origins=*",
                    f"--remote-debugging-port={debug_port}",
                    f"--user-data-dir={profile}",
                    page_url,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
            target = wait_for_page(debug_port, page_url)
            devtools = DevToolsSocket(target["webSocketDebuggerUrl"])
            devtools.call("Runtime.enable")
            devtools.call("Page.enable")
            report["browser"] = devtools.call("Browser.getVersion")
            result = wait_for_result(devtools)
            report["environment"] = json.loads(devtools.call(
                "Runtime.evaluate", {
                    "expression": "JSON.stringify({userAgent:navigator.userAgent,platform:navigator.platform,secureContext:isSecureContext,crossOriginIsolated,webGpu:Boolean(navigator.gpu),hardwareConcurrency:navigator.hardwareConcurrency ?? null})",
                    "returnByValue": True,
                }).get("result", {}).get("value", "{}"))
            if not report["environment"].get("secureContext") or \
                    not report["environment"].get("webGpu"):
                raise RuntimeError(
                    "browser gate page did not expose secure-context WebGPU: "
                    f"{report['environment']}")
            if result == FRAME_READY_MARKER:
                screenshot = devtools.call("Page.captureScreenshot", {
                    "format": "png",
                    "clip": {"x": 0, "y": 0, "width": 640, "height": 360, "scale": 1},
                    "captureBeyondViewport": False,
                })
                frame_metrics = analyze_png(base64.b64decode(screenshot["data"]))
                if (frame_metrics["width"], frame_metrics["height"]) != (640, 360) or \
                        frame_metrics["bright_pixels"] < 100 or \
                        frame_metrics["quantized_colors"] < 3:
                    raise RuntimeError(
                        "packaged scene did not produce a visible textured frame: "
                        f"{frame_metrics}; console={console_diagnostics(devtools)}"
                    )
                events_before = evaluate(devtools, "__terminSmokeInput.metrics.events")
                devtools.call("Input.dispatchMouseEvent", {
                    "type": "mousePressed", "x": 320, "y": 180,
                    "button": "left", "buttons": 1, "clickCount": 1,
                })
                devtools.call("Input.dispatchMouseEvent", {
                    "type": "mouseMoved", "x": 410, "y": 225,
                    "button": "left", "buttons": 1,
                })
                devtools.call("Input.dispatchMouseEvent", {
                    "type": "mouseReleased", "x": 410, "y": 225,
                    "button": "left", "buttons": 0, "clickCount": 1,
                })
                devtools.call("Input.dispatchMouseEvent", {
                    "type": "mouseWheel", "x": 410, "y": 225,
                    "deltaX": 0, "deltaY": -100,
                })
                devtools.call("Input.dispatchKeyEvent", {
                    "type": "keyDown", "key": "a", "code": "KeyA", "text": "a",
                    "windowsVirtualKeyCode": 65, "nativeVirtualKeyCode": 65,
                })
                devtools.call("Input.dispatchKeyEvent", {
                    "type": "keyUp", "key": "a", "code": "KeyA",
                    "windowsVirtualKeyCode": 65, "nativeVirtualKeyCode": 65,
                })
                time.sleep(0.25)
                moved_screenshot = devtools.call("Page.captureScreenshot", {
                    "format": "png",
                    "clip": {"x": 0, "y": 0, "width": 640, "height": 360, "scale": 1},
                    "captureBeyondViewport": False,
                })
                moved_metrics = analyze_png(base64.b64decode(moved_screenshot["data"]))
                if moved_metrics["pixel_sha256"] == frame_metrics["pixel_sha256"]:
                    raise RuntimeError(
                        "packaged orbit camera did not change the rendered frame; "
                        f"input={devtools.call('Runtime.evaluate', {'expression': 'JSON.stringify(globalThis.__terminSmokeInput?.metrics)', 'returnByValue': True})}"
                    )
                resize_result = devtools.call("Runtime.evaluate", {
                    "expression": "(() => { const c=document.querySelector('#termin-canvas'); c.style.width='800px'; c.style.height='450px'; globalThis.__terminSmokeInput.syncCanvasSize(); return JSON.stringify({width:c.width,height:c.height,metrics:globalThis.__terminSmokeInput.metrics}); })()",
                    "returnByValue": True,
                }).get("result", {}).get("value", "")
                resize_data = json.loads(resize_result)
                # Three mouse events, a wheel, two keys and the resize reach the runtime.
                if resize_data["width"] < 800 or resize_data["height"] < 450 or \
                        resize_data["metrics"]["events"] - events_before < 7 or \
                        resize_data["metrics"]["resizes"] < 1:
                    raise RuntimeError(
                        f"browser input/resize adapter did not report expected activity: {resize_data}"
                    )
                devtools.call("Runtime.evaluate", {
                    "expression": "(() => { const c=document.querySelector('#termin-canvas'); c.blur(); c.style.width='640px'; c.style.height='360px'; globalThis.__terminSmokeInput.syncCanvasSize(); c.focus(); return true; })()",
                    "returnByValue": True,
                })
                devtools.call("Runtime.evaluate", {
                    "expression": "document.querySelector('#result').textContent='TERMIN_WEB_CORE_SMOKE_RUNNING'; globalThis.__terminSmokeContinue(); 'continued'",
                    "returnByValue": True,
                })
                result = wait_for_result(devtools)
            if result == TEXTURE_OPS_READY_MARKER:
                texture_ops_screenshot = devtools.call("Page.captureScreenshot", {
                    "format": "png",
                    "clip": {"x": 0, "y": 0, "width": 640, "height": 360, "scale": 1},
                    "captureBeyondViewport": False,
                })
                texture_ops_metrics = analyze_png(
                    base64.b64decode(texture_ops_screenshot["data"]),
                    {
                        "background": (10, 340),
                        "cropped_red": (40, 40),
                        "scaled_red": (160, 100),
                        "scaled_yellow": (480, 100),
                        "scaled_blue": (160, 260),
                        "scaled_white": (480, 260),
                        "partial_clear": (320, 180),
                    },
                )
                probes = texture_ops_metrics["probes"]
                expected = {
                    "cropped_red": lambda r, g, b: r > 170 and g < 100 and b < 100,
                    "scaled_red": lambda r, g, b: r > 170 and g < 100 and b < 100,
                    "scaled_yellow": lambda r, g, b: r > 170 and g > 150 and b < 120,
                    "scaled_blue": lambda r, g, b: r < 100 and g < 120 and b > 160,
                    "scaled_white": lambda r, g, b: r > 170 and g > 170 and b > 170,
                    "partial_clear": lambda r, g, b: r < 100 and g > 160 and b < 120,
                    "background": lambda r, g, b: max(r, g, b) < 80,
                }
                failed_probes = [
                    name for name, predicate in expected.items()
                    if not predicate(*probes[name])
                ]
                if failed_probes:
                    raise RuntimeError(
                        "WebGPU cropped/scaled blit or partial clear pixel probes failed: "
                        f"failed={failed_probes} metrics={texture_ops_metrics}; "
                        f"console={console_diagnostics(devtools)}"
                    )
                report["texture_ops"] = texture_ops_metrics
                devtools.call("Runtime.evaluate", {
                    "expression": "document.querySelector('#result').textContent='TERMIN_WEB_CORE_SMOKE_RUNNING'; globalThis.__terminTextureOpsContinue(); 'continued'",
                    "returnByValue": True,
                })
                result = wait_for_result(devtools)
            if result != SUCCESS_MARKER:
                diagnostics = devtools.call("Runtime.evaluate", {
                    "expression": "JSON.stringify({hostStatus:document.querySelector('#host-status')?.textContent,frame:globalThis.__terminSmokeFrame,asyncError:globalThis.__terminSmokeAsyncError,hostError:globalThis.__terminSmokeModule?globalThis.__terminSmokeModule.UTF8ToString(globalThis.__terminSmokeModule._termin_web_host_error()):'',graphicsStatus:globalThis.__terminSmokeModule?._termin_web_host_graphics_status?.(),graphicsError:globalThis.__terminSmokeModule?globalThis.__terminSmokeModule.UTF8ToString(globalThis.__terminSmokeModule._termin_web_host_graphics_error()):''})",
                    "returnByValue": True,
                }).get("result", {}).get("value", "")
                raise RuntimeError(
                    f"Browser smoke failed: {result}; {diagnostics}; "
                    f"console={console_diagnostics(devtools)}")

            smoke_state = json.loads(devtools.call("Runtime.evaluate", {
                "expression": "JSON.stringify({frame:globalThis.__terminSmokeFrame,inputMetrics:globalThis.__terminSmokeInput?.metrics ?? null})",
                "returnByValue": True,
            }).get("result", {}).get("value", "{}"))
            package_metrics = (smoke_state.get("frame") or {}).get("metrics") or {}
            if package_metrics.get("packageProvider") != "blob" or \
                    package_metrics.get("packageRequests") != 1 or \
                    package_metrics.get("packageBytes", 0) <= 0:
                raise RuntimeError(
                    "browser host did not use the single-blob package provider: "
                    f"{package_metrics}"
                )
            report["smoke"] = {
                "frame": smoke_state.get("frame"),
                "input_metrics": smoke_state.get("inputMetrics"),
                "initial_frame": frame_metrics,
                "moved_frame": moved_metrics,
                "resize": resize_data,
            }

            viewer_url = f"http://127.0.0.1:{server.server_port}/viewer.html"
            navigate_to_viewer(devtools, viewer_url)
            devtools.call("Runtime.evaluate", {
                "expression": "document.querySelectorAll('.panel').forEach((element) => { element.style.visibility = 'hidden'; }); true",
                "returnByValue": True,
            })
            before = devtools.call("Page.captureScreenshot", {"format": "png"})
            before_metrics = analyze_png(base64.b64decode(before["data"]))
            devtools.call("Input.dispatchMouseEvent", {
                "type": "mousePressed", "x": 320, "y": 180,
                "button": "left", "buttons": 1, "clickCount": 1,
            })
            devtools.call("Input.dispatchMouseEvent", {
                "type": "mouseMoved", "x": 430, "y": 240,
                "button": "left", "buttons": 1,
            })
            devtools.call("Input.dispatchMouseEvent", {
                "type": "mouseReleased", "x": 430, "y": 240,
                "button": "left", "buttons": 0, "clickCount": 1,
            })
            time.sleep(0.25)
            after = devtools.call("Page.captureScreenshot", {"format": "png"})
            after_metrics = analyze_png(base64.b64decode(after["data"]))
            viewer_state = wait_for_viewer(devtools)
            if after_metrics["pixel_sha256"] == before_metrics["pixel_sha256"]:
                raise RuntimeError(
                    "viewer orbit gesture did not change the rendered frame: "
                    f"{viewer_state}; console={console_diagnostics(devtools)}"
                )
            report["viewer"] = {
                "state": viewer_state,
                "before_frame": before_metrics,
                "after_frame": after_metrics,
            }

            devtools.call("Emulation.setDeviceMetricsOverride", {
                "width": 960,
                "height": 700,
                "deviceScaleFactor": 1,
                "mobile": False,
            })
            visual_scene_url = f"http://127.0.0.1:{server.server_port}/visual-scene.html"
            devtools.call("Page.navigate", {"url": visual_scene_url})
            wait_for_visual_scene_example(devtools)
            time.sleep(0.25)
            visual_scene_state = wait_for_visual_scene_example(devtools)
            visual_scene_screenshot = devtools.call("Page.captureScreenshot", {
                "format": "png",
                "clip": {"x": 0, "y": 0, "width": 960, "height": 600, "scale": 1},
                "captureBeyondViewport": False,
            })
            visual_scene_png = base64.b64decode(visual_scene_screenshot["data"])
            visual_scene_metrics = analyze_png(
                visual_scene_png,
                {
                    "background": (20, 20),
                    "header": (100, 100),
                    "panel": (820, 250),
                    "orbit_center": (248, 316),
                    "star_center": (520, 305),
                    "chart_line": (670, 350),
                    "chart_line_alt": (650, 405),
                    "action": (720, 440),
                    "action_center": (770, 446),
                    "action_right": (820, 446),
                },
            )
            probes = visual_scene_metrics["probes"]
            expected_visual_scene = {
                "background": lambda r, g, b: max(r, g, b) < 70,
                "header": lambda r, g, b: b > 130 and g > 90 and r < 100,
                "panel": lambda r, g, b: b > r and b > g and max(r, g, b) < 150,
                "orbit_center": lambda r, g, b: r > 150 and g > 90 and b < 100,
                "star_center": lambda r, g, b: r > 150 and g > 90 and b < 100,
            }
            failed_visual_scene_probes = [
                name for name, predicate in expected_visual_scene.items()
                if not predicate(*probes[name])
            ]
            chart_predicate = lambda rgb: rgb[1] > 150 and rgb[0] < 130 and rgb[2] < 150
            if not chart_predicate(probes["chart_line"]) and not chart_predicate(probes["chart_line_alt"]):
                failed_visual_scene_probes.append("chart_line")
            action_predicate = lambda rgb: rgb[0] > 150 and rgb[1] < 130 and rgb[2] < 100
            if not any(action_predicate(probes[name]) for name in ("action", "action_center", "action_right")):
                failed_visual_scene_probes.append("action")
            if failed_visual_scene_probes or visual_scene_metrics["quantized_colors"] < 7:
                failure_path = Path(args.output_directory) / "visual-scene-webgpu-failure.png"
                failure_path.write_bytes(visual_scene_png)
                raise RuntimeError(
                    "VisualScene2D WebGPU pixel probes failed: "
                    f"failed={failed_visual_scene_probes} metrics={visual_scene_metrics}; "
                    f"screenshot={failure_path}; "
                    f"state={visual_scene_state}; console={console_diagnostics(devtools)}"
                )
            report["visual_scene"] = {
                "state": visual_scene_state,
                "frame": visual_scene_metrics,
            }
            chart_url = f"http://127.0.0.1:{server.server_port}/chart2d.html"
            report["retained_chart2d"] = {}
            for backend in ("webgpu", "webgl2"):
                report["retained_chart2d"][backend] = check_chart(devtools, chart_url, backend)
            chart3d_url = f"http://127.0.0.1:{server.server_port}/chart3d.html"
            report["retained_chart3d"] = {}
            for backend in ("webgpu", "webgl2"):
                report["retained_chart3d"][backend] = check_chart3d(devtools, chart3d_url, backend)
            report["standalone_chart3d"] = check_standalone_chart3d(
                devtools, Path(args.output_directory) / "Termin-Chart3D.html")
            interactive = Path(args.output_directory) / "Termin-InteractiveScene.html"
            ui = Path(args.output_directory) / "Termin-UiScene.html"
            report["ui_scene"] = {
                backend: check_ui_scene(devtools, ui, backend) for backend in ("webgpu", "webgl2")
            }
            report["interactive_scene"] = {
                backend: check_interactive_scene(devtools, interactive, backend, touch=backend == "webgl2")
                for backend in ("webgpu", "webgl2")
            }
            physics = Path(args.output_directory) / "Termin-PhysicsScene.html"
            report["physics_scene"] = {
                backend: check_physics_scene(devtools, physics, backend) for backend in ("webgpu", "webgl2")
            }
            gpu, gl = (report["physics_scene"][b]["initial_srgb"] for b in ("webgpu", "webgl2"))
            for patch in gpu:
                if max(abs(a - b) for a, b in zip(gpu[patch], gl[patch], strict=True)) > 4:
                    raise RuntimeError(f"Displayed {patch} colours differ: WebGPU {gpu[patch]}, WebGL2 {gl[patch]}")
    except Exception as error:
        failure = error
    finally:
        if devtools is not None:
            devtools.close()
        if browser is not None:
            browser.terminate()
            try:
                _, stderr = browser.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                browser.kill()
                _, stderr = browser.communicate()
        server.shutdown()
        thread.join()
        server.server_close()

    if failure is not None:
        details = f"{failure}"
        if stderr:
            details += f"\nChrome stderr:\n{stderr}"
        report["status"] = "failed"
        report["duration_ms"] = round((time.monotonic() - started_at) * 1000, 3)
        report["error"] = str(failure)
        report["chrome_stderr"] = stderr
        write_report(report_path, report)
        raise RuntimeError(details) from failure
    report["status"] = "passed"
    report["duration_ms"] = round((time.monotonic() - started_at) * 1000, 3)
    write_report(report_path, report)
    print(SUCCESS_MARKER)
    print(f"TERMIN_WEB_GATE_REPORT={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
