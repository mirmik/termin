"""UI-neutral MCP tools for a running editor process."""

from __future__ import annotations

import json
import os
import time

from tcbase import log

from termin.editor_core.mcp_contract import editor_mcp_tool_schemas
from termin.editor_core.mcp_session import canonical_sdk_root, new_editor_mcp_session_file
from termin.editor_core.project_context import current_project_path
from termin.editor_core.python_executor import (
    EditorPythonExecutor,
)
from termin.mcp.server import TerminMcpConfig, TerminMcpServer, create_secure_mcp_config


EditorMcpConfig = TerminMcpConfig


class EditorMcpServer(TerminMcpServer):
    def __init__(self, executor: EditorPythonExecutor, config: EditorMcpConfig) -> None:
        super().__init__(
            executor,
            config,
            log_prefix="EditorMCP",
            server_name="termin-editor",
            server_version="TerminEditorMCP/0.1",
            thread_name="termin-editor-mcp",
        )

    def _session_payload(self) -> dict[str, object]:
        payload = super()._session_payload()
        project_path = current_project_path()
        payload["project_path"] = str(project_path) if project_path is not None else None
        payload["sdk_root"] = str(canonical_sdk_root())
        return payload

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
        if name == "capture_framegraph_resource":
            return self._handle_framegraph_capture_tool_call(request_id, params)
        if name == "capture_framegraph_pass_symbol":
            return self._handle_framegraph_pass_symbol_capture_tool_call(
                request_id,
                params,
            )
        return super()._handle_tool_call(request_id, params)

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

    def _handle_framegraph_capture_tool_call(
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

        resource_name = arguments.get("resource")
        if resource_name is not None and not isinstance(resource_name, str):
            return self._rpc_error(request_id, -32602, "resource must be a string")

        output_path = arguments.get("path")
        if output_path is not None and not isinstance(output_path, str):
            return self._rpc_error(request_id, -32602, "path must be a string")

        capture_kind = str(arguments.get("capture_kind", "main"))
        include_image = bool(arguments.get("include_image", False))
        highlight_hdr = bool(arguments.get("highlight_hdr", False))
        channel_mode = int(arguments.get("channel_mode", 0))
        timeout = float(arguments.get("timeout", 30.0))

        result = self._capture_framegraph_resource(
            target_index=target_index,
            resource_name=resource_name,
            output_path=output_path,
            include_image=include_image,
            capture_kind=capture_kind,
            channel_mode=channel_mode,
            highlight_hdr=highlight_hdr,
            timeout=timeout,
        )
        if not result.get("ok", False):
            error = str(result.get("error", "Framegraph capture failed"))
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
        resource = str(result.get("resource", ""))
        content: list[dict[str, object]] = [
            {
                "type": "text",
                "text": (f"Captured framegraph resource '{resource}': {path} ({width}x{height})"),
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

    def _handle_framegraph_pass_symbol_capture_tool_call(
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

        pass_index = arguments.get("pass_index")
        if pass_index is not None:
            try:
                pass_index = int(pass_index)
            except (TypeError, ValueError):
                return self._rpc_error(request_id, -32602, "pass_index must be an integer")

        pass_name = arguments.get("pass_name")
        if pass_name is not None and not isinstance(pass_name, str):
            return self._rpc_error(request_id, -32602, "pass_name must be a string")

        symbol_index = arguments.get("symbol_index")
        if symbol_index is not None:
            try:
                symbol_index = int(symbol_index)
            except (TypeError, ValueError):
                return self._rpc_error(request_id, -32602, "symbol_index must be an integer")

        symbol = arguments.get("symbol")
        if symbol is not None and not isinstance(symbol, str):
            return self._rpc_error(request_id, -32602, "symbol must be a string")

        output_path = arguments.get("path")
        if output_path is not None and not isinstance(output_path, str):
            return self._rpc_error(request_id, -32602, "path must be a string")

        capture_kind = str(arguments.get("capture_kind", "main"))
        include_image = bool(arguments.get("include_image", False))
        timeout = float(arguments.get("timeout", 30.0))

        result = self._capture_framegraph_pass_symbol(
            target_index=target_index,
            pass_index=pass_index,
            pass_name=pass_name,
            symbol=symbol,
            symbol_index=symbol_index,
            output_path=output_path,
            include_image=include_image,
            capture_kind=capture_kind,
            timeout=timeout,
        )
        if not result.get("ok", False):
            error = str(result.get("error", "Framegraph pass symbol capture failed"))
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
        pass_label = str(result.get("pass_name", ""))
        symbol_label = str(result.get("symbol", ""))
        content: list[dict[str, object]] = [
            {
                "type": "text",
                "text": (f"Captured framegraph pass symbol '{pass_label}/{symbol_label}': {path} ({width}x{height})"),
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

        result = self._capture_editor_screenshot(
            output_path=output_path,
            include_image=include_image,
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
                payload = json.loads(line[len(marker) :])
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

    def _capture_framegraph_resource(
        self,
        *,
        target_index: int | None,
        resource_name: str | None,
        output_path: str | None,
        include_image: bool,
        capture_kind: str,
        channel_mode: int,
        highlight_hdr: bool,
        timeout: float,
    ) -> dict[str, object]:
        prepare = self._prepare_framegraph_resource_capture(
            target_index=target_index,
            resource_name=resource_name,
            channel_mode=channel_mode,
            highlight_hdr=highlight_hdr,
            timeout=min(timeout, 5.0),
        )
        if not prepare.get("ok", False):
            return prepare

        deadline = time.monotonic() + timeout
        last_result: dict[str, object] | None = None
        while time.monotonic() < deadline:
            result = self._export_framegraph_resource_capture(
                output_path=output_path,
                include_image=include_image,
                capture_kind=capture_kind,
                timeout=min(max(deadline - time.monotonic(), 0.1), 5.0),
            )
            last_result = result
            if not result.get("ok", False):
                return result
            if result.get("ready", False):
                return result
            time.sleep(0.05)

        payload: dict[str, object] = {
            "ok": False,
            "error": "Timed out waiting for framegraph capture",
            "prepare": prepare,
        }
        if last_result is not None:
            payload["last_result"] = last_result
        return payload

    def _capture_framegraph_pass_symbol(
        self,
        *,
        target_index: int | None,
        pass_index: int | None,
        pass_name: str | None,
        symbol: str | None,
        symbol_index: int | None,
        output_path: str | None,
        include_image: bool,
        capture_kind: str,
        timeout: float,
    ) -> dict[str, object]:
        prepare = self._prepare_framegraph_pass_symbol_capture(
            target_index=target_index,
            pass_index=pass_index,
            pass_name=pass_name,
            symbol=symbol,
            symbol_index=symbol_index,
            timeout=min(timeout, 5.0),
        )
        if not prepare.get("ok", False):
            return prepare

        deadline = time.monotonic() + timeout
        last_result: dict[str, object] | None = None
        while time.monotonic() < deadline:
            result = self._export_framegraph_resource_capture(
                output_path=output_path,
                include_image=include_image,
                capture_kind=capture_kind,
                timeout=min(max(deadline - time.monotonic(), 0.1), 5.0),
            )
            last_result = result
            if not result.get("ok", False):
                return result
            if result.get("ready", False):
                merged = dict(result)
                for key in (
                    "pass_index",
                    "pass_name",
                    "pass_type",
                    "symbol",
                    "symbol_index",
                    "symbols",
                ):
                    merged[key] = prepare.get(key)
                return merged
            time.sleep(0.05)

        payload: dict[str, object] = {
            "ok": False,
            "error": "Timed out waiting for framegraph pass symbol capture",
            "prepare": prepare,
        }
        if last_result is not None:
            payload["last_result"] = last_result
        return payload

    def _prepare_framegraph_resource_capture(
        self,
        *,
        target_index: int | None,
        resource_name: str | None,
        channel_mode: int,
        highlight_hdr: bool,
        timeout: float,
    ) -> dict[str, object]:
        marker = "__TERMIN_MCP_FRAMEGRAPH_CAPTURE_PREPARE__"
        script = "\n".join(
            [
                "import json",
                "_termin_mcp_framegraph_capture_prepare = framegraph_debugger.prepare_resource_capture(",
                f"    target_index={target_index!r},",
                f"    resource_name={resource_name!r},",
                f"    channel_mode={channel_mode!r},",
                f"    highlight_hdr={highlight_hdr!r},",
                ")",
                (
                    f"print({json.dumps(marker)} + "
                    "json.dumps(_termin_mcp_framegraph_capture_prepare, ensure_ascii=False))"
                ),
            ]
        )
        return self._execute_json_marker_script(
            script,
            marker=marker,
            timeout=timeout,
            error_label="Framegraph capture prepare",
        )

    def _prepare_framegraph_pass_symbol_capture(
        self,
        *,
        target_index: int | None,
        pass_index: int | None,
        pass_name: str | None,
        symbol: str | None,
        symbol_index: int | None,
        timeout: float,
    ) -> dict[str, object]:
        marker = "__TERMIN_MCP_FRAMEGRAPH_PASS_SYMBOL_PREPARE__"
        script = "\n".join(
            [
                "import json",
                "_termin_mcp_framegraph_pass_symbol_prepare = framegraph_debugger.prepare_pass_symbol_capture(",
                f"    target_index={target_index!r},",
                f"    pass_index={pass_index!r},",
                f"    pass_name={pass_name!r},",
                f"    symbol={symbol!r},",
                f"    symbol_index={symbol_index!r},",
                ")",
                (
                    f"print({json.dumps(marker)} + "
                    "json.dumps(_termin_mcp_framegraph_pass_symbol_prepare, ensure_ascii=False))"
                ),
            ]
        )
        return self._execute_json_marker_script(
            script,
            marker=marker,
            timeout=timeout,
            error_label="Framegraph pass symbol capture prepare",
        )

    def _export_framegraph_resource_capture(
        self,
        *,
        output_path: str | None,
        include_image: bool,
        capture_kind: str,
        timeout: float,
    ) -> dict[str, object]:
        marker = "__TERMIN_MCP_FRAMEGRAPH_CAPTURE_EXPORT__"
        script = "\n".join(
            [
                "import json",
                "_termin_mcp_framegraph_capture_export = framegraph_debugger.export_capture(",
                f"    output_path={output_path!r},",
                f"    include_image={include_image!r},",
                f"    capture_kind={capture_kind!r},",
                ")",
                (
                    f"print({json.dumps(marker)} + "
                    "json.dumps(_termin_mcp_framegraph_capture_export, ensure_ascii=False))"
                ),
            ]
        )
        return self._execute_json_marker_script(
            script,
            marker=marker,
            timeout=timeout,
            error_label="Framegraph capture export",
        )

    def _execute_json_marker_script(
        self,
        script: str,
        *,
        marker: str,
        timeout: float,
        error_label: str,
    ) -> dict[str, object]:
        result = self._execute_python(script, timeout=timeout)
        if not result.ok:
            return {
                "ok": False,
                "output": result.output,
                "error": result.error or f"{error_label} script failed",
            }

        for line in result.output.splitlines():
            if not line.startswith(marker):
                continue
            try:
                payload = json.loads(line[len(marker) :])
            except json.JSONDecodeError as exc:
                return {
                    "ok": False,
                    "output": result.output,
                    "error": f"Invalid {error_label} result JSON: {exc}",
                }
            if isinstance(payload, dict):
                payload["ok"] = True
                return payload
            return {
                "ok": False,
                "output": result.output,
                "error": f"{error_label} result payload is not an object",
            }

        return {
            "ok": False,
            "output": result.output,
            "error": f"{error_label} result marker not found",
        }

    def _capture_editor_screenshot(
        self,
        *,
        output_path: str | None,
        include_image: bool,
        timeout: float,
    ) -> dict[str, object]:
        marker = "__TERMIN_MCP_SCREENSHOT_RESULT__"
        script = "\n".join(
            [
                "import json",
                "_termin_mcp_screenshot_result = capture_editor_screenshot(",
                f"    output_path={output_path!r},",
                f"    include_image={include_image!r},",
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
                payload = json.loads(line[len(marker) :])
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
        return editor_mcp_tool_schemas()


def editor_mcp_enabled() -> bool:
    value = os.environ.get("TERMIN_EDITOR_MCP")
    if value is not None:
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off", ""}:
            return False
        log.warn(f"[EditorMCP] invalid TERMIN_EDITOR_MCP value '{value}', treating it as disabled")
        return False

    from termin.editor_core.settings import EditorSettings

    return EditorSettings.instance().get_mcp_server_enabled()


def load_editor_mcp_config() -> EditorMcpConfig:
    session_file = os.environ.get("TERMIN_EDITOR_MCP_SESSION_FILE")
    if session_file is None:
        session_file = new_editor_mcp_session_file()
    return create_secure_mcp_config(
        host=os.environ.get("TERMIN_EDITOR_MCP_HOST", "127.0.0.1"),
        port=os.environ.get("TERMIN_EDITOR_MCP_PORT", "0"),
        token=os.environ.get("TERMIN_EDITOR_MCP_TOKEN"),
        session_file=session_file,
        default_host="127.0.0.1",
        default_port=0,
        log_prefix="EditorMCP",
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
