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
            "tools": [
                "execute_python_script",
                "capture_editor_screenshot",
                "inspect_framegraph",
            ],
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
                return self._rpc_result(request_id, {"tools": self._tool_schemas()})
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
        if name == "capture_editor_screenshot":
            return self._handle_screenshot_tool_call(request_id, params)
        if name == "inspect_framegraph":
            return self._handle_framegraph_tool_call(request_id, params)
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

    def _handle_framegraph_tool_call(
        self,
        request_id: object,
        params: dict[str, object],
    ) -> dict[str, object]:
        arguments = params.get("arguments")
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, dict):
            return self._rpc_error(request_id, -32602, "Tool arguments must be an object")

        target_index = arguments.get("target_index")
        if target_index is not None:
            try:
                target_index = int(target_index)
            except (TypeError, ValueError):
                return self._rpc_error(request_id, -32602, "target_index must be an integer")
        include_pass_json = bool(arguments.get("include_pass_json", False))
        include_debugger_pass = bool(arguments.get("include_debugger_pass", False))
        timeout = float(arguments.get("timeout", 30.0))

        result = self._inspect_framegraph(
            target_index=target_index,
            include_pass_json=include_pass_json,
            include_debugger_pass=include_debugger_pass,
            timeout=timeout,
        )
        if not result.get("ok", False):
            error = str(result.get("error", "Framegraph inspection failed"))
            return self._rpc_result(
                request_id,
                {
                    "content": [{"type": "text", "text": error}],
                    "isError": True,
                    "structuredContent": result,
                },
            )

        text = json.dumps(result, indent=2, ensure_ascii=False)
        return self._rpc_result(
            request_id,
            {
                "content": [{"type": "text", "text": text}],
                "isError": False,
                "structuredContent": result,
            },
        )

    def _handle_screenshot_tool_call(
        self,
        request_id: object,
        params: dict[str, object],
    ) -> dict[str, object]:
        arguments = params.get("arguments")
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, dict):
            return self._rpc_error(request_id, -32602, "Tool arguments must be an object")

        timeout = float(arguments.get("timeout", 30.0))
        output_path = arguments.get("path")
        if output_path is not None and not isinstance(output_path, str):
            return self._rpc_error(request_id, -32602, "Screenshot path must be a string")
        include_image = bool(arguments.get("include_image", False))
        flip_y = bool(arguments.get("flip_y", True))

        result = self._capture_editor_screenshot(
            output_path=output_path,
            include_image=include_image,
            flip_y=flip_y,
            timeout=timeout,
        )
        if not result.get("ok", False):
            error = str(result.get("error", "Screenshot capture failed"))
            return self._rpc_result(
                request_id,
                {
                    "content": [{"type": "text", "text": error}],
                    "isError": True,
                    "structuredContent": result,
                },
            )

        path = str(result.get("path", ""))
        width = int(result.get("width", 0))
        height = int(result.get("height", 0))
        content: list[dict[str, object]] = [
            {
                "type": "text",
                "text": f"Captured editor screenshot: {path} ({width}x{height})",
            }
        ]
        image_data = result.get("base64")
        if isinstance(image_data, str):
            content.append(
                {
                    "type": "image",
                    "data": image_data,
                    "mimeType": str(result.get("mime_type", "image/png")),
                }
            )
        return self._rpc_result(
            request_id,
            {
                "content": content,
                "isError": False,
                "structuredContent": result,
            },
        )

    def _execute_python_result(self, script: str, *, timeout: float) -> dict[str, object]:
        return self._result_payload(self._execute_python(script, timeout=timeout))

    def _execute_python(self, script: str, *, timeout: float) -> PythonExecutionResult:
        return self._executor.execute_script_from_any_thread(script, timeout=timeout)

    def _inspect_framegraph(
        self,
        *,
        target_index: int | None,
        include_pass_json: bool,
        include_debugger_pass: bool,
        timeout: float,
    ) -> dict[str, object]:
        marker = "__TERMIN_MCP_FRAMEGRAPH_RESULT__"
        script = "\n".join(
            [
                "import json",
                "_termin_mcp_framegraph_result = framegraph_debugger.inspect(",
                f"    target_index={target_index!r},",
                f"    include_pass_json={include_pass_json!r},",
                f"    include_debugger_pass={include_debugger_pass!r},",
                ")",
                f"print({json.dumps(marker)} + json.dumps(_termin_mcp_framegraph_result, ensure_ascii=False))",
            ]
        )
        result = self._execute_python(script, timeout=timeout)
        if not result.ok:
            return {
                "ok": False,
                "output": result.output,
                "error": result.error or "Framegraph inspection script failed",
            }

        for line in result.output.splitlines():
            if not line.startswith(marker):
                continue
            try:
                payload = json.loads(line[len(marker):])
            except json.JSONDecodeError as exc:
                return {
                    "ok": False,
                    "output": result.output,
                    "error": f"Invalid framegraph result JSON: {exc}",
                }
            if isinstance(payload, dict):
                payload["ok"] = True
                return payload
            return {
                "ok": False,
                "output": result.output,
                "error": "Framegraph result payload is not an object",
            }

        return {
            "ok": False,
            "output": result.output,
            "error": "Framegraph result marker not found",
        }

    def _capture_editor_screenshot(
        self,
        *,
        output_path: str | None,
        include_image: bool,
        flip_y: bool,
        timeout: float,
    ) -> dict[str, object]:
        marker = "__TERMIN_MCP_SCREENSHOT_RESULT__"
        script = "\n".join(
            [
                "import json",
                "from termin.editor_tcgui.editor_screenshot import capture_editor_viewport_screenshot",
                "_termin_mcp_screenshot_result = capture_editor_viewport_screenshot(",
                "    editor,",
                f"    output_path={output_path!r},",
                f"    include_image={include_image!r},",
                f"    flip_y={flip_y!r},",
                ")",
                f"print({json.dumps(marker)} + json.dumps(_termin_mcp_screenshot_result, ensure_ascii=False))",
            ]
        )
        result = self._execute_python(script, timeout=timeout)
        if not result.ok:
            return {
                "ok": False,
                "output": result.output,
                "error": result.error or "Screenshot capture script failed",
            }

        for line in result.output.splitlines():
            if not line.startswith(marker):
                continue
            try:
                payload = json.loads(line[len(marker):])
            except json.JSONDecodeError as exc:
                return {
                    "ok": False,
                    "output": result.output,
                    "error": f"Invalid screenshot result JSON: {exc}",
                }
            if isinstance(payload, dict):
                payload["ok"] = True
                return payload
            return {
                "ok": False,
                "output": result.output,
                "error": "Screenshot result payload is not an object",
            }

        return {
            "ok": False,
            "output": result.output,
            "error": "Screenshot result marker not found",
        }

    def _tool_schemas(self) -> list[dict[str, object]]:
        return [
            self._execute_python_tool_schema(),
            self._screenshot_tool_schema(),
            self._framegraph_tool_schema(),
        ]

    def _execute_python_tool_schema(self) -> dict[str, object]:
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

    def _screenshot_tool_schema(self) -> dict[str, object]:
        return {
            "name": "capture_editor_screenshot",
            "description": "Capture the running editor viewport FBO as a PNG screenshot.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Optional output PNG path. Defaults to /tmp/termin-editor-screenshots/.",
                    },
                    "include_image": {
                        "type": "boolean",
                        "description": "Return base64 PNG data as MCP image content.",
                        "default": False,
                    },
                    "flip_y": {
                        "type": "boolean",
                        "description": "Flip framebuffer rows vertically before writing PNG.",
                        "default": True,
                    },
                    "timeout": {
                        "type": "number",
                        "description": "Seconds to wait for the editor thread to capture the screenshot.",
                        "default": 30,
                    },
                },
                "additionalProperties": False,
            },
        }

    def _framegraph_tool_schema(self) -> dict[str, object]:
        return {
            "name": "inspect_framegraph",
            "description": "Inspect the running editor framegraph debugger model without opening its dialog.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "target_index": {
                        "type": "integer",
                        "description": "Optional framegraph target index from the previous snapshot.",
                    },
                    "include_pass_json": {
                        "type": "boolean",
                        "description": "Include serialized pass data when available.",
                        "default": False,
                    },
                    "include_debugger_pass": {
                        "type": "boolean",
                        "description": "Include the FrameDebugger pass in pass and schedule lists.",
                        "default": False,
                    },
                    "timeout": {
                        "type": "number",
                        "description": "Seconds to wait for the editor thread to inspect the framegraph.",
                        "default": 30,
                    },
                },
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
