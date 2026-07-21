"""Editor-specific MCP tool contract shared by the endpoint and stdio broker."""

from __future__ import annotations


def editor_mcp_tool_schemas() -> list[dict[str, object]]:
    """Return a fresh copy of the editor tool schemas."""
    return [
        _execute_python_tool_schema(),
        _screenshot_tool_schema(),
        _framegraph_tool_schema(),
        _framegraph_capture_tool_schema(),
        _framegraph_pass_symbol_capture_tool_schema(),
    ]


def _execute_python_tool_schema() -> dict[str, object]:
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


def _screenshot_tool_schema() -> dict[str, object]:
    return {
        "name": "capture_editor_screenshot",
        "description": "Capture the running editor UI or viewport as a PNG screenshot.",
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
                "timeout": {
                    "type": "number",
                    "description": "Seconds to wait for the editor thread to capture the screenshot.",
                    "default": 30,
                },
            },
            "additionalProperties": False,
        },
    }


def _framegraph_tool_schema() -> dict[str, object]:
    return {
        "name": "inspect_framegraph",
        "description": "Inspect the running native framegraph debugger without opening its dialog.",
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
                "timeout": {
                    "type": "number",
                    "description": "Seconds to wait for the editor thread to inspect the framegraph.",
                    "default": 30,
                },
            },
            "additionalProperties": False,
        },
    }


def _framegraph_capture_tool_schema() -> dict[str, object]:
    return {
        "name": "capture_framegraph_resource",
        "description": (
            "Capture a resource from the next matching native framegraph execution and write it as a PNG image."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "target_index": {
                    "type": "integer",
                    "description": "Optional framegraph target index from inspect_framegraph.",
                },
                "resource": {
                    "type": "string",
                    "description": "Optional resource name. Defaults to the first capturable resource.",
                },
                "path": {
                    "type": "string",
                    "description": "Optional output PNG path. Defaults to /tmp/termin-framegraph-captures/.",
                },
                "include_image": {
                    "type": "boolean",
                    "description": "Return base64 PNG data as MCP image content.",
                    "default": False,
                },
                "capture_kind": {
                    "type": "string",
                    "description": "'main' for selected resource capture, or 'depth' for associated depth capture.",
                    "default": "main",
                },
                "channel_mode": {
                    "type": "integer",
                    "description": "Color preview channel: 0=RGBA, 1=R, 2=G, 3=B, 4=A.",
                    "default": 0,
                },
                "highlight_hdr": {
                    "type": "boolean",
                    "description": "Apply the framegraph debugger HDR highlight preview to color captures.",
                    "default": False,
                },
                "timeout": {
                    "type": "number",
                    "description": "Seconds to wait for a render frame to produce the capture.",
                    "default": 30,
                },
            },
            "additionalProperties": False,
        },
    }


def _framegraph_pass_symbol_capture_tool_schema() -> dict[str, object]:
    return {
        "name": "capture_framegraph_pass_symbol",
        "description": (
            "Capture the framebuffer state immediately after an internal "
            "symbol draw inside a framegraph pass and write it as PNG."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "target_index": {
                    "type": "integer",
                    "description": "Optional framegraph target index from inspect_framegraph.",
                },
                "pass_index": {
                    "type": "integer",
                    "description": "Stable pass index from inspect_framegraph. Preferred over pass_name.",
                },
                "pass_name": {
                    "type": "string",
                    "description": "Pass name from inspect_framegraph. Must be unique unless pass_index is provided.",
                },
                "symbol": {
                    "type": "string",
                    "description": "Internal symbol/entity name. Defaults to the last symbol in the pass.",
                },
                "symbol_index": {
                    "type": "integer",
                    "description": "Internal symbol index. Use when symbol names are duplicated.",
                },
                "path": {
                    "type": "string",
                    "description": "Optional output PNG path. Defaults to /tmp/termin-framegraph-captures/.",
                },
                "include_image": {
                    "type": "boolean",
                    "description": "Return base64 PNG data as MCP image content.",
                    "default": False,
                },
                "capture_kind": {
                    "type": "string",
                    "description": "'main' for selected symbol capture, or 'depth' for associated depth capture.",
                    "default": "main",
                },
                "timeout": {
                    "type": "number",
                    "description": "Seconds to wait for a render frame to produce the capture.",
                    "default": 30,
                },
            },
            "additionalProperties": False,
        },
    }
