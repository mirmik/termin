"""Discovery paths for independently addressable editor MCP sessions."""

from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import uuid
from pathlib import Path


def canonical_sdk_root(sdk_root: str | Path | None = None) -> Path:
    """Return the canonical SDK root used to identify an editor installation."""

    candidate = Path(sys.prefix if sdk_root is None else sdk_root)
    return Path(os.path.normcase(str(candidate.expanduser().resolve(strict=False))))


def default_editor_mcp_registry_dir(
    *,
    sdk_root: str | Path | None = None,
    temp_dir: str | Path | None = None,
) -> Path:
    """Return the SDK-scoped registry directory for user-owned editors."""

    root = canonical_sdk_root(sdk_root)
    identity = hashlib.sha256(os.fsencode(str(root))).hexdigest()[:16]
    directory = Path(tempfile.gettempdir() if temp_dir is None else temp_dir)
    return directory / f"termin-editor-mcp-{identity}" / "sessions"


def new_editor_mcp_session_file(
    *,
    sdk_root: str | Path | None = None,
    temp_dir: str | Path | None = None,
    instance_id: str | None = None,
) -> Path:
    """Allocate a collision-free descriptor path in the default registry."""

    resolved_instance_id = instance_id or uuid.uuid4().hex
    return (
        default_editor_mcp_registry_dir(
            sdk_root=sdk_root,
            temp_dir=temp_dir,
        )
        / f"{resolved_instance_id}.json"
    )
