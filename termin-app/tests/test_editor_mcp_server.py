import json
import socket
import threading
import time
import urllib.request

import pytest

from termin.editor_tcgui.editor_python_executor import EditorPythonExecutor
from termin.editor_tcgui.mcp_server import (
    EditorMcpConfig,
    EditorMcpServer,
    editor_mcp_enabled,
)


def _loopback_listener_available() -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            sock.listen(1)
    except OSError:
        return False
    return True


requires_loopback_listener = pytest.mark.skipif(
    not _loopback_listener_available(),
    reason="local loopback listener is unavailable in this test environment",
)


def _start_or_skip(server: EditorMcpServer) -> None:
    try:
        server.start()
    except OSError as exc:
        pytest.skip(f"local loopback listener is unavailable: {exc}")


def _post(session, method, params=None):
    payload = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        payload["params"] = params
    request = urllib.request.Request(
        session["url"],
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {session['token']}",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5.0) as response:
        return json.loads(response.read().decode("utf-8"))


@requires_loopback_listener
def test_editor_mcp_server_exposes_editor_tools(tmp_path):
    executor = EditorPythonExecutor(lambda: {"value": 41})
    config = EditorMcpConfig(
        host="127.0.0.1",
        port=0,
        token="test-token",
        session_file=tmp_path / "editor-mcp.json",
    )
    server = EditorMcpServer(executor, config)
    _start_or_skip(server)
    try:
        session = json.loads(config.session_file.read_text(encoding="utf-8"))

        listed = _post(session, "tools/list")
        tools = listed["result"]["tools"]
        assert tools[0]["name"] == "execute_python_script"
        assert tools[1]["name"] == "capture_editor_screenshot"
        assert tools[2]["name"] == "inspect_framegraph"
        assert tools[3]["name"] == "capture_framegraph_resource"
        assert tools[4]["name"] == "capture_framegraph_pass_symbol"
        for tool in tools[1:5]:
            properties = tool["inputSchema"]["properties"]
            assert "flip_y" not in properties
        assert session["tools"] == [
            "execute_python_script",
            "capture_editor_screenshot",
            "inspect_framegraph",
            "capture_framegraph_resource",
            "capture_framegraph_pass_symbol",
        ]

        result_holder = {}

        def call_tool():
            result_holder["response"] = _post(
                session,
                "tools/call",
                {
                    "name": "execute_python_script",
                    "arguments": {"script": "print(value + 1)", "timeout": 2.0},
                },
            )

        thread = threading.Thread(target=call_tool)
        thread.start()
        deadline = time.monotonic() + 2.0
        while thread.is_alive() and time.monotonic() < deadline:
            executor.process_pending()
            thread.join(timeout=0.01)
        thread.join(timeout=0.1)

        response = result_holder["response"]
        assert response["result"]["isError"] is False
        assert response["result"]["content"][0]["text"] == "42\n"
    finally:
        server.stop()


@requires_loopback_listener
def test_editor_mcp_server_captures_screenshot_tool(monkeypatch, tmp_path):
    from termin.editor_tcgui import editor_screenshot

    def fake_capture(editor, *, output_path=None, include_image=False):
        assert editor == "fake-editor"
        assert output_path == "/tmp/editor-shot.png"
        assert include_image is True
        return {
            "path": "/tmp/editor-shot.png",
            "width": 320,
            "height": 200,
            "mime_type": "image/png",
            "base64": "ZmFrZQ==",
        }

    monkeypatch.setattr(
        editor_screenshot,
        "capture_editor_viewport_screenshot",
        fake_capture,
    )

    executor = EditorPythonExecutor(lambda: {"editor": "fake-editor"})
    config = EditorMcpConfig(
        host="127.0.0.1",
        port=0,
        token="test-token",
        session_file=tmp_path / "editor-mcp.json",
    )
    server = EditorMcpServer(executor, config)
    _start_or_skip(server)
    try:
        session = json.loads(config.session_file.read_text(encoding="utf-8"))
        result_holder = {}

        def call_tool():
            result_holder["response"] = _post(
                session,
                "tools/call",
                {
                    "name": "capture_editor_screenshot",
                    "arguments": {
                        "path": "/tmp/editor-shot.png",
                        "include_image": True,
                        "timeout": 2.0,
                    },
                },
            )

        thread = threading.Thread(target=call_tool)
        thread.start()
        deadline = time.monotonic() + 2.0
        while thread.is_alive() and time.monotonic() < deadline:
            executor.process_pending()
            thread.join(timeout=0.01)
        thread.join(timeout=0.1)

        response = result_holder["response"]
        result = response["result"]
        assert result["isError"] is False
        assert result["content"][0]["text"] == (
            "Captured editor screenshot: /tmp/editor-shot.png (320x200)"
        )
        assert result["content"][1] == {
            "type": "image",
            "data": "ZmFrZQ==",
            "mimeType": "image/png",
        }
        assert result["structuredContent"]["ok"] is True
        assert result["structuredContent"]["path"] == "/tmp/editor-shot.png"
    finally:
        server.stop()


@requires_loopback_listener
def test_editor_mcp_server_captures_framegraph_resource_tool(tmp_path):
    class FakeFramegraphDebugger:
        def __init__(self):
            self.prepared = False

        def prepare_resource_capture(
            self,
            *,
            target_index=None,
            resource_name=None,
            channel_mode=0,
            highlight_hdr=False,
        ):
            assert target_index == 1
            assert resource_name == "ColorPass_3_output_res"
            assert channel_mode == 2
            assert highlight_hdr is True
            self.prepared = True
            return {
                "target_index": 1,
                "target_label": "Display 0",
                "resource": resource_name,
                "capture": {"has_capture": False},
            }

        def export_capture(
            self,
            *,
            output_path=None,
            include_image=False,
            capture_kind="main",
        ):
            assert self.prepared is True
            assert output_path == "/tmp/framegraph-color.png"
            assert include_image is True
            assert capture_kind == "main"
            return {
                "ready": True,
                "path": "/tmp/framegraph-color.png",
                "width": 128,
                "height": 64,
                "mime_type": "image/png",
                "base64": "ZmFrZQ==",
                "resource": "ColorPass_3_output_res",
            }

    fake_debugger = FakeFramegraphDebugger()
    executor = EditorPythonExecutor(lambda: {"framegraph_debugger": fake_debugger})
    config = EditorMcpConfig(
        host="127.0.0.1",
        port=0,
        token="test-token",
        session_file=tmp_path / "editor-mcp.json",
    )
    server = EditorMcpServer(executor, config)
    _start_or_skip(server)
    try:
        session = json.loads(config.session_file.read_text(encoding="utf-8"))
        result_holder = {}

        def call_tool():
            result_holder["response"] = _post(
                session,
                "tools/call",
                {
                    "name": "capture_framegraph_resource",
                    "arguments": {
                        "target_index": 1,
                        "resource": "ColorPass_3_output_res",
                        "path": "/tmp/framegraph-color.png",
                        "include_image": True,
                        "channel_mode": 2,
                        "highlight_hdr": True,
                        "timeout": 2.0,
                    },
                },
            )

        thread = threading.Thread(target=call_tool)
        thread.start()
        deadline = time.monotonic() + 2.0
        while thread.is_alive() and time.monotonic() < deadline:
            executor.process_pending()
            thread.join(timeout=0.01)
        thread.join(timeout=0.1)

        response = result_holder["response"]
        result = response["result"]
        assert result["isError"] is False
        assert result["content"][0]["text"] == (
            "Captured framegraph resource 'ColorPass_3_output_res': "
            "/tmp/framegraph-color.png (128x64)"
        )
        assert result["content"][1] == {
            "type": "image",
            "data": "ZmFrZQ==",
            "mimeType": "image/png",
        }
        assert result["structuredContent"]["ok"] is True
        assert result["structuredContent"]["ready"] is True
        assert result["structuredContent"]["path"] == "/tmp/framegraph-color.png"
    finally:
        server.stop()


@requires_loopback_listener
def test_editor_mcp_server_captures_framegraph_pass_symbol_tool(tmp_path):
    class FakeFramegraphDebugger:
        def __init__(self):
            self.prepared = False

        def prepare_pass_symbol_capture(
            self,
            *,
            target_index=None,
            pass_index=None,
            pass_name=None,
            symbol=None,
            symbol_index=None,
        ):
            assert target_index == 1
            assert pass_index == 4
            assert pass_name == "Color"
            assert symbol == "Cube"
            assert symbol_index == 2
            self.prepared = True
            return {
                "target_index": 1,
                "target_label": "Display 0",
                "pass_index": 4,
                "pass_name": "Color",
                "pass_type": "ColorPass",
                "symbol": "Cube",
                "symbol_index": 2,
                "symbols": ["Ground", "Lines", "Cube"],
                "capture": {"has_capture": False},
            }

        def export_capture(
            self,
            *,
            output_path=None,
            include_image=False,
            capture_kind="main",
        ):
            assert self.prepared is True
            assert output_path == "/tmp/framegraph-pass-color-cube.png"
            assert include_image is True
            assert capture_kind == "main"
            return {
                "ready": True,
                "path": "/tmp/framegraph-pass-color-cube.png",
                "width": 128,
                "height": 64,
                "mime_type": "image/png",
                "base64": "ZmFrZQ==",
                "resource": "",
            }

    fake_debugger = FakeFramegraphDebugger()
    executor = EditorPythonExecutor(lambda: {"framegraph_debugger": fake_debugger})
    config = EditorMcpConfig(
        host="127.0.0.1",
        port=0,
        token="test-token",
        session_file=tmp_path / "editor-mcp.json",
    )
    server = EditorMcpServer(executor, config)
    _start_or_skip(server)
    try:
        session = json.loads(config.session_file.read_text(encoding="utf-8"))
        result_holder = {}

        def call_tool():
            result_holder["response"] = _post(
                session,
                "tools/call",
                {
                    "name": "capture_framegraph_pass_symbol",
                    "arguments": {
                        "target_index": 1,
                        "pass_index": 4,
                        "pass_name": "Color",
                        "symbol": "Cube",
                        "symbol_index": 2,
                        "path": "/tmp/framegraph-pass-color-cube.png",
                        "include_image": True,
                        "timeout": 2.0,
                    },
                },
            )

        thread = threading.Thread(target=call_tool)
        thread.start()
        deadline = time.monotonic() + 2.0
        while thread.is_alive() and time.monotonic() < deadline:
            executor.process_pending()
            thread.join(timeout=0.01)
        thread.join(timeout=0.1)

        response = result_holder["response"]
        result = response["result"]
        assert result["isError"] is False
        assert result["content"][0]["text"] == (
            "Captured framegraph pass symbol 'Color/Cube': "
            "/tmp/framegraph-pass-color-cube.png (128x64)"
        )
        assert result["content"][1] == {
            "type": "image",
            "data": "ZmFrZQ==",
            "mimeType": "image/png",
        }
        assert result["structuredContent"]["ok"] is True
        assert result["structuredContent"]["ready"] is True
        assert result["structuredContent"]["pass_index"] == 4
        assert result["structuredContent"]["symbol_index"] == 2
        assert result["structuredContent"]["path"] == "/tmp/framegraph-pass-color-cube.png"
    finally:
        server.stop()


@requires_loopback_listener
def test_editor_mcp_server_inspects_framegraph_tool(tmp_path):
    class FakeFramegraphDebugger:
        def inspect(
            self,
            *,
            target_index=None,
            include_pass_json=False,
            include_debugger_pass=False,
        ):
            assert target_index == 2
            assert include_pass_json is True
            assert include_debugger_pass is False
            return {
                "targets": [{"index": 2, "label": "Editor / Viewport 0"}],
                "resources": ["hdr", "ldr"],
                "passes": [{"name": "Color", "internal_symbols": ["after_color"]}],
            }

    executor = EditorPythonExecutor(
        lambda: {"framegraph_debugger": FakeFramegraphDebugger()}
    )
    config = EditorMcpConfig(
        host="127.0.0.1",
        port=0,
        token="test-token",
        session_file=tmp_path / "editor-mcp.json",
    )
    server = EditorMcpServer(executor, config)
    _start_or_skip(server)
    try:
        session = json.loads(config.session_file.read_text(encoding="utf-8"))
        result_holder = {}

        def call_tool():
            result_holder["response"] = _post(
                session,
                "tools/call",
                {
                    "name": "inspect_framegraph",
                    "arguments": {
                        "target_index": 2,
                        "include_pass_json": True,
                        "timeout": 2.0,
                    },
                },
            )

        thread = threading.Thread(target=call_tool)
        thread.start()
        deadline = time.monotonic() + 2.0
        while thread.is_alive() and time.monotonic() < deadline:
            executor.process_pending()
            thread.join(timeout=0.01)
        thread.join(timeout=0.1)

        response = result_holder["response"]
        result = response["result"]
        assert result["isError"] is False
        assert result["structuredContent"]["ok"] is True
        assert result["structuredContent"]["resources"] == ["hdr", "ldr"]
        assert result["structuredContent"]["passes"] == [
            {"name": "Color", "internal_symbols": ["after_color"]}
        ]
    finally:
        server.stop()


def test_editor_mcp_enabled_uses_settings_when_env_is_absent(monkeypatch):
    class FakeSettings:
        def get_mcp_server_enabled(self):
            return True

    from termin.editor_core.settings import EditorSettings

    monkeypatch.delenv("TERMIN_EDITOR_MCP", raising=False)
    monkeypatch.setattr(EditorSettings, "instance", staticmethod(lambda: FakeSettings()))

    assert editor_mcp_enabled() is True


def test_editor_mcp_enabled_env_overrides_settings(monkeypatch):
    class FakeSettings:
        def get_mcp_server_enabled(self):
            return True

    from termin.editor_core.settings import EditorSettings

    monkeypatch.setenv("TERMIN_EDITOR_MCP", "0")
    monkeypatch.setattr(EditorSettings, "instance", staticmethod(lambda: FakeSettings()))

    assert editor_mcp_enabled() is False
