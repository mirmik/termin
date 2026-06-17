from pathlib import Path
from types import SimpleNamespace
import threading

from termin.mcp import PythonScriptExecutor, TerminMcpConfig, TerminMcpServer
from termin.player.mcp_server import (
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
        asset_manifest_path=tmp_path / "manifest.json",
        build_json_path=tmp_path / "app.json",
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
