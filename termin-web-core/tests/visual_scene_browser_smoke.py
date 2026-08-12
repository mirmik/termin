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
            f"VisualScene2D WebGL2 pixel probes failed: failed={failed} metrics={metrics}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Termin VisualScene2D browser smoke")
    parser.add_argument("output_directory")
    args = parser.parse_args()

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=args.output_directory)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    page_url = f"http://127.0.0.1:{server.server_port}/visual-scene.html?backend=auto"
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
                    "--use-gl=angle",
                    "--use-angle=swiftshader-webgl",
                    "--enable-unsafe-swiftshader",
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
            if state.get("backend") != "webgl2":
                raise RuntimeError(f"expected WebGL2 fallback, got state={state}")
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
            devtools.call("Runtime.evaluate", {
                "expression": "globalThis.__terminVisualSceneExample.host.start(); true",
                "returnByValue": True,
            })
            runtime_state = None
            deadline = time.monotonic() + 10.0
            while time.monotonic() < deadline:
                value = devtools.call("Runtime.evaluate", {
                    "expression": "JSON.stringify({state:globalThis.__terminVisualSceneExample.host.state,frames:globalThis.__terminVisualSceneExample.host.frameCount(),backend:globalThis.__terminVisualSceneExample.host.graphicsBackend,error:globalThis.__terminVisualSceneExample.host.error})",
                    "returnByValue": True,
                }).get("result", {}).get("value", "")
                runtime_state = json.loads(value) if value else None
                if runtime_state and runtime_state["state"] == "running" and runtime_state["frames"] >= 2:
                    break
                if runtime_state and runtime_state["state"] == "error":
                    raise RuntimeError(f"WebGL2 packaged runtime failed: {runtime_state}")
                time.sleep(0.05)
            else:
                raise RuntimeError(f"WebGL2 packaged runtime did not render: {runtime_state}")
            time.sleep(0.2)
            runtime_screenshot = devtools.call("Page.captureScreenshot", {
                "format": "png",
                "clip": {"x": 0, "y": 0, "width": 960, "height": 600, "scale": 1},
                "captureBeyondViewport": False,
            })
            runtime_metrics = analyze_png(base64.b64decode(runtime_screenshot["data"]))
            if runtime_metrics["bright_pixels"] < 100 or runtime_metrics["quantized_colors"] < 3:
                raise RuntimeError(
                    "WebGL2 packaged 3D runtime produced no visible frame: "
                    f"state={runtime_state} metrics={runtime_metrics}; "
                    f"console={console_diagnostics(devtools)}"
                )
            resized = devtools.call("Runtime.evaluate", {
                "expression": """
                    (() => {
                        const canvas = document.querySelector('#termin-canvas');
                        const before = globalThis.__terminVisualSceneExample.host.frameCount();
                        const ok = globalThis.__terminVisualSceneExample.core.module
                            ._termin_web_host_resize(800, 450);
                        return JSON.stringify({ok, width: canvas.width, height: canvas.height, before});
                    })()
                """,
                "returnByValue": True,
            }).get("result", {}).get("value", "")
            resize_state = json.loads(resized) if resized else None
            if not resize_state or resize_state["ok"] != 1 or \
                    resize_state["width"] != 800 or resize_state["height"] != 450:
                raise RuntimeError(
                    f"WebGL2 packaged runtime resize failed: {resize_state}; "
                    f"console={console_diagnostics(devtools)}"
                )
            resize_deadline = time.monotonic() + 3.0
            while time.monotonic() < resize_deadline:
                frames = devtools.call("Runtime.evaluate", {
                    "expression": "globalThis.__terminVisualSceneExample.host.frameCount()",
                    "returnByValue": True,
                }).get("result", {}).get("value", 0)
                if frames > resize_state["before"]:
                    break
                time.sleep(0.05)
            else:
                raise RuntimeError(f"WebGL2 runtime stopped rendering after resize: {resize_state}")
            print("TERMIN_WEB_VISUAL_SCENE_SMOKE_PASSED")
            print(json.dumps(metrics, sort_keys=True))
            print("TERMIN_WEBGL2_PACKAGED_RUNTIME_SMOKE_PASSED")
            print(json.dumps(runtime_metrics, sort_keys=True))
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
