#!/usr/bin/env python3
import argparse
import base64
import functools
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
from urllib.parse import urlparse


SUCCESS_MARKER = "TERMIN_WEB_CORE_SMOKE_PASSED"
FAILURE_MARKER = "TERMIN_WEB_CORE_SMOKE_FAILED"
FRAME_READY_MARKER = "TERMIN_WEB_CORE_FRAME_READY"


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
        if value in (SUCCESS_MARKER, FRAME_READY_MARKER) or value.startswith(FAILURE_MARKER):
            return value
        time.sleep(0.05)
    diagnostics = devtools.call("Runtime.evaluate", {
        "expression": "JSON.stringify({result: document.querySelector('#result')?.textContent, gpu: Boolean(navigator.gpu), asyncError: globalThis.__terminSmokeAsyncError, renderStatus: globalThis.__terminSmokeModule?._termin_web_render_smoke_status?.(), renderError: globalThis.__terminSmokeModule?globalThis.__terminSmokeModule.UTF8ToString(globalThis.__terminSmokeModule._termin_web_render_smoke_error()):''})",
        "returnByValue": True,
    }).get("result", {}).get("value", "")
    raise RuntimeError(
        f"browser smoke page did not publish a terminal result: {diagnostics}"
    )


def analyze_png(content: bytes) -> dict[str, int]:
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
    for row in rows:
        for offset in range(0, len(row), channels):
            red, green, blue = row[offset:offset + 3]
            if max(red, green, blue) > 120:
                bright_pixels += 1
            for index, value in enumerate((red, green, blue)):
                channel_min[index] = min(channel_min[index], value)
                channel_max[index] = max(channel_max[index], value)
            colors.add((red >> 4, green >> 4, blue >> 4))
    return {
        "width": width,
        "height": height,
        "bright_pixels": bright_pixels,
        "quantized_colors": len(colors),
        "channel_min": channel_min,
        "channel_max": channel_max,
    }


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
    args = parser.parse_args()

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
            result = wait_for_result(devtools)
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
                devtools.call("Runtime.evaluate", {
                    "expression": "document.querySelector('#result').textContent='TERMIN_WEB_CORE_SMOKE_RUNNING'; globalThis.__terminSmokeContinue(); 'continued'",
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
        raise RuntimeError(details) from failure
    print(SUCCESS_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
