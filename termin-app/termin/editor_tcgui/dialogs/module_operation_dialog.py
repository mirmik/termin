"""Progress dialog for editor project module operations."""

from __future__ import annotations

import threading
from typing import Callable

from tcbase import log
from tcgui.widgets.dialog import Dialog
from tcgui.widgets.label import Label
from tcgui.widgets.progress_bar import ProgressBar
from tcgui.widgets.text_area import TextArea
from tcgui.widgets.units import px
from tcgui.widgets.vstack import VStack


_TAG = "[ModuleOperationDialog]"


def show_module_operation_dialog(
    ui,
    runtime,
    *,
    title: str,
    start_message: str,
    worker_action: Callable[[], bool] | None = None,
    owner_action: Callable[[], bool] | None = None,
    on_complete: Callable[[bool], None],
    auto_close: bool = True,
) -> None:
    """Run isolated build work off-thread and live mutation on the UI owner thread."""
    if worker_action is None and owner_action is None:
        raise ValueError("module operation requires worker_action or owner_action")
    owner_thread_id = threading.get_ident()
    content = VStack()
    content.spacing = 8
    content.preferred_width = px(640)
    content.preferred_height = px(260)

    status_label = Label()
    status_label.text = start_message
    content.add_child(status_label)

    progress = ProgressBar()
    progress.value = 0.08
    progress.preferred_height = px(18)
    content.add_child(progress)

    current_line = Label()
    current_line.text = "Waiting for build output..."
    current_line.font_size = 11
    content.add_child(current_line)

    log_view = TextArea()
    log_view.read_only = True
    log_view.word_wrap = False
    log_view.preferred_height = px(170)
    log_view.stretch = True
    content.add_child(log_view)

    dlg = Dialog()
    dlg.title = title
    dlg.content = content
    # Module operations are not cancellable mid-build. A non-daemon worker owns
    # no live editor state; its commit is queued back to this UI thread.
    dlg.buttons = []
    dlg.default_button = ""
    dlg.cancel_button = ""
    dlg.min_width = 680

    line_count = 0

    def request_layout() -> None:
        if status_label._ui is not None:
            status_label._ui.request_layout()

    def append_log(message: str, *, advance_progress: bool = True) -> None:
        nonlocal line_count
        current = log_view.text
        log_view.text = message if current == "" else current + "\n" + message
        current_line.text = message
        if advance_progress:
            line_count += 1
            progress.value = min(0.92, 0.08 + line_count * 0.025)
        request_layout()

    def defer(callback: Callable[[], None]) -> None:
        ui.defer(callback)

    def on_build_output(module_id: str, line: str) -> None:
        defer(lambda module_id=module_id, line=line: append_log(f"[{module_id}] {line}"))

    def finish(success: bool, error_message: str = "") -> None:
        if threading.get_ident() != owner_thread_id:
            log.error(f"{_TAG} finish callback escaped the UI owner thread")
            success = False
            error_message = "Module operation completion ran on the wrong thread"
        progress.value = 1.0 if success else 0.0
        if success:
            status_label.text = "Complete"
            append_log("Complete.", advance_progress=False)
        else:
            status_label.text = "Failed"
            if error_message:
                append_log(f"Failed: {error_message}", advance_progress=False)
            else:
                append_log("Failed.", advance_progress=False)
        on_complete(success)
        if auto_close:
            dlg.close()
        else:
            dlg.buttons = ["Close"]
            dlg.default_button = "Close"
            dlg.cancel_button = "Close"
        request_layout()

    def run_owner_action() -> None:
        if threading.get_ident() != owner_thread_id:
            finish(False, "Live module commit ran on the wrong thread")
            return
        success = False
        error_message = ""
        try:
            assert owner_action is not None
            success = owner_action()
            if not success:
                error_message = runtime.last_error
        except Exception as exc:
            error_message = str(exc)
            log.error(f"{_TAG} {title} failed: {error_message}", exc_info=True)
        finish(success, error_message)

    def worker() -> None:
        success = False
        error_message = ""
        runtime.add_build_output_listener(on_build_output)
        try:
            assert worker_action is not None
            success = worker_action()
            if not success:
                error_message = runtime.last_error
        except Exception as exc:
            error_message = str(exc)
            log.error(f"{_TAG} {title} failed: {error_message}", exc_info=True)
        finally:
            try:
                runtime.remove_build_output_listener(on_build_output)
            except Exception:
                log.error(f"{_TAG} failed to remove build output listener", exc_info=True)

        if success and owner_action is not None:
            defer(run_owner_action)
        else:
            defer(lambda: finish(success, error_message))

    dlg.show(ui, windowed=False)
    if worker_action is None:
        defer(run_owner_action)
        return

    thread = threading.Thread(target=worker, name=f"ModuleOperation-{title}", daemon=False)
    thread.start()
