"""UI-neutral editor Python execution service for diagnostics and MCP."""

from __future__ import annotations

from collections.abc import Callable

from tcbase import log

from termin.mcp.python_executor import PythonExecutionResult, PythonScriptExecutor


def _request_editor_render_update(editor: object | None) -> None:
    if editor is None:
        log.error("[EditorPythonExecutor] request_render_update requires an editor context")
        raise RuntimeError("request_render_update requires an editor context")

    try:
        editor.request_viewport_update()
    except AttributeError as exc:
        log.error(
            "[EditorPythonExecutor] editor context does not expose request_viewport_update()",
            exc_info=True,
        )
        raise RuntimeError(
            "editor context does not expose request_viewport_update()"
        ) from exc


class EditorPythonExecutor(PythonScriptExecutor):
    """Executes Python snippets against the live editor namespace."""

    def __init__(self, context_provider: Callable[[], dict[str, object | None]]) -> None:
        super().__init__(
            context_provider,
            log_prefix="EditorPythonExecutor",
            compile_filename="<termin-editor-mcp>",
        )

    def _add_runtime_context(self, namespace: dict[str, object | None]) -> None:
        request_render_update = namespace.get("request_render_update")
        if callable(request_render_update):
            namespace["refresh_editor"] = request_render_update
            return
        editor = namespace.get("editor")
        namespace["request_render_update"] = lambda: _request_editor_render_update(editor)
        namespace["refresh_editor"] = namespace["request_render_update"]


__all__ = ["EditorPythonExecutor", "PythonExecutionResult"]
