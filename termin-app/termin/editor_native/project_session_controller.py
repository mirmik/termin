"""Native startup projection for :mod:`termin.editor_core` project sessions."""

from __future__ import annotations

from collections.abc import Callable
import logging
from pathlib import Path
import threading

from termin.editor_core.project_session_controller import (
    ProjectSessionController as CoreProjectSessionController,
)
from termin.gui_native import Document, EdgeInsets, Rect, RichTextModel, Size


_logger = logging.getLogger(__name__)


class NativeModuleOperationDialog:
    """Modal progress surface for a non-cancellable project module operation.

    Artifact preparation runs on a worker thread.  Module registration and all
    widget mutation remain on the native editor owner thread through ``defer``.
    This mirrors the established tcgui lifecycle instead of merely decorating
    startup with a fake progress indicator.
    """

    def __init__(
        self,
        document: Document,
        *,
        viewport: Callable[[], Rect],
        defer: Callable[[Callable[[], None]], None],
        request_render: Callable[[], None],
        runtime,
        title: str,
        start_message: str,
        worker_action: Callable[[], bool] | None,
        owner_action: Callable[[], bool] | None,
        on_complete: Callable[[bool], None],
    ) -> None:
        if worker_action is None and owner_action is None:
            raise ValueError("module operation requires worker_action or owner_action")
        self.document = document
        self.viewport = viewport
        self.defer = defer
        self.request_render = request_render
        self.runtime = runtime
        self.worker_action = worker_action
        self.owner_action = owner_action
        self.on_complete = on_complete
        self._started = False
        self._finished = False
        self._line_count = 0
        self._log_lines: list[str] = []

        content = document.create_vstack("native-module-operation-content")
        content.stable_id = "editor.module-operation.content"
        content.preferred_size = Size(640.0, 260.0)
        content.set_layout_padding(EdgeInsets(8.0, 8.0, 8.0, 8.0))
        content.set_layout_spacing(8.0)
        self.status = document.create_label(start_message, "native-module-operation-status")
        content.add_fixed_child(self.status, 24.0)
        self.progress = document.create_progress_bar(0.08)
        content.add_fixed_child(self.progress.widget, 18.0)
        self.current_line = document.create_label(
            "Waiting for build output...",
            "native-module-operation-current-line",
        )
        content.add_fixed_child(self.current_line, 22.0)
        self.log_model = RichTextModel()
        self.log_view = document.create_rich_text_view(self.log_model)
        self.log_view.word_wrap = False
        self.log_view.placeholder = "Build output"
        content.add_stretch_child(document.ref(self.log_view.handle))

        self.dialog = document.create_dialog(title)
        self.dialog.actions = []
        self.dialog.dismiss_on_escape = False
        self.dialog.set_content(content)

    def start(self) -> None:
        if self._started:
            raise RuntimeError("native module operation has already started")
        self._started = True
        if not self.dialog.show(self.viewport()):
            raise RuntimeError("failed to show native module operation dialog")
        self.request_render()
        if self.worker_action is None:
            self.defer(self._run_owner_action)
            return
        worker = threading.Thread(
            target=self._run_worker_action,
            name="NativeEditorModulesOperation",
            daemon=False,
        )
        worker.start()

    def _append_log(self, message: str, *, advance_progress: bool = True) -> None:
        if self._finished:
            return
        self._log_lines.append(message)
        self.log_model.set_text("\n".join(self._log_lines))
        self.current_line.text = message
        if advance_progress:
            self._line_count += 1
            self.progress.value = min(0.92, 0.08 + self._line_count * 0.025)
        self.request_render()

    def _on_build_output(self, module_id: str, line: str) -> None:
        self.defer(
            lambda module_id=module_id, line=line: self._append_log(
                f"[{module_id}] {line}"
            )
        )

    def _run_worker_action(self) -> None:
        success = False
        error_message = ""
        self.runtime.add_build_output_listener(self._on_build_output)
        try:
            assert self.worker_action is not None
            success = bool(self.worker_action())
            if not success:
                error_message = self.runtime.last_error
        except Exception as error:
            error_message = str(error)
            _logger.exception("Native module worker operation failed")
        finally:
            try:
                self.runtime.remove_build_output_listener(self._on_build_output)
            except Exception:
                _logger.exception("Native module operation could not remove its output listener")

        if success and self.owner_action is not None:
            self.defer(self._run_owner_action)
        else:
            self.defer(lambda: self._finish(success, error_message))

    def _run_owner_action(self) -> None:
        success = False
        error_message = ""
        try:
            assert self.owner_action is not None
            success = bool(self.owner_action())
            if not success:
                error_message = self.runtime.last_error
        except Exception as error:
            error_message = str(error)
            _logger.exception("Native module owner-thread operation failed")
        self._finish(success, error_message)

    def _finish(self, success: bool, error_message: str) -> None:
        if self._finished:
            return
        self.progress.value = 1.0 if success else 0.0
        if success:
            self.status.text = "Complete"
            self._append_log("Complete.", advance_progress=False)
        else:
            self.status.text = "Failed"
            message = f"Failed: {error_message}" if error_message else "Failed."
            self._append_log(message, advance_progress=False)
        self._finished = True
        self.request_render()
        try:
            self.on_complete(success)
        except Exception:
            _logger.exception("Native module operation completion callback failed")
        finally:
            self.close()

    def close(self) -> None:
        if self.dialog.open:
            self.dialog.close()
        if self.document.is_alive(self.dialog.handle):
            if not self.document.destroy_widget_recursive(self.dialog.handle):
                _logger.error("Native module operation dialog destruction failed")
        self.request_render()


class NativeProjectSessionController(CoreProjectSessionController):
    """Project-session controller with a native startup-module progress dialog."""

    def __init__(
        self,
        *,
        document: Document,
        viewport: Callable[[], Rect],
        defer: Callable[[Callable[[], None]], None],
        request_render: Callable[[], None],
        **kwargs,
    ) -> None:
        self._document = document
        self._viewport = viewport
        self._defer = defer
        self._request_render = request_render
        self._active_operation: NativeModuleOperationDialog | None = None
        super().__init__(run_module_operation=self._run_module_operation, **kwargs)

    @property
    def active_module_operation(self) -> NativeModuleOperationDialog | None:
        return self._active_operation

    def _run_module_operation(self, runtime, project_root: Path, on_complete) -> None:
        if self._active_operation is not None:
            raise RuntimeError("a native project module operation is already active")

        operation: NativeModuleOperationDialog | None = None

        def finished(success: bool) -> None:
            try:
                on_complete(success)
            finally:
                if self._active_operation is operation:
                    self._active_operation = None

        operation = NativeModuleOperationDialog(
            self._document,
            viewport=self._viewport,
            defer=self._defer,
            request_render=self._request_render,
            runtime=runtime,
            title="Load Project Modules",
            start_message=f"Loading project modules: {project_root.name}",
            worker_action=lambda: runtime.prepare_module_artifacts(project_root=project_root),
            owner_action=lambda: runtime.load_project(project_root),
            on_complete=finished,
        )
        self._active_operation = operation
        try:
            operation.start()
        except Exception:
            self._active_operation = None
            operation.close()
            raise


__all__ = ["NativeModuleOperationDialog", "NativeProjectSessionController"]
