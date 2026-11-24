"""Play the standalone salvage mission offline using the same controls as a player."""

import argparse
import base64
from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import tempfile
import time

from browser_smoke import (
    DevToolsSocket, available_port, chart_screenshot, console_diagnostics,
    decode_png, dispatch_gesture, evaluate, find_browser, offline_page, wait_for_page,
)


@dataclass(frozen=True)
class Snapshot:
    phase: int
    seconds: float
    attached: bool
    can_hook: bool
    x: float
    z: float
    cargo_x: float
    cargo_z: float
    tension: float


def await_phase(devtools, phase):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        current = evaluate(devtools, "document.querySelector('main')?.dataset.phase")
        if current == phase:
            return
        if current == "error":
            break
        time.sleep(.05)
    raise RuntimeError(f"Expected phase {phase}, got {current}: {console_diagnostics(devtools)}")


def center(devtools, selector):
    return evaluate(devtools, f"""(() => {{
        const element = document.querySelector({json.dumps(selector)});
        const r = element.getBoundingClientRect();
        return [r.x + r.width / 2, r.y + r.height / 2];
    }})()""")


class Pilot:
    """Steer by reading body positions and pressing the keyboard or touch stick."""

    def __init__(self, devtools, touch):
        self.devtools = devtools
        self.touch = touch
        self.axes = (0, 0)
        self.max_tow_offset = 0
        self.stick = center(devtools, "#stick") if touch else None
        # Only the telemetry buffer belongs to the test. The game owns the simulation.
        evaluate(devtools, """(() => {
            const m = __terminViewer.core.module;
            const p = m._malloc(9 * 8);
            window.readMission = () => {
                if (!m._termin_web_salvage_read(p)) throw Error(m.UTF8ToString(m._termin_web_salvage_error()));
                return [...new Float64Array(m.HEAPU8.buffer, p, 9)];
            };
            window.releaseMissionProbe = () => m._free(p);
        })()""")

    def read(self):
        s = Snapshot(*evaluate(self.devtools, "readMission()"))
        if s.attached:
            self.max_tow_offset = max(self.max_tow_offset, s.x - s.cargo_x)
        return s

    def key(self, code, down):
        self.devtools.call("Input.dispatchKeyEvent", {
            "type": "keyDown" if down else "keyUp",
            "code": code, "key": " " if code == "Space" else code,
        })

    def steer(self, x, z):
        previous = self.axes
        if (x, z) == previous:
            return
        if self.touch:
            cx, cy = self.stick
            points = [{"x": cx + 28 * x, "y": cy - 28 * z, "id": 1}]
            if previous == (0, 0):
                self.devtools.call("Input.dispatchTouchEvent", {
                    "type": "touchStart", "touchPoints": [{"x": cx, "y": cy, "id": 1}],
                })
            self.devtools.call("Input.dispatchTouchEvent", {
                "type": "touchMove" if (x or z) else "touchEnd",
                "touchPoints": points if (x or z) else [],
            })
        else:
            for i, negative, positive in ((0, "ArrowLeft", "ArrowRight"), (1, "ArrowDown", "ArrowUp")):
                current = (x, z)[i]
                if previous[i] != current:
                    if previous[i]:
                        self.key(positive if previous[i] > 0 else negative, False)
                    if current:
                        self.key(positive if current > 0 else negative, True)
        self.axes = x, z

    def hook(self):
        self.steer(0, 0)
        if self.touch:
            dispatch_gesture(self.devtools, True, center(self.devtools, "#hook"))
        else:
            self.key("Space", True)
            self.key("Space", False)

    def fly(self, target_x, target_z, reached, label, limit=9):
        previous = self.read()
        start = previous.seconds
        wall_limit = time.monotonic() + limit * 4
        while time.monotonic() < wall_limit:
            s = self.read()
            if reached(s):
                self.steer(0, 0)
                return s
            if s.phase != 1 or start - s.seconds > limit:
                break
            # Apply counter-thrust before crossing the target. Delta comes from the
            # native fixed-step clock, which can advance differently on software GPUs.
            dt = previous.seconds - s.seconds
            if dt > 0:
                def thrust(error, displacement, step):
                    residual = error - .40 * displacement / step
                    return (residual > .07) - (residual < -.07)
                self.steer(thrust(target_x - s.x, s.x - previous.x, dt),
                           thrust(target_z - s.z, s.z - previous.z, dt))
                previous = s
            time.sleep(.055)
        self.steer(0, 0)
        raise RuntimeError(f"Could not {label}: {self.read()}")


