"""Compatibility import for the canonical editor MCP service."""

from termin.editor_core.mcp_server import (
    EditorMcpConfig,
    EditorMcpServer,
    editor_mcp_enabled,
    load_editor_mcp_config,
    start_editor_mcp_server,
)

__all__ = [
    "EditorMcpConfig",
    "EditorMcpServer",
    "editor_mcp_enabled",
    "load_editor_mcp_config",
    "start_editor_mcp_server",
]
