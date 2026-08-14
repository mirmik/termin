from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "platform"
    / "termin-web-core"
    / "tests"
    / "browser_smoke.py"
)
SPEC = importlib.util.spec_from_file_location("termin_web_browser_smoke", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
browser_smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(browser_smoke)


def test_viewer_navigation_retries_with_a_fresh_url(monkeypatch) -> None:
    class DevTools:
        def __init__(self) -> None:
            self.urls = []

        def call(self, method: str, params: dict) -> dict:
            assert method == "Page.navigate"
            self.urls.append(params["url"])
            return {}

    observed = []

    def wait_for_viewer(devtools, *, expected_url: str):
        del devtools
        observed.append(expected_url)
        if len(observed) == 1:
            raise RuntimeError("transient WebGPU device loss")
        return {"state": "running", "frames": 2}

    monkeypatch.setattr(browser_smoke, "wait_for_viewer", wait_for_viewer)
    devtools = DevTools()

    state = browser_smoke.navigate_to_viewer(
        devtools, "http://127.0.0.1:9000/viewer.html"
    )

    assert state == {"state": "running", "frames": 2}
    assert devtools.urls == [
        "http://127.0.0.1:9000/viewer.html?gate_attempt=1",
        "http://127.0.0.1:9000/viewer.html?gate_attempt=2",
    ]
    assert observed == devtools.urls
