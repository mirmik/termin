from __future__ import annotations

from types import SimpleNamespace

import pytest

from termin.player import native_runtime
from termin.player import runtime as player_runtime


class _FakeExecutor:
    def __init__(self) -> None:
        self.closed = False
        self.processed = 0

    def process_pending(self) -> int:
        self.processed += 1
        return 1

    def close(self) -> None:
        self.closed = True


class _FakeServer:
    def __init__(self) -> None:
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


def _bridge() -> SimpleNamespace:
    state = SimpleNamespace(
        should_close=False,
        quit_codes=[],
        scene_handle=(1, 2),
        viewport_handle=(5, 6),
        scene_name="Main",
    )

    def set_window_should_close(value: bool) -> None:
        state.should_close = value

    return SimpleNamespace(
        state=state,
        engine_capsule=lambda: "engine-capsule",
        scene_handle=lambda: state.scene_handle,
        display_handle=lambda: (3, 4),
        viewport_handle=lambda: state.viewport_handle,
        window_framebuffer_size=lambda: (640, 360),
        window_should_close=lambda: state.should_close,
        set_window_should_close=set_window_should_close,
        project_path=lambda: "/tmp/native-player-bundle",
        scene_name=lambda: state.scene_name,
        exit_code=lambda: 7,
        request_quit=lambda code: state.quit_codes.append(code),
    )


def test_native_player_session_exposes_live_host_context_and_closes(monkeypatch) -> None:
    import termin.default_assets.resource_manager as resource_manager_module

    bridge = _bridge()
    engine = SimpleNamespace(rendering_manager="rendering-manager")
    resource_manager = object()
    executor = _FakeExecutor()
    server = _FakeServer()
    start_calls = []

    monkeypatch.setattr(native_runtime, "_borrow_engine_core", lambda capsule: engine)
    monkeypatch.setattr(
        resource_manager_module,
        "DefaultResourceManager",
        SimpleNamespace(instance=lambda: resource_manager),
    )
    monkeypatch.setattr(
        native_runtime,
        "TcScene",
        SimpleNamespace(from_handle=lambda index, generation: ("scene", index, generation)),
    )
    monkeypatch.setattr(
        native_runtime,
        "Display",
        SimpleNamespace(from_handle=lambda index, generation: ("display", index, generation)),
    )
    monkeypatch.setattr(
        native_runtime,
        "Viewport",
        SimpleNamespace(_from_handle=lambda handle: ("viewport", *handle)),
    )

    def start_mcp(runtime, *, explicit, manifest_options):
        start_calls.append((runtime, explicit, manifest_options))
        return executor, server

    monkeypatch.setattr(native_runtime, "start_player_mcp_server", start_mcp)

    session = native_runtime.create_native_player_session(
        bridge,
        True,
        '{"enabled": false, "port": 0}',
    )
    runtime = session.runtime

    assert player_runtime.active_runtime() is runtime
    assert runtime.rendering_manager == "rendering-manager"
    assert runtime.resource_manager is resource_manager
    assert runtime.scene == ("scene", 1, 2)
    assert runtime.display == ("display", 3, 4)
    assert runtime.viewport == ("viewport", 5, 6)
    assert runtime.window.framebuffer_size() == (640, 360)
    assert runtime.project_path.name == "native-player-bundle"
    assert runtime.scene_name == "Main"
    assert runtime.exit_code == 7
    assert start_calls == [(runtime, True, {"enabled": False, "port": 0})]

    bridge.state.scene_handle = (10, 20)
    bridge.state.viewport_handle = (50, 60)
    bridge.state.scene_name = "Secondary"
    assert runtime.scene == ("scene", 10, 20)
    assert runtime.viewport == ("viewport", 50, 60)
    assert runtime.scene_name == "Secondary"

    runtime.window.set_should_close(True)
    runtime.request_quit(9)
    assert runtime.window.should_close()
    assert bridge.state.quit_codes == [9]
    assert session.process_pending() == 1

    session.close()
    session.close()
    assert executor.closed
    assert server.stopped
    assert player_runtime.active_runtime() is None
    assert session.process_pending() == 0


def test_native_player_session_rejects_non_object_manifest_options() -> None:
    with pytest.raises(TypeError, match="must be an object"):
        native_runtime.create_native_player_session(_bridge(), False, "[]")
