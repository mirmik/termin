"""Transitional built-in shader catalog and source lookup."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


def builtin_shader_catalog_entry(uuid_value: str) -> dict[str, Any]:
    catalog = builtin_shader_catalog()
    shaders = catalog.get("shaders")
    if not isinstance(shaders, list):
        raise ValueError("Built-in shader catalog has no shader list")
    for entry in shaders:
        if isinstance(entry, dict) and entry.get("uuid") == uuid_value:
            return entry
    raise KeyError(f"Built-in shader catalog has no entry for '{uuid_value}'")


def builtin_shader_catalog() -> dict[str, Any]:
    catalog_path = builtin_shader_catalog_path()
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Built-in shader catalog is not an object: {catalog_path}")
    version = data.get("version")
    if version != 1:
        raise ValueError(f"Built-in shader catalog has unsupported version: {version}")
    return data


def builtin_shader_catalog_path() -> Path:
    filename = "engine-shader-catalog.json"
    for root in builtin_shader_roots():
        path = root / filename
        if path.exists():
            return path
    roots = ", ".join(str(root) for root in builtin_shader_roots())
    raise FileNotFoundError(f"Built-in shader catalog '{filename}' was not found in: {roots}")


def builtin_shader_source(filename: str) -> str:
    for root in builtin_shader_roots():
        path = root / filename
        if path.exists():
            return path.read_text(encoding="utf-8")
    roots = ", ".join(str(root) for root in builtin_shader_roots())
    raise FileNotFoundError(f"Built-in shader source '{filename}' was not found in: {roots}")


def builtin_shader_roots() -> list[Path]:
    repo_root = Path(__file__).resolve().parents[4]
    roots = [
        repo_root / "termin-graphics" / "resources" / "builtin_shaders",
    ]

    sdk_env = os.environ.get("TERMIN_SDK")
    if sdk_env:
        roots.append(Path(sdk_env).resolve() / "share" / "termin" / "builtin_shaders")

    roots.append(Path(sys.prefix).resolve() / "share" / "termin" / "builtin_shaders")
    return roots

