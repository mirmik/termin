"""Compatibility facade for editor MCP discovery paths."""

from __future__ import annotations

from pathlib import Path

from termin.mcp.session import (
    canonical_sdk_root as canonical_sdk_root,
    new_sdk_session_file,
    sdk_session_registry_dir,
)


def default_editor_mcp_registry_dir(
    *,
    sdk_root: str | Path | None = None,
    temp_dir: str | Path | None = None,
) -> Path:
    """Return the SDK-scoped registry directory for user-owned editors."""

    return sdk_session_registry_dir("editor", sdk_root=sdk_root, temp_dir=temp_dir)


def new_editor_mcp_session_file(
    *,
    sdk_root: str | Path | None = None,
    temp_dir: str | Path | None = None,
    instance_id: str | None = None,
) -> Path:
    """Allocate a collision-free descriptor path in the default registry."""

    return new_sdk_session_file(
        "editor",
        sdk_root=sdk_root,
        temp_dir=temp_dir,
        instance_id=instance_id,
    )
