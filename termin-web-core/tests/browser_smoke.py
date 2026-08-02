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
from urllib.parse import urlparse


SUCCESS_MARKER = "TERMIN_WEB_CORE_SMOKE_PASSED"
FAILURE_MARKER = "TERMIN_WEB_CORE_SMOKE_FAILED"


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
        if value == SUCCESS_MARKER or value.startswith(FAILURE_MARKER):
            return value
        time.sleep(0.05)
    diagnostics = devtools.call("Runtime.evaluate", {
        "expression": "JSON.stringify({result: document.querySelector('#result')?.textContent, gpu: Boolean(navigator.gpu), asyncError: globalThis.__terminSmokeAsyncError, renderStatus: globalThis.__terminSmokeModule?._termin_web_render_smoke_status?.(), renderError: globalThis.__terminSmokeModule?globalThis.__terminSmokeModule.UTF8ToString(globalThis.__terminSmokeModule._termin_web_render_smoke_error()):''})",
        "returnByValue": True,
    }).get("result", {}).get("value", "")
    raise RuntimeError(
        f"browser smoke page did not publish a terminal result: {diagnostics}"
    )


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
                    "--disable-vulkan-surface",
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
            if result != SUCCESS_MARKER:
                raise RuntimeError(f"Browser smoke failed: {result}")
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
