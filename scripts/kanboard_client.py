#!/usr/bin/env python3
"""Shared Kanboard JSON-RPC client helpers for Termin scripts."""

from __future__ import annotations

import base64
import ipaddress
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_ENV_PATH = "~/.config/termin/kanboard-codex.env"
DEFAULT_PROJECT_ID = 1
REDACTED = "<redacted>"
SENSITIVE_KEY_PARTS = ("token", "password", "secret", "key")


class KanboardError(RuntimeError):
    pass


@dataclass(frozen=True)
class KanboardConfig:
    url: str
    user: str
    token: str


class KanboardClient:
    def __init__(self, config: KanboardConfig) -> None:
        self._config = config

    def call(self, method: str, params: object = None, request_id: int = 1) -> dict[str, Any]:
        return call_kanboard(
            self._config.url,
            self._config.user,
            self._config.token,
            method,
            params,
            request_id,
        )

    def result(self, method: str, params: object = None) -> Any:
        response = self.call(method, params)
        if "error" in response and response["error"] is not None:
            raise KanboardError(f"Kanboard method {method} failed: {response['error']}")
        return response.get("result")


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        raise KanboardError(f"Kanboard env file not found: {path}")

    for lineno, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        if "=" not in line:
            raise KanboardError(f"Invalid env line {path}:{lineno}: expected KEY=VALUE")

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise KanboardError(f"Invalid env line {path}:{lineno}: empty key")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        values[key] = value

    return values


def load_config(env_path: str) -> KanboardConfig:
    file_values = parse_env_file(Path(env_path).expanduser())
    url = os.environ.get("KANBOARD_URL") or file_values.get("KANBOARD_URL")
    user = os.environ.get("KANBOARD_USER") or file_values.get("KANBOARD_USER")
    token = os.environ.get("KANBOARD_TOKEN") or file_values.get("KANBOARD_TOKEN")

    missing = [
        name
        for name, value in (
            ("KANBOARD_URL", url),
            ("KANBOARD_USER", user),
            ("KANBOARD_TOKEN", token),
        )
        if not value
    ]
    if missing:
        raise KanboardError(f"Missing Kanboard setting(s): {', '.join(missing)}")

    return KanboardConfig(url=url, user=user, token=token)


def parse_params(params_text: str | None) -> object:
    if params_text is None:
        return None
    try:
        return json.loads(params_text)
    except json.JSONDecodeError as exc:
        raise KanboardError(f"Invalid params JSON: {exc}") from exc


def redact(value: object) -> object:
    if isinstance(value, dict):
        result: dict[str, object] = {}
        for key, item in value.items():
            lowered = key.lower()
            if any(part in lowered for part in SENSITIVE_KEY_PARTS):
                result[key] = REDACTED
            else:
                result[key] = redact(item)
        return result
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def should_bypass_proxy(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname
    if not host:
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return host in {"localhost"}
    return address.is_private or address.is_loopback or address.is_link_local


def call_kanboard(url: str, user: str, token: str, method: str, params: object, request_id: int) -> dict[str, Any]:
    payload: dict[str, object] = {
        "jsonrpc": "2.0",
        "method": method,
        "id": request_id,
    }
    if params is not None:
        payload["params"] = params

    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    credentials = base64.b64encode(f"{user}:{token}".encode("utf-8")).decode("ascii")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        opener = (
            urllib.request.build_opener(urllib.request.ProxyHandler({}))
            if should_bypass_proxy(url)
            else urllib.request.build_opener()
        )
        with opener.open(request, timeout=20) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise KanboardError(f"Kanboard HTTP error {exc.code}: {details}") from exc
    except urllib.error.URLError as exc:
        raise KanboardError(f"Kanboard connection failed: {exc.reason}") from exc

    try:
        decoded = json.loads(response_body)
    except json.JSONDecodeError as exc:
        raise KanboardError(f"Kanboard returned invalid JSON: {response_body[:500]}") from exc
    if not isinstance(decoded, dict):
        raise KanboardError(f"Kanboard returned non-object JSON: {response_body[:500]}")
    return decoded


def make_client(env_file: str) -> KanboardClient:
    return KanboardClient(load_config(env_file))

