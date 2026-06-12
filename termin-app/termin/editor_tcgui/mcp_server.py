"""Local MCP-compatible endpoint for a running editor process."""

from __future__ import annotations

import json
import os
import secrets
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from tcbase import log

from termin.editor_tcgui.editor_python_executor import (
    EditorPythonExecutor,
    PythonExecutionResult,
)


_DEFAULT_SESSION_FILE = "/tmp/termin-editor-mcp.json"


@dataclass(frozen=True)
class EditorMcpConfig:
    host: str
    port: int
    token: str
    session_file: Path


class EditorMcpServer:
    def __init__(self, executor: EditorPythonExecutor, config: EditorMcpConfig) -> None:
        self._executor = executor
        self._config = config
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        server = self._httpd
        if server is None:
            return f"http://{self._config.host}:{self._config.port}/mcp"
        host, port = server.server_address
        return f"http://{host}:{port}/mcp"

    def start(self) -> None:
        handler_class = self._make_handler()
        self._httpd = ThreadingHTTPServer(
            (self._config.host, self._config.port),
            handler_class,
        )
        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            name="termin-editor-mcp",
            daemon=True,
        )
        self._thread.start()
        self._write_session_file()
        log.info(f"[EditorMCP] listening on {self.url}")

    def stop(self) -> None:
        server = self._httpd
        if server is not None:
            server.shutdown()
            server.server_close()
            self._httpd = None
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        try:
            self._config.session_file.unlink(missing_ok=True)
        except OSError as exc:
            log.error(f"[EditorMCP] failed to remove session file: {exc}")

    def _write_session_file(self) -> None:
        path = self._config.session_file
        payload = {
            "pid": os.getpid(),
            "url": self.url,
            "token": self._config.token,
            "started_at": time.time(),
            "tools": ["execute_python_script"],
        }
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            os.chmod(tmp, 0o600)
            tmp.replace(path)
        except OSError as exc:
            log.error(f"[EditorMCP] failed to write session file '{path}': {exc}")

    def _make_handler(self):
        owner = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "TerminEditorMCP/0.1"

            def do_GET(self) -> None:
                if self.path == "/health":
                    self._send_json({"ok": True, "server": "termin-editor"})
                    return
                self.send_error(404)

            def do_POST(self) -> None:
                if self.path not in ("/mcp", "/jsonrpc"):
                    self.send_error(404)
                    return
                if not self._is_authorized():
                    self._send_json(
                        self._error_response(None, -32001, "Unauthorized"),
                        status=401,
                    )
                    return

                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    body = self.rfile.read(length).decode("utf-8")
                    request = json.loads(body)
                except Exception as exc:
                    log.error(f"[EditorMCP] invalid JSON-RPC request: {exc}")
                    self._send_json(self._error_response(None, -32700, "Parse error"))
                    return

                if isinstance(request, list):
                    responses = [
                        response
                        for item in request
                        if (response := owner._handle_rpc(item)) is not None
                    ]
                    self._send_json(responses)
                    return

                response = owner._handle_rpc(request)
                if response is None:
                    self.send_response(204)
                    self.end_headers()
                    return
                self._send_json(response)

            def log_message(self, fmt: str, *args: object) -> None:
                log.debug(f"[EditorMCP] {fmt % args}")

            def _is_authorized(self) -> bool:
                token = owner._config.token
                if not token:
                    return True
                header = self.headers.get("Authorization", "")
                if header == f"Bearer {token}":
                    return True
                return self.headers.get("X-Termin-MCP-Token", "") == token

            def _send_json(self, payload: Any, *, status: int = 200) -> None:
                data = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _error_response(
                self,
                request_id: object,
                code: int,
                message: str,
            ) -> dict[str, object]:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": code, "message": message},
                }

        return Handler

    def _handle_rpc(self, request: Any) -> dict[str, object] | None:
        if not isinstance(request, dict):
            return self._rpc_error(None, -32600, "Invalid Request")
        request_id = request.get("id")
        method = request.get("method")

        try:
            if method == "initialize":
                return self._rpc_result(
                    request_id,
                    {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {"listChanged": False}},
                        "serverInfo": {
                            "name": "termin-editor",
                            "version": "0.1.0",
                        },
                    },
                )
            if method == "notifications/initialized":
                return None
            if method == "ping":
                return self._rpc_result(request_id, {})
            if method == "tools/list":
                return self._rpc_result(request_id, {"tools": [self._tool_schema()]})
            if method == "tools/call":
                return self._handle_tool_call(request_id, request.get("params"))
            if method == "termin/execute_python":
                params = request.get("params")
                if not isinstance(params, dict):
                    return self._rpc_error(request_id, -32602, "Invalid params")
                return self._rpc_result(
                    request_id,
                    self._execute_python_result(
                        str(params.get("script", "")),
                        timeout=float(params.get("timeout", 30.0)),
                    ),
                )
            return self._rpc_error(request_id, -32601, f"Method not found: {method}")
        except Exception as exc:
            log.error(f"[EditorMCP] request handling failed: {exc}")
            return self._rpc_error(request_id, -32603, f"Internal error: {exc}")

    def _handle_tool_call(
        self,
        request_id: object,
        params: object,
    ) -> dict[str, object]:
        if not isinstance(params, dict):
            return self._rpc_error(request_id, -32602, "Invalid params")
        name = params.get("name")
        if name != "execute_python_script":
            return self._rpc_error(request_id, -32602, f"Unknown tool: {name}")
        arguments = params.get("arguments")
        if not isinstance(arguments, dict):
            return self._rpc_error(request_id, -32602, "Tool arguments must be an object")

        script = str(arguments.get("script", ""))
        timeout = float(arguments.get("timeout", 30.0))
        result = self._execute_python(script, timeout=timeout)
        return self._rpc_result(
            request_id,
            {
                "content": [{"type": "text", "text": result.output or ""}],
                "isError": not result.ok,
                "structuredContent": self._result_payload(result),
            },
        )

    def _execute_python_result(self, script: str, *, timeout: float) -> dict[str, object]:
        return self._result_payload(self._execute_python(script, timeout=timeout))

    def _execute_python(self, script: str, *, timeout: float) -> PythonExecutionResult:
        return self._executor.execute_script_from_any_thread(script, timeout=timeout)

    def _tool_schema(self) -> dict[str, object]:
        return {
            "name": "execute_python_script",
            "description": "Execute a Python script inside the running Termin editor.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "script": {
                        "type": "string",
                        "description": "Python source code to execute in the editor namespace.",
                    },
                    "timeout": {
                        "type": "number",
                        "description": "Seconds to wait for the editor thread to run the script.",
                        "default": 30,
                    },
                },
                "required": ["script"],
                "additionalProperties": False,
            },
        }

    def _result_payload(self, result: PythonExecutionResult) -> dict[str, object]:
        payload: dict[str, object] = {
            "ok": result.ok,
            "output": result.output,
            "wants_more": result.wants_more,
        }
        if result.error is not None:
            payload["error"] = result.error
        return payload

    def _rpc_result(self, request_id: object, result: object) -> dict[str, object]:
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    def _rpc_error(self, request_id: object, code: int, message: str) -> dict[str, object]:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message},
        }


