"""Verify the packaged SpriteFlipbook demo on both browser graphics backends."""

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

from browser_smoke import (
    DevToolsSocket, available_port, chart_screenshot, decode_png, evaluate,
    find_browser, offline_page, wait_for_page, wait_for_viewer,
)


def green_pixels(image):
    _, _, channels, rows = image
    return {
        (x, y) for y, row in enumerate(rows)
        for x, (r, g, b) in enumerate(zip(row[0::channels], row[1::channels], row[2::channels], strict=True))
        if g > 65 and g > r + 25 and g > b + 3
    }


def bounds(mask):
    if not mask:
        raise RuntimeError("The sprite's green body is missing from the canvas")
    xs, ys = zip(*mask, strict=True)
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


def reference_frames():
    assets = Path(__file__).resolve().parents[3] / "test-projects/sprite-flipbook/Assets"
    atlas = green_pixels(decode_png((assets / "Slime.png").read_bytes()))
    clip = json.loads((assets / "Hop.spriteclip").read_text())
    regions = {
        json.loads(path.with_suffix(".sprite.meta").read_text())["uuid"]: json.loads(path.read_text())["region"]
        for path in assets.glob("*.sprite")
    }
    elapsed = 0.0
    frames = []
    for frame in clip["frames"]:
        x, y, w, h = regions[frame["sprite"]]
        mask = {(i - x, j - y) for i, j in atlas if x <= i < x + w and y <= j < y + h}
        frames.append((elapsed + frame["duration"] / 2, mask, (w, h)))
        elapsed += frame["duration"]
    t, mask, size = frames[0]
    frames.append((elapsed + t, mask, size))
    return frames


def check_flipbook(devtools, artifact, backend, captures):
    with offline_page(devtools, artifact) as url:
        url += f"?backend={backend}"
        devtools.call("Page.navigate", {"url": url})
        state = wait_for_viewer(devtools, expected_url=url)
        if state["hostMetrics"]["graphicsBackend"] != backend:
            raise RuntimeError(f"Unexpected graphics backend in {state}")
        reference = reference_frames()
        scores = []
        for index, (timestamp, expected, size) in enumerate(reference):
            evaluate(devtools, f"window.flipbookTimestamp = {1000 + timestamp * 1000}")
            _, png = chart_screenshot(devtools, selector="#termin-canvas")
            if captures:
                (captures / f"{backend}-frame-{index}.png").write_bytes(png)
            actual = green_pixels(decode_png(png))
            if index == 0:
                # Infer the on-screen texel size and origin from the resting pose.
                # Reuse that mapping to detect incorrect UVs, pivots or animation order.
                x, y, right, bottom = bounds(actual)
                a, b, c, d = bounds(expected)
                sx, sy = (right - x) / (c - a), (bottom - y) / (d - b)
                if min(sx, sy) < 1:
                    raise RuntimeError(f"Rendered sprite is too small: texel size {(sx, sy)}")
                left, top = x - sx * a, y - sy * b
            samples = {
                (x, y) for x in range(size[0]) for y in range(size[1])
                if (int(left + sx * (x + 0.5)), int(top + sy * (y + 0.5))) in actual
            }
            overlap = len(samples & expected) / len(samples | expected)
            if overlap < 0.94:
                raise RuntimeError(f"{backend}: frame {index} at {timestamp:.3f}s only "
                                   f"matches {overlap:.1%} of the atlas silhouette")
            scores.append(round(overlap, 4))
        return scores


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", type=Path)
    parser.add_argument("--captures", type=Path, help="directory for the seven PNGs from each backend")
    args = parser.parse_args()
    if args.captures:
        args.captures.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="termin-flipbook-browser-") as profile:
        port = available_port()
        with subprocess.Popen([
            find_browser(), "--no-sandbox", "--no-first-run", "--window-size=800,640",
            "--enable-unsafe-webgpu", "--enable-unsafe-swiftshader", "--use-webgpu-adapter=swiftshader",
            "--use-gpu-in-tests", "--remote-allow-origins=*",
            f"--remote-debugging-port={port}", f"--user-data-dir={profile}", "about:blank",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) as browser:
            try:
                devtools = DevToolsSocket(wait_for_page(port, "about:blank")["webSocketDebuggerUrl"])
                try:
                    devtools.call("Page.enable")
                    devtools.call("Runtime.enable")
                    devtools.call("Emulation.setDeviceMetricsOverride", {
                        "width": 640, "height": 480, "deviceScaleFactor": 1, "mobile": False,
                    })
                    # Keep normal ordering and presentation of RAF callbacks. Only control the timestamp
                    # that reaches Termin so every capture lands in the middle of a known animation frame.
                    devtools.call("Page.addScriptToEvaluateOnNewDocument", {"source": """
                        window.flipbookTimestamp = 1000;
                        const schedule = window.requestAnimationFrame.bind(window);
                        window.requestAnimationFrame = callback => schedule(() => callback(window.flipbookTimestamp));
                    """})
                    for backend in ("webgpu", "webgl2"):
                        scores = check_flipbook(devtools, args.html, backend, args.captures)
                        print(f"{backend} atlas silhouette matches: {scores}", flush=True)
                finally:
                    try:
                        devtools.call("Browser.close")
                    finally:
                        devtools.close()
            finally:
                try:
                    browser.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    browser.kill()


if __name__ == "__main__":
    main()
