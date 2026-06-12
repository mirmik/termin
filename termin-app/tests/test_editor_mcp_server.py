import json
import threading
import time
import urllib.request

from termin.editor_tcgui.editor_python_executor import EditorPythonExecutor
from termin.editor_tcgui.mcp_server import (
    EditorMcpConfig,
    EditorMcpServer,
    editor_mcp_enabled,
)


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


def test_editor_mcp_server_exposes_editor_tools(tmp_path):
    executor = EditorPythonExecutor(lambda: {"value": 41})
    config = EditorMcpConfig(
        host="127.0.0.1",
        port=0,
        token="test-token",
        session_file=tmp_path / "editor-mcp.json",
    )
    server = EditorMcpServer(executor, config)
    server.start()
    try:
        session = json.loads(config.session_file.read_text(encoding="utf-8"))

        listed = _post(session, "tools/list")
        tools = listed["result"]["tools"]
        assert tools[0]["name"] == "execute_python_script"
        assert tools[1]["name"] == "capture_editor_screenshot"
        assert session["tools"] == [
            "execute_python_script",
            "capture_editor_screenshot",
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


def test_editor_mcp_server_captures_screenshot_tool(monkeypatch, tmp_path):
    from termin.editor_tcgui import editor_screenshot

    def fake_capture(editor, *, output_path=None, include_image=False, flip_y=True):
        assert editor == "fake-editor"
        assert output_path == "/tmp/editor-shot.png"
        assert include_image is True
        assert flip_y is False
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
    server.start()
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
                        "flip_y": False,
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
