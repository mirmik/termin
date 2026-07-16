"""Resource file actions for EditorWindowTcgui."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from tcbase import log
from tcgui.widgets.message_box import MessageBox
from termin.stdlib import stdlib_root, sync_stdlib


class ResourceActionsController:
    def __init__(
        self,
        *,
        get_ui: Callable[[], object | None],
        get_project_path: Callable[[], str | None],
        resource_loader,
        get_inspector_controller: Callable[[], object | None],
        request_viewport_update: Callable[[], None],
    ) -> None:
        self._get_ui = get_ui
        self._get_project_path = get_project_path
        self._resource_loader = resource_loader
        self._get_inspector_controller = get_inspector_controller
        self._request_viewport_update = request_viewport_update

    def load_material_from_file(self) -> None:
        ui = self._get_ui()
        if ui is None:
            return
        from tcgui.widgets.file_dialog_overlay import show_open_file_dialog

        show_open_file_dialog(
            ui,
            title="Load Material",
            directory=self._get_project_path() or str(Path.home()),
            filter_str="Shader Files (*.shader);;All Files (*)",
            on_result=self.on_material_file_selected,
            windowed=True,
        )

    def deploy_stdlib(self) -> None:
        ui = self._get_ui()
        if ui is None:
            return
        stdlib_src = stdlib_root()
        if not stdlib_src.exists():
            MessageBox.error(
                ui,
                "Standard Library Not Found",
                f"Path not found:\n{stdlib_src}",
            )
            return

        from tcgui.widgets.file_dialog_overlay import show_open_directory_dialog

        show_open_directory_dialog(
            ui,
            title="Select Directory for Standard Library",
            directory=self._get_project_path() or str(Path.home()),
            on_result=self.deploy_stdlib_to,
            windowed=True,
        )

    def on_material_file_selected(self, path: str | None) -> None:
        if not path:
            return
        self._resource_loader.load_material_from_path(path)
        inspector = self._get_inspector_controller()
        if inspector is not None:
            inspector.show_material_inspector_for_file(path)
        self._request_viewport_update()

    def deploy_stdlib_to(self, path: str | None) -> None:
        ui = self._get_ui()
        if not path or ui is None:
            return
        try:
            result = sync_stdlib(path)
            MessageBox.info(
                ui,
                "Standard Library Deployed",
                f"Deployed to:\n{result.target_root}",
            )
            log.info(f"[Editor] Standard library deployed to {result.target_root}")
        except Exception as e:
            MessageBox.error(
                ui,
                "Deployment Failed",
                f"Failed to deploy standard library:\n{e}",
            )
