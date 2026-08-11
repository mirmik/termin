#!/usr/bin/env python3

import argparse
import base64
import functools
import http.server
import json
import subprocess
import tempfile
import threading
import time

from browser_smoke import (
    DevToolsSocket,
    analyze_png,
    available_port,
    console_diagnostics,
    find_browser,
    wait_for_page,
    wait_for_visual_scene_example,
)


def validate_frame(metrics: dict) -> None:
    probes = metrics["probes"]
    expected = {
        "background": lambda r, g, b: max(r, g, b) < 70,
        "header": lambda r, g, b: b > 130 and g > 90 and r < 100,
        "panel": lambda r, g, b: b > r and b > g and max(r, g, b) < 150,
        "orbit_center": lambda r, g, b: r > 150 and g > 90 and b < 100,
        "star_center": lambda r, g, b: r > 150 and g > 90 and b < 100,
        "chart_line": lambda r, g, b: g > 150 and r < 130 and b < 150,
        "action": lambda r, g, b: r > 150 and g < 130 and b < 100,
    }
    failed = [name for name, predicate in expected.items() if not predicate(*probes[name])]
    if failed or metrics["quantized_colors"] < 7:
        raise RuntimeError(
            f"VisualScene2D WebGPU pixel probes failed: failed={failed} metrics={metrics}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Termin VisualScene2D browser smoke")
    parser.add_argument("output_directory")
    args = parser.parse_args()

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=args.output_directory)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    page_url = f"http://127.0.0.1:{server.server_port}/visual-scene.html"
    debug_port = available_port()
    browser = None
    devtools = None
    stderr = ""
    try:
        with tempfile.TemporaryDirectory(prefix="termin-visual-scene-chrome-") as profile:
            browser = subprocess.Popen(
                [
                    find_browser(),
                    "--headless",
                    "--enable-unsafe-webgpu",
                    "--enable-features=Vulkan",
                    "--enable-dawn-features=allow_unsafe_apis",
                    "--use-angle=swiftshader",
                    "--no-sandbox",
                    "--remote-allow-origins=*",
                    "--window-size=960,700",
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
            try:
                state = wait_for_visual_scene_example(devtools)
            except RuntimeError as error:
                raise RuntimeError(
                    f"{error}; console={console_diagnostics(devtools)}"
                ) from error
            time.sleep(0.25)
            state = wait_for_visual_scene_example(devtools)
            screenshot = devtools.call("Page.captureScreenshot", {
                "format": "png",
                "clip": {"x": 0, "y": 0, "width": 960, "height": 600, "scale": 1},
                "captureBeyondViewport": False,
            })
            metrics = analyze_png(
                base64.b64decode(screenshot["data"]),
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
            try:
                validate_frame(metrics)
            except RuntimeError as error:
                raise RuntimeError(
                    f"{error}; state={state}; console={console_diagnostics(devtools)}"
                ) from error
            print("TERMIN_WEB_VISUAL_SCENE_SMOKE_PASSED")
            print(json.dumps(metrics, sort_keys=True))
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
    if stderr and "ERROR" in stderr:
        print(stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
