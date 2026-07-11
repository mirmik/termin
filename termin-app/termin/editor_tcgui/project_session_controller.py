"""tcgui adapter for the toolkit-neutral project session lifecycle."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from termin.editor_core.project_session_controller import (
    ProjectSessionController as CoreProjectSessionController,
)


class ProjectSessionController(CoreProjectSessionController):
    def __init__(
        self,
        *,
        get_ui: Callable[[], object | None],
        **kwargs,
    ) -> None:
        def show_error(title: str, message: str) -> None:
            ui = get_ui()
            if ui is None:
                return
            from tcgui.widgets.message_box import MessageBox

            MessageBox.error(ui, title, message)

        def run_module_operation(runtime, project_root: Path, on_complete) -> None:
            ui = get_ui()
            if ui is None:
                on_complete(runtime.load_project(project_root))
                return
            from termin.editor_tcgui.dialogs.module_operation_dialog import (
                show_module_operation_dialog,
            )

            show_module_operation_dialog(
                ui,
                runtime,
                title="Load Project Modules",
                start_message=f"Loading project modules: {project_root.name}",
                worker_action=lambda: runtime.prepare_module_artifacts(project_root=project_root),
                owner_action=lambda: runtime.load_project(project_root),
                on_complete=on_complete,
            )

        super().__init__(
            show_error=show_error,
            run_module_operation=run_module_operation,
            **kwargs,
        )


__all__ = ["ProjectSessionController"]
