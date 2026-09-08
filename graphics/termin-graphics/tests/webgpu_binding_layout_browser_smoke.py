#!/usr/bin/env python3
import argparse
import base64
import functools
import http.server
import json
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "platform/termin-web-core/tests"))

from browser_smoke import (  # noqa: E402
    DevToolsSocket,
    analyze_png,
    available_port,
    console_diagnostics,
    find_browser,
    wait_for_page,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the tgfx2 WebGPU binding-layout browser fixture")
    parser.add_argument("output_directory")
    parser.add_argument("--report")
    args = parser.parse_args()
    output = Path(args.output_directory).resolve()
    page_url_path = "tgfx2-webgpu-binding-layout-fixture.html"
    required = [
        output / page_url_path,
        output / "tgfx2_webgpu_binding_layout_fixture.mjs",
        output / "tgfx2_webgpu_binding_layout_fixture.wasm",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(f"missing WebGPU binding-layout fixture artifacts: {missing}")

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=output)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    browser = None
    devtools = None
    report = {"schema_version": 1, "status": "running", "fixture": "tgfx2-webgpu-binding-layout"}
    try:
        page_url = f"http://127.0.0.1:{server.server_port}/{page_url_path}"
        debug_port = available_port()
        with tempfile.TemporaryDirectory(prefix="tgfx2-webgpu-layout-chrome-") as profile:
            browser_path = find_browser()
            browser_version = subprocess.run(
                [browser_path, "--version"], text=True, capture_output=True, check=False, timeout=10
            )
            if browser_version.returncode != 0:
                details = (browser_version.stderr or browser_version.stdout).strip()
                raise RuntimeError(f"Chromium executable is unavailable: {browser_path}: {details}")
            browser = subprocess.Popen(
                [
                    browser_path,
                    "--no-first-run",
                    "--disable-default-apps",
                    "--enable-unsafe-webgpu",
                    "--use-webgpu-adapter=swiftshader",
                    "--enable-dawn-features=allow_unsafe_apis",
                    "--disable-dawn-features=use_dxc",
                    "--enable-webgpu-developer-features",
                    "--use-gpu-in-tests",
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
            deadline = time.monotonic() + 30.0
            result = ""
            while time.monotonic() < deadline:
                result = devtools.call(
                    "Runtime.evaluate",
                    {"expression": "document.querySelector('#result')?.textContent ?? ''", "returnByValue": True},
                ).get("result", {}).get("value", "")
                if result == "TERMIN_WEBGPU_BINDING_LAYOUT_READY" or result.startswith("ERROR:"):
                    break
                time.sleep(0.05)
            if result != "TERMIN_WEBGPU_BINDING_LAYOUT_READY":
                raise RuntimeError(
                    f"WebGPU binding-layout fixture failed: {result!r}; console={console_diagnostics(devtools)}"
                )
            screenshot = devtools.call(
                "Page.captureScreenshot",
                {"format": "png", "clip": {"x": 0, "y": 0, "width": 320, "height": 320, "scale": 1}},
            )
            metrics = analyze_png(base64.b64decode(screenshot["data"]))
            if metrics["bright_pixels"] < 1000 or metrics["quantized_colors"] < 4:
                raise RuntimeError(f"binding-layout draws are not visible: {metrics}")
            report.update({"status": "passed", "frame": metrics})
    except Exception as error:
        report.update({"status": "failed", "error": str(error)})
        raise
    finally:
        if devtools is not None:
            devtools.close()
        if browser is not None:
            browser.terminate()
            try:
                browser.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                browser.kill()
                browser.communicate()
        server.shutdown()
        server.server_close()
        if args.report:
            destination = Path(args.report)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
