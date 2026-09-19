"""Client for the private HTTP JSON-RPC endpoints of Termin processes."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


class McpClientError(RuntimeError):
    """Failure while loading a session or calling its endpoint."""


def load_session(path: Path) -> dict[str, Any]:
    try:
        session = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise McpClientError(f"Session file not found: {path}") from None
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise McpClientError(f"Cannot read session file '{path}': {exc}") from exc
    if not isinstance(session, dict):
        raise McpClientError(f"Invalid session file '{path}': root must be an object")
    if not isinstance(session.get("url"), str) or not session["url"]:
        raise McpClientError(f"Invalid session file '{path}': missing endpoint URL")
    if not isinstance(session.get("token"), str) or not session["token"]:
        raise McpClientError(f"Invalid session file '{path}': missing bearer token")
    session["session_file"] = str(path)
    return session


def post_rpc(session: dict[str, Any], payload: object) -> object | None:
    request = urllib.request.Request(
        session["url"],
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {session['token']}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=35) as response:
            body = response.read()
            if response.status == 204 or not body:
                return None
            return json.loads(body.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # The remote body can echo request headers, including the bearer token.
        raise McpClientError(f"MCP endpoint returned HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        detail = str(exc).replace(session["token"], "[redacted]")
        raise McpClientError(f"Cannot reach MCP endpoint: {detail}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise McpClientError("MCP endpoint returned invalid JSON") from exc


def call(
    session: dict[str, Any], method: str, params: object | None = None
) -> dict[str, Any]:
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        payload["params"] = params
    response = post_rpc(session, payload)
    if not isinstance(response, dict):
        raise McpClientError("MCP endpoint returned no JSON-RPC response")
    return response