def editor_mcp_enabled() -> bool:
    value = os.environ.get("TERMIN_EDITOR_MCP")
    if value is not None:
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off", ""}:
            return False
        log.warn(
            "[EditorMCP] invalid TERMIN_EDITOR_MCP value "
            f"'{value}', treating it as disabled"
        )
        return False

    from termin.editor_core.settings import EditorSettings

    return EditorSettings.instance().get_mcp_server_enabled()


def load_editor_mcp_config() -> EditorMcpConfig:
    host = os.environ.get("TERMIN_EDITOR_MCP_HOST", "127.0.0.1")
    port = int(os.environ.get("TERMIN_EDITOR_MCP_PORT", "8765"))
    token = os.environ.get("TERMIN_EDITOR_MCP_TOKEN") or secrets.token_urlsafe(24)
    session_file = Path(
        os.environ.get("TERMIN_EDITOR_MCP_SESSION_FILE", _DEFAULT_SESSION_FILE)
    )
    return EditorMcpConfig(
        host=host,
        port=port,
        token=token,
        session_file=session_file,
    )


def start_editor_mcp_server(executor: EditorPythonExecutor) -> EditorMcpServer | None:
    if not editor_mcp_enabled():
        return None
    server = EditorMcpServer(executor, load_editor_mcp_config())
    try:
        server.start()
    except OSError as exc:
        log.error(f"[EditorMCP] failed to start server: {exc}")
        return None
    return server
