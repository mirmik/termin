"""Resource file actions for EditorWindowTcgui."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable

from tcbase import log
from tcgui.widgets.message_box import MessageBox


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

    def load_components_from_file(self) -> None:
        ui = self._get_ui()
        if ui is None:
            return
        from tcgui.widgets.file_dialog_overlay import show_open_file_dialog

        show_open_file_dialog(
            ui,
            title="Load Components",
            directory=self._get_project_path() or str(Path.home()),
            filter_str="Python Files (*.py);;All Files (*)",
            on_result=self.on_components_file_selected,
            windowed=True,
        )

    def deploy_stdlib(self) -> None:
        ui = self._get_ui()
        if ui is None:
            return
        import termin

        stdlib_src = Path(termin.__path__[0]) / "resources" / "stdlib"
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
            on_result=lambda path: self.deploy_stdlib_to(path, stdlib_src),
            windowed=True,
        )

    def migrate_spec_to_meta(self) -> None:
        ui = self._get_ui()
        if ui is None:
            return
        project = self._get_project_path()
        if not project:
            MessageBox.warning(
                ui,
                "No Project",
                "Open a project first to migrate .spec files.",
            )
            return

        spec_files = list(Path(project).rglob("*.spec"))
        if not spec_files:
            MessageBox.info(
                ui,
                "No Files to Migrate",
                "No .spec files found in the current project.",
            )
            return

        migrated = 0
        errors: list[str] = []
        for spec_path in spec_files:
            meta_path = spec_path.with_suffix(".meta")
            try:
                spec_path.rename(meta_path)
                migrated += 1
            except Exception as e:
                errors.append(f"{spec_path.name}: {e}")

        if errors:
            MessageBox.warning(
                ui,
                "Migration Completed with Errors",
                f"Migrated {migrated} files.\nErrors: {len(errors)}",
            )
            log.error("Spec->meta migration completed with errors:\n" + "\n".join(errors))
        else:
            MessageBox.info(
                ui,
                "Migration Complete",
                f"Successfully migrated {migrated} files.",
            )

    def on_material_file_selected(self, path: str | None) -> None:
        if not path:
            return
        self._resource_loader.load_material_from_path(path)
        inspector = self._get_inspector_controller()
        if inspector is not None:
            inspector.show_material_inspector_for_file(path)
        self._request_viewport_update()

    def on_components_file_selected(self, path: str | None) -> None:
        if not path:
            return
        self._resource_loader.load_components_from_path(path)

    def deploy_stdlib_to(self, path: str | None, stdlib_src: Path) -> None:
        ui = self._get_ui()
        if not path or ui is None:
            return
        target_path = Path(path) / "stdlib"
        try:
            shutil.copytree(stdlib_src, target_path, dirs_exist_ok=True)
            MessageBox.info(
                ui,
                "Standard Library Deployed",
                f"Deployed to:\n{target_path}",
            )
            log.info(f"[Editor] Standard library deployed to {target_path}")
        except Exception as e:
            MessageBox.error(
                ui,
                "Deployment Failed",
                f"Failed to deploy standard library:\n{e}",
            )
