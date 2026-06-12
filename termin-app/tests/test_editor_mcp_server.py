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


def test_editor_mcp_server_exposes_execute_python_tool(tmp_path):
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
