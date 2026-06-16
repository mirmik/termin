from pathlib import Path
import threading

from termin.mcp import PythonScriptExecutor, TerminMcpConfig, TerminMcpServer


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
