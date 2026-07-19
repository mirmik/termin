from pathlib import Path
from types import SimpleNamespace
import threading

from termin.mcp import PythonExecutionResult, PythonScriptExecutor, TerminMcpConfig, TerminMcpServer
from termin.player.mcp_server import (
    PlayerMcpServer,
    PlayerPythonExecutor,
    load_player_mcp_config,
    player_mcp_enabled,
)


def test_python_script_executor_runs_queued_work_on_owner_thread() -> None:
    owner_thread = threading.get_ident()
    executor = PythonScriptExecutor(
        lambda: {
            "value": 41,
            "owner_thread": owner_thread,
            "threading": threading,
        }
    )
    result_holder = []

    def worker() -> None:
        result_holder.append(
            executor.execute_script_from_any_thread(
                "print(value + 1)\nprint(threading.get_ident() == owner_thread)",
                timeout=2.0,
            )
        )

    thread = threading.Thread(target=worker)
    thread.start()
    assert executor.process_pending() == 1
    thread.join(timeout=2.0)

    assert len(result_holder) == 1
    result = result_holder[0]
    assert result.ok
    assert result.output.splitlines() == ["42", "True"]


def test_termin_mcp_server_exposes_execute_python_tool(tmp_path: Path) -> None:
    executor = PythonScriptExecutor(lambda: {"value": 7})
    server = TerminMcpServer(
        executor,
        TerminMcpConfig(
            host="127.0.0.1",
            port=0,
            token="",
            session_file=tmp_path / "mcp.json",
        ),
    )

    tools_response = server._handle_rpc(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    )
    assert tools_response is not None
    tools = tools_response["result"]["tools"]
    assert [tool["name"] for tool in tools] == ["execute_python_script"]

    exec_response = server._handle_rpc(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "termin/execute_python",
            "params": {"script": "print(value)", "timeout": 1.0},
        }
    )
    assert exec_response is not None
    assert exec_response["result"]["ok"] is True
    assert exec_response["result"]["output"] == "7\n"


def test_player_python_executor_exposes_runtime_context(tmp_path: Path) -> None:
    quit_codes = []

    def request_quit(code: int = 0) -> None:
        quit_codes.append(code)

    runtime = SimpleNamespace(
        scene="scene-object",
        window="window-object",
        surface="surface-object",
        display="display-object",
        viewport="viewport-object",
        camera="camera-object",
        project_path=tmp_path,
        scene_name="package/scene.json",
        delta_time=0.25,
        request_quit=request_quit,
    )

    executor = PlayerPythonExecutor(runtime)
    result = executor.execute_script(
        "print(scene)\n"
        "print(project_path.name)\n"
        "print(delta_time)\n"
        "request_quit(3)\n"
    )

    assert result.ok
    assert result.output.splitlines() == ["scene-object", tmp_path.name, "0.25"]
    assert quit_codes == [3]


def test_player_mcp_config_uses_manifest_and_env(monkeypatch) -> None:
    assert player_mcp_enabled(manifest_options={"enabled": True})
    assert not player_mcp_enabled(manifest_options={"enabled": False})

    config = load_player_mcp_config(
        manifest_options={
            "host": "0.0.0.0",
            "port": 9100,
            "token": "manifest-token",
            "session_file": "/tmp/manifest-player-mcp.json",
        }
    )
    assert config.host == "0.0.0.0"
    assert config.port == 9100
    assert config.token == "manifest-token"
    assert config.session_file == Path("/tmp/manifest-player-mcp.json")

    monkeypatch.setenv("TERMIN_PLAYER_MCP_PORT", "9200")
    monkeypatch.setenv("TERMIN_PLAYER_MCP_TOKEN", "env-token")
    config = load_player_mcp_config(manifest_options={"port": 9100, "token": "manifest-token"})
    assert config.port == 9200
    assert config.token == "env-token"

    monkeypatch.setenv("TERMIN_PLAYER_MCP_PORT", "0")
    config = load_player_mcp_config(manifest_options={"port": 9100, "token": "manifest-token"})
    assert config.port == 0


def test_player_mcp_config_recovers_from_invalid_port_and_blank_token(monkeypatch) -> None:
    monkeypatch.setenv("TERMIN_PLAYER_MCP_PORT", "-1")
    monkeypatch.setenv("TERMIN_PLAYER_MCP_TOKEN", "   ")

    config = load_player_mcp_config()

    assert config.port == 8766
    assert config.token
    assert config.token.strip()

    monkeypatch.setenv("TERMIN_PLAYER_MCP_PORT", "70000")
    config = load_player_mcp_config(manifest_options={"token": ""})
    assert config.port == 8766
    assert config.token


def test_player_mcp_server_exposes_screenshot_tool(tmp_path: Path) -> None:
    executor = PythonScriptExecutor(lambda: {})
    server = PlayerMcpServer(
        executor,
        TerminMcpConfig(
            host="127.0.0.1",
            port=0,
            token="",
            session_file=tmp_path / "mcp.json",
        ),
    )

    tools_response = server._handle_rpc(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    )
    assert tools_response is not None
    tools = tools_response["result"]["tools"]
    assert [tool["name"] for tool in tools] == [
        "execute_python_script",
        "capture_player_screenshot",
    ]


def test_player_mcp_screenshot_tool_returns_structured_result(tmp_path: Path) -> None:
    class FakePlayerMcpServer(PlayerMcpServer):
        def _execute_python(self, script: str, *, timeout: float) -> PythonExecutionResult:
            assert "capture_player_screenshot" in script
            return PythonExecutionResult(
                ok=True,
                output=(
                    "__TERMIN_PLAYER_MCP_SCREENSHOT_RESULT__"
                    '{"path": "/tmp/player.png", "width": 320, "height": 200, '
                    '"mime_type": "image/png", "base64": "cG5n"}\n'
                ),
                wants_more=False,
            )

    executor = PythonScriptExecutor(lambda: {})
    server = FakePlayerMcpServer(
        executor,
        TerminMcpConfig(
            host="127.0.0.1",
            port=0,
            token="",
            session_file=tmp_path / "mcp.json",
        ),
    )

    response = server._handle_rpc(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "capture_player_screenshot",
                "arguments": {
                    "path": "/tmp/player.png",
                    "include_image": True,
                    "timeout": 1.0,
                },
            },
        }
    )

    assert response is not None
    result = response["result"]
    assert result["isError"] is False
    assert result["structuredContent"]["ok"] is True
    assert result["structuredContent"]["path"] == "/tmp/player.png"
    assert result["content"][0]["text"] == "Captured player screenshot: /tmp/player.png (320x200)"
    assert result["content"][1] == {
        "type": "image",
        "data": "cG5n",
        "mimeType": "image/png",
    }