def capture(devtools, directory, name):
    if directory:
        png = devtools.call("Page.captureScreenshot", {"format": "png"})["data"]
        (directory / f"{name}.png").write_bytes(base64.b64decode(png))


def warm_pixels(devtools):
    """Find warm vehicle and cargo paint in the scene presented by the compositor."""
    _, png = chart_screenshot(devtools)
    w, h, channels, rows = decode_png(png)
    points = set()
    for y in range(h // 4, 9 * h // 10, 2):
        for x in range(0, w, 2):
            r, g, b = rows[y][x * channels:x * channels + 3]
            if r > 110 and r > b + 40 and g > b + 10:
                points.add((x, y))
    return w, points


def play(devtools, artifact, backend, captures, check_timeout):
    touch = backend == "webgl2"
    with offline_page(devtools, artifact) as url:
        devtools.call("Emulation.setDeviceMetricsOverride", {
            "width": 412 if touch else 920, "height": 820 if touch else 650,
            "deviceScaleFactor": 1, "mobile": touch,
        })
        devtools.call("Emulation.setTouchEmulationEnabled", {"enabled": touch})
        devtools.call("Page.navigate", {"url": f"{url}?backend={backend}"})
        await_phase(devtools, "ready")
        if evaluate(devtools, "__terminViewer.host.graphicsBackend") != backend:
            raise RuntimeError(f"Salvage did not select {backend}")

        def click_start():
            # The victory text and restart button can reflow the phone layout.
            point = evaluate(devtools, """new Promise((resolve, reject) =>
                requestAnimationFrame(() => requestAnimationFrame(() => {
                    const button = document.querySelector('#start');
                    const r = button.getBoundingClientRect();
                    const x = r.x + r.width / 2, y = r.y + r.height / 2;
                    if (document.elementFromPoint(x, y) !== button) reject(Error('Start button is obscured'));
                    else resolve([x, y]);
                })))""")
            if touch:
                devtools.call("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [
                    {"id": 1, "x": point[0], "y": point[1]},
                ]})
                time.sleep(.09)
                devtools.call("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
            else:
                dispatch_gesture(devtools, False, point)

        capture(devtools, captures, f"{backend}-briefing")
        click_start()
        await_phase(devtools, "active")
        pilot = Pilot(devtools, touch)
        try:
            initial = pilot.read()
            if initial.attached or initial.seconds < 55 or initial.x > -3:
                raise RuntimeError(f"Unexpected mission starting position: {initial}")
            width, initial_paint = warm_pixels(devtools)
            pilot.fly(-2.2, -.4, lambda s: s.x > -2.45, "clear the recorder")
            pilot.fly(-2.2, -1.77, lambda s: s.z < -1.63, "dive to lower bulkhead")
            # The sub could pass x=0 at this depth in an empty room. Hold right
            # against the obstruction for a full second and check its position.
            wall = pilot.fly(2, -1.77, lambda s: s.x > -.99, "reach lower bulkhead")
            collision = pilot.fly(2, -1.77, lambda s: wall.seconds - s.seconds > 1., "push against bulkhead")
            if not -1.05 < collision.x < -.30 or collision.z > -1.34:
                raise RuntimeError(f"The submerged bulkhead failed to stop the pilot: {collision}")
            capture(devtools, captures, f"{backend}-contact")

            pilot.fly(-2.4, -.75, lambda s: s.x < -2.1 and s.z > -1., "rise above recorder")
            pilot.fly(-3.6, -.9, lambda s: s.can_hook, "approach recorder")
            pilot.hook()
            pilot.fly(-3.4, -.46, lambda s: s.attached and s.cargo_z > -1.81, "lift recorder")
            # The pilot fits at this altitude. The suspended recorder hits the sill.
            snag = pilot.fly(2, -.46, lambda s: s.x > .02 and s.cargo_x < -.30, "catch recorder on sill")
            jammed = pilot.fly(2, -.46, lambda s: snag.seconds - s.seconds > .65, "pull against sill")
            if not jammed.attached or jammed.cargo_x >= -.23 or jammed.x <= 0:
                raise RuntimeError(f"Expected the cargo to catch behind the pilot: {jammed}")
            capture(devtools, captures, f"{backend}-snag")
            pilot.fly(-1.6, .82, lambda s: s.cargo_z > -.64 and s.x < -.85, "back up and lift recorder")
            capture(devtools, captures, f"{backend}-tow")
            pilot.max_tow_offset = 0
            passed = pilot.fly(3.35, .84, lambda s: s.cargo_x > 1.0 and s.x > 2.8, "tow recorder through breach")
            if not passed.attached or pilot.max_tow_offset < .25:
                raise RuntimeError(f"Expected a swinging tow in the breach: {passed}, offset={pilot.max_tow_offset}")
            offset = pilot.max_tow_offset
            _, moved_paint = warm_pixels(devtools)
            leaving = sum(x < width / 3 for x, _ in initial_paint - moved_paint)
            arriving = sum(x > width * .6 for x, _ in moved_paint - initial_paint)
            if min(leaving, arriving) < 12:
                raise RuntimeError(f"Moving bodies are missing from the rendered scene: {leaving=}, {arriving=}")
            pilot.fly(3.4, -.25, lambda s: abs(s.cargo_x - 3.4) < .43 and s.cargo_z < -1.15,
                      "lower recorder over extraction pad", limit=12)
            pilot.hook()
            pilot.fly(3.4, -.1, lambda s: s.phase == 2, "release recorder onto extraction pad")
            await_phase(devtools, "won")
            won = pilot.read()
            capture(devtools, captures, f"{backend}-won")
            click_start()
            await_phase(devtools, "active")
            restarted = pilot.read()
            if (restarted.attached or restarted.seconds < 55 or
                    abs(restarted.x - initial.x) > .12 or abs(restarted.cargo_x - initial.cargo_x) > .12):
                raise RuntimeError(f"Restart did not restore the initial mission: {restarted}")
            if check_timeout:
                deadline = time.monotonic() + 180
                while time.monotonic() < deadline and pilot.read().phase == 1:
                    time.sleep(.35)
                await_phase(devtools, "timeout")
                if pilot.read().seconds > .03 or evaluate(devtools, "document.querySelector('#clock').textContent") != "0:00":
                    raise RuntimeError("Air gauge and mission timeout disagree")
            return {"contact_x": round(collision.x, 2), "tow_offset": round(offset, 2),
                    "cargo_through_x": round(passed.cargo_x, 2),
                    "won_seconds_left": round(won.seconds, 2), "restart": True, "timeout_tested": check_timeout}
        finally:
            pilot.steer(0, 0)
            evaluate(devtools, "releaseMissionProbe()")


def check_backend(args, backend, check_timeout):
    with tempfile.TemporaryDirectory(prefix="termin-salvage-browser-") as profile:
        port = available_port()
        with subprocess.Popen([
            find_browser(), "--no-sandbox", "--no-first-run", "--window-size=960,840",
            "--enable-unsafe-webgpu", "--enable-unsafe-swiftshader", "--use-webgpu-adapter=swiftshader",
            "--use-gpu-in-tests", "--remote-allow-origins=*",
            f"--remote-debugging-port={port}", f"--user-data-dir={profile}", "about:blank",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) as browser:
            try:
                devtools = DevToolsSocket(wait_for_page(port, "about:blank")["webSocketDebuggerUrl"])
                try:
                    devtools.call("Page.enable")
                    devtools.call("Runtime.enable")
                    return play(devtools, args.html, backend, args.captures, check_timeout)
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", type=Path)
    parser.add_argument("--backend", choices=("webgpu", "webgl2"), help="test one backend")
    parser.add_argument("--captures", type=Path)
    parser.add_argument("--check-timeout", action="store_true",
                        help="also let one restarted dive run for its full sixty seconds")
    args = parser.parse_args()
    if args.captures:
        args.captures.mkdir(parents=True, exist_ok=True)
    # Each emulated device starts at the same isolated file URL in a fresh browser.
    for index, backend in enumerate([args.backend] if args.backend else ["webgpu", "webgl2"]):
        result = check_backend(args, backend, args.check_timeout and index == 0)
        print(backend, json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
