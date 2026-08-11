#!/usr/bin/env python3
import argparse
import base64
import functools
import gzip
import hashlib
import http.server
import json
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


def wait_for_page(debug_port: int, page_url: str, timeout: float = 10.0) -> dict:
    deadline = time.monotonic() + timeout
    endpoint = f"http://127.0.0.1:{debug_port}/json"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(endpoint, timeout=1) as response:
                targets = json.load(response)
            for target in targets:
                if target.get("type") == "page" and target.get("url") == page_url:
                    return target
        except (OSError, ValueError):
            pass
        time.sleep(0.05)
    raise RuntimeError("Chrome DevTools did not expose the smoke page")


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


def wait_for_viewer(devtools: DevToolsSocket, timeout: float = 30.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = devtools.call("Runtime.evaluate", {
            "expression": "JSON.stringify({state:globalThis.__terminViewer?.host?.state ?? '',error:document.querySelector('#error')?.textContent ?? '',frames:globalThis.__terminViewer?.host?.frameCount?.() ?? 0,hostMetrics:globalThis.__terminViewer?.host?.metrics ?? null,inputMetrics:globalThis.__terminViewer?.input?.metrics ?? null})",
            "returnByValue": True,
        }).get("result", {}).get("value", "")
        if result:
            state = json.loads(result)
            if state["state"] == "running" and state["frames"] >= 2:
                return state
            if state["state"] == "error":
                raise RuntimeError(f"viewer entered error state: {state}")
        time.sleep(0.05)
    raise RuntimeError("viewer did not reach running state")


def wait_for_visual_scene_example(devtools: DevToolsSocket, timeout: float = 30.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = devtools.call("Runtime.evaluate", {
            "expression": "JSON.stringify(globalThis.__terminVisualSceneExample ? {status:globalThis.__terminVisualSceneExample.status,error:globalThis.__terminVisualSceneExample.error ?? ''} : null)",
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


def analyze_png(
    content: bytes,
    probes: dict[str, tuple[int, int]] | None = None,
) -> dict:
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
                    "--headless",
                    "--disable-background-timer-throttling",
                    "--disable-backgrounding-occluded-windows",
                    "--disable-renderer-backgrounding",
                    "--enable-unsafe-webgpu",
                    "--enable-features=Vulkan",
                    "--enable-dawn-features=allow_unsafe_apis",
                    "--use-angle=swiftshader",
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
                if resize_data["width"] < 800 or resize_data["height"] < 450 or \
                        resize_data["metrics"]["events"] < 10 or \
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
            devtools.call("Page.navigate", {"url": viewer_url})
            wait_for_viewer(devtools)
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
            visual_scene_metrics = analyze_png(
                base64.b64decode(visual_scene_screenshot["data"]),
                {
                    "background": (20, 20),
                    "header": (100, 100),
                    "panel": (820, 250),
                    "orbit_center": (248, 316),
                    "star_center": (520, 305),
                    "chart_line": (670, 350),
                    "action": (720, 440),
                },
            )
            probes = visual_scene_metrics["probes"]
            expected_visual_scene = {
                "background": lambda r, g, b: max(r, g, b) < 70,
                "header": lambda r, g, b: b > 130 and g > 90 and r < 100,
                "panel": lambda r, g, b: b > r and b > g and max(r, g, b) < 150,
                "orbit_center": lambda r, g, b: r > 150 and g > 90 and b < 100,
                "star_center": lambda r, g, b: r > 150 and g > 90 and b < 100,
                "chart_line": lambda r, g, b: g > 150 and r < 130 and b < 150,
                "action": lambda r, g, b: r > 150 and g < 130 and b < 100,
            }
            failed_visual_scene_probes = [
                name for name, predicate in expected_visual_scene.items()
                if not predicate(*probes[name])
            ]
            if failed_visual_scene_probes or visual_scene_metrics["quantized_colors"] < 7:
                raise RuntimeError(
                    "VisualScene2D WebGPU pixel probes failed: "
                    f"failed={failed_visual_scene_probes} metrics={visual_scene_metrics}; "
                    f"state={visual_scene_state}; console={console_diagnostics(devtools)}"
                )
            report["visual_scene"] = {
                "state": visual_scene_state,
                "frame": visual_scene_metrics,
            }
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
