"""MCP diagnostics for standalone/player runtime processes."""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any

from tcbase import log

from termin.mcp import PythonScriptExecutor, TerminMcpConfig, TerminMcpServer, create_secure_mcp_config

if TYPE_CHECKING:
    from termin.player.runtime import PlayerRuntime


_DEFAULT_SESSION_FILE = "/tmp/termin-player-mcp.json"


class PlayerPythonExecutor(PythonScriptExecutor):
    """Executes Python snippets against the live player namespace."""

    def __init__(self, runtime: "PlayerRuntime") -> None:
        self._runtime = runtime
        super().__init__(
            self._build_context,
            log_prefix="PlayerPythonExecutor",
            compile_filename="<termin-player-mcp>",
        )

    def _build_context(self) -> dict[str, object | None]:
        runtime = self._runtime
        return {
            "runtime": runtime,
            "player": runtime,
            "scene": runtime.scene,
            "window": runtime.window,
            "display": runtime.display,
            "viewport": runtime.viewport,
            "camera": runtime.camera,
            "project_path": runtime.project_path,
            "scene_name": runtime.scene_name,
            "delta_time": runtime.delta_time,
            "request_quit": runtime.request_quit,
            "quit": runtime.request_quit,
        }

    def _add_runtime_context(self, namespace: dict[str, object | None]) -> None:
        namespace["request_render_update"] = lambda: True
        namespace["refresh_runtime"] = namespace["request_render_update"]


class PlayerMcpServer(TerminMcpServer):
    def __init__(self, executor: PlayerPythonExecutor, config: TerminMcpConfig) -> None:
        super().__init__(
            executor,
            config,
            log_prefix="PlayerMCP",
            server_name="termin-player",
            server_version="TerminPlayerMCP/0.1",
            thread_name="termin-player-mcp",
        )

    def _handle_tool_call(
        self,
        request_id: object,
        params: object,
    ) -> dict[str, object]:
        if not isinstance(params, dict):
            return self._rpc_error(request_id, -32602, "Invalid params")
        name = params.get("name")
        if name == "capture_player_screenshot":
            return self._handle_screenshot_tool_call(request_id, params)
        return super()._handle_tool_call(request_id, params)

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

        result = self._capture_player_screenshot(
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
                "text": f"Captured player screenshot: {path} ({width}x{height})",
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

    def _capture_player_screenshot(
        self,
        *,
        output_path: str | None,
        include_image: bool,
        timeout: float,
    ) -> dict[str, object]:
        marker = "__TERMIN_PLAYER_MCP_SCREENSHOT_RESULT__"
        script = "\n".join(
            [
                "import json",
                "from termin.player.screenshot import capture_player_screenshot",
                "_termin_mcp_screenshot_result = capture_player_screenshot(",
                "    runtime,",
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
        ]

    def _screenshot_tool_schema(self) -> dict[str, object]:
        return {
            "name": "capture_player_screenshot",
            "description": "Capture the running player render surface as a PNG screenshot.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Optional output PNG path. Defaults to /tmp/termin-player-screenshots/.",
                    },
                    "include_image": {
                        "type": "boolean",
                        "description": "Return base64 PNG data as MCP image content.",
                        "default": False,
                    },
                    "timeout": {
                        "type": "number",
                        "description": "Seconds to wait for the player thread to capture the screenshot.",
                        "default": 30,
                    },
                },
                "additionalProperties": False,
            },
        }


def player_mcp_enabled(
    *,
    explicit: bool = False,
    manifest_options: dict[str, Any] | None = None,
) -> bool:
    if explicit:
        return True

    value = os.environ.get("TERMIN_PLAYER_MCP")
    if value is None:
        value = os.environ.get("TERMIN_MCP")
    if value is not None:
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off", ""}:
            return False
        log.warn(
            "[PlayerMCP] invalid TERMIN_PLAYER_MCP/TERMIN_MCP value "
            f"'{value}', treating it as disabled"
        )
        return False

    if manifest_options is not None:
        enabled = manifest_options.get("enabled")
        if isinstance(enabled, bool):
            return enabled

    return False


def load_player_mcp_config(
    *,
    manifest_options: dict[str, Any] | None = None,
) -> TerminMcpConfig:
    host = _option_string(
        env_name="TERMIN_PLAYER_MCP_HOST",
        manifest_options=manifest_options,
        key="host",
        default="127.0.0.1",
    )
    port = _option_int(
        env_name="TERMIN_PLAYER_MCP_PORT",
        manifest_options=manifest_options,
        key="port",
        default=8766,
    )
    token = os.environ.get("TERMIN_PLAYER_MCP_TOKEN")
    if token is None:
        token = os.environ.get("TERMIN_MCP_TOKEN")
    if token is None and manifest_options is not None:
        token_value = manifest_options.get("token")
        if isinstance(token_value, str):
            token = token_value
    session_file = _option_string(
        env_name="TERMIN_PLAYER_MCP_SESSION_FILE",
        manifest_options=manifest_options,
        key="session_file",
        default=_DEFAULT_SESSION_FILE,
    )
    return create_secure_mcp_config(
        host=host,
        port=port,
        token=token,
        session_file=session_file,
        default_host="127.0.0.1",
        default_port=8766,
        log_prefix="PlayerMCP",
    )


def start_player_mcp_server(
    runtime: "PlayerRuntime",
    *,
    explicit: bool = False,
    manifest_options: dict[str, Any] | None = None,
) -> tuple[PlayerPythonExecutor | None, PlayerMcpServer | None]:
    if not player_mcp_enabled(explicit=explicit, manifest_options=manifest_options):
        return None, None

    executor = PlayerPythonExecutor(runtime)
    server = PlayerMcpServer(executor, load_player_mcp_config(manifest_options=manifest_options))
    try:
        server.start()
    except OSError as exc:
        log.error(f"[PlayerMCP] failed to start server: {exc}")
        return executor, None
    return executor, server


def _option_string(
    *,
    env_name: str,
    manifest_options: dict[str, Any] | None,
    key: str,
    default: str,
) -> str:
    value = os.environ.get(env_name)
    if value is not None:
        return value
    if manifest_options is not None:
        option = manifest_options.get(key)
        if isinstance(option, str) and option != "":
            return option
    return default


def _option_int(
    *,
    env_name: str,
    manifest_options: dict[str, Any] | None,
    key: str,
    default: int,
) -> int:
    value = os.environ.get(env_name)
    if value is not None:
        try:
            return int(value)
        except ValueError:
            log.warn(f"[PlayerMCP] invalid {env_name} value '{value}', using {default}")
            return default
    if manifest_options is not None:
        option = manifest_options.get(key)
        if isinstance(option, int):
            return option
    return default
