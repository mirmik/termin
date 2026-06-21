"""Scene file actions for the tcgui editor."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from tcbase import log
from tcgui.widgets.message_box import MessageBox

from termin.editor_core.editor_state_io import EditorStateIO
from termin.engine import scene as engine_scene
from termin.scene_rendering import default_scene_extensions

SceneMode = engine_scene.SceneMode


class SceneFileController:
    def __init__(
        self,
        *,
        scene_manager,
        get_ui: Callable[[], object | None],
        get_editor_scene_name: Callable[[], str | None],
        set_editor_scene_name: Callable[[str | None], None],
        get_scene: Callable[[], object | None],
        get_project_path: Callable[[], str | None],
        get_editor_state_io: Callable[[], EditorStateIO | None],
        has_editor_attachment: Callable[[], bool],
        detach_editor_from_scene: Callable[..., bool],
        detach_scene_from_render: Callable[..., bool],
        attach_editor_to_scene: Callable[..., bool],
        attach_scene_to_render: Callable[[str], bool],
        get_scene_tree_controller: Callable[[], object | None],
        get_inspector_controller: Callable[[], object | None],
        observe_scene_events: Callable[[object | None], None],
        on_rendering_changed: Callable[[], None],
        request_viewport_update: Callable[[], None],
        update_window_title: Callable[[], None],
        log_to_console: Callable[[str], None],
    ) -> None:
        self._scene_manager = scene_manager
        self._get_ui = get_ui
        self._get_editor_scene_name = get_editor_scene_name
        self._set_editor_scene_name = set_editor_scene_name
        self._get_scene = get_scene
        self._get_project_path = get_project_path
        self._get_editor_state_io = get_editor_state_io
        self._has_editor_attachment = has_editor_attachment
        self._detach_editor_from_scene = detach_editor_from_scene
        self._detach_scene_from_render = detach_scene_from_render
        self._attach_editor_to_scene = attach_editor_to_scene
        self._attach_scene_to_render = attach_scene_to_render
        self._get_scene_tree_controller = get_scene_tree_controller
        self._get_inspector_controller = get_inspector_controller
        self._observe_scene_events = observe_scene_events
        self._on_rendering_changed = on_rendering_changed
        self._request_viewport_update = request_viewport_update
        self._update_window_title = update_window_title
        self._log_to_console = log_to_console

    def new_scene(self) -> None:
        ui = self._get_ui()
        if ui is None:
            self.do_new_scene()
            return
        MessageBox.question(
            ui,
            "New Scene",
            "Create a new scene?\n\nThis will remove all entities and resources.",
            on_result=lambda result: self.do_new_scene() if result == "Yes" else None,
        )

    def do_new_scene(self) -> None:
        old_scene_name = self._get_editor_scene_name()
        if old_scene_name and self._scene_manager.has_scene(old_scene_name):
            self._detach_editor_from_scene(save_state=True, clear_editor_scene_name=False)
            self._detach_scene_from_render(old_scene_name, save_state=True)
            self._scene_manager.close_scene(old_scene_name)

        scene_name = "untitled"
        self._set_editor_scene_name(scene_name)
        self._scene_manager.create_scene(scene_name, default_scene_extensions())
        self._scene_manager.set_mode(scene_name, SceneMode.STOP)
        if self._has_editor_attachment():
            self._attach_editor_to_scene(scene_name, restore_state=False)
            self._attach_scene_to_render(scene_name)
        self._sync_scene_tree()
        self._observe_scene_events(self._get_scene())
        self._update_window_title()

    def save_scene(self) -> None:
        scene_name = self._get_editor_scene_name()
        scene_path = self._scene_manager.get_scene_path(scene_name) if scene_name else None
        if scene_path is not None:
            self.save_scene_to_file(scene_path)
        else:
            self.save_scene_as()

    def save_scene_as(self) -> None:
        ui = self._get_ui()
        if ui is None:
            return
        project_path = self._get_project_path()
        directory = project_path or str(Path.home())
        from tcgui.widgets.file_dialog_overlay import show_save_file_dialog

        show_save_file_dialog(
            ui,
            title="Save Scene As",
            directory=directory,
            filter_str="Scene Files (*.scene);;Legacy Scene Files (*.tc_scene);;All Files (*)",
            on_result=lambda path: self.save_scene_to_file(path) if path else None,
            windowed=True,
        )

    def load_scene(self) -> None:
        ui = self._get_ui()
        if ui is None:
            return
        project_path = self._get_project_path()
        directory = project_path or str(Path.home())
        from tcgui.widgets.file_dialog_overlay import show_open_file_dialog

        show_open_file_dialog(
            ui,
            title="Load Scene",
            directory=directory,
            filter_str="Scene Files (*.scene);;Legacy Scene Files (*.tc_scene);;All Files (*)",
            on_result=lambda path: self.load_scene_from_file(path) if path else None,
            windowed=True,
        )

    def close_scene(self) -> None:
        scene_name = self._get_editor_scene_name()
        if scene_name:
            self._scene_manager.close_scene(scene_name)
            self._scene_manager.create_scene(scene_name, default_scene_extensions())
            self._scene_manager.set_mode(scene_name, SceneMode.STOP)
        self._sync_scene_tree()
        self._observe_scene_events(self._get_scene())
        self._update_window_title()

    def save_scene_to_file(self, path: str) -> None:
        if not path:
            return
        if not self.validate_scene_path(path):
            return
        scene_name = self._get_editor_scene_name()
        if scene_name is None:
            return
        try:
            state_io = self._get_editor_state_io()
            editor_data = state_io.collect() if state_io else None
            self._scene_manager.save_scene(scene_name, path, editor_data)
            from termin.project.settings import ProjectSettingsManager

            ProjectSettingsManager.instance().set_last_scene(path)
            self._log_to_console(f"Saved: {path}")
            self._update_window_title()
        except Exception as e:
            log.error(f"Failed to save scene: {e}")
            self._log_to_console(f"Error saving: {e}")

    def load_scene_from_file(self, path: str) -> None:
        if not path:
            return
        if not self.validate_scene_path(path):
            return
        try:
            from termin.editor_core import scene_name_from_file_path

            old_scene_name = self._get_editor_scene_name()
            scene_name = scene_name_from_file_path(path)

            if old_scene_name and self._scene_manager.has_scene(old_scene_name):
                self._scene_manager.close_scene(old_scene_name)

            self._set_editor_scene_name(scene_name)

            self._scene_manager.load_scene(scene_name, path)
            from termin.modules import upgrade_scene_unknown_components

            upgrade_scene_unknown_components(self._scene_manager.get_scene(scene_name))
            self._scene_manager.set_mode(scene_name, SceneMode.STOP)

            from termin.project.settings import ProjectSettingsManager

            ProjectSettingsManager.instance().set_last_scene(path)

            self._log_to_console(f"Loaded: {path}")
            self._sync_scene_tree()
            self._observe_scene_events(self._get_scene())
            inspector = self._get_inspector_controller()
            if inspector is not None:
                inspector.set_scene(self._get_scene())
                inspector.clear()

            editor_data = EditorStateIO.extract_from_file(path)

            if self._has_editor_attachment():
                self._attach_editor_to_scene(scene_name, restore_state=False)
                self._attach_scene_to_render(scene_name)

            state_io = self._get_editor_state_io()
            if state_io is not None:
                state_io.apply(editor_data)
            self._on_rendering_changed()
            self._request_viewport_update()
            self._update_window_title()
        except Exception as e:
            log.error(f"Failed to load scene: {e}")
            self._log_to_console(f"Error loading: {e}")

    def validate_scene_path(self, path: str) -> bool:
        project_path = self._get_project_path()
        if not project_path:
            return True
        real_file = os.path.realpath(path)
        real_project = os.path.realpath(project_path)
        if real_file.startswith(real_project + os.sep) or real_file == real_project:
            return True

        ui = self._get_ui()
        if ui is not None:
            MessageBox.warning(
                ui,
                "Scene Outside Project",
                f"The scene file must be inside the project directory.\n\n"
                f"Scene: {path}\n"
                f"Project: {project_path}",
            )
        log.error(f"Scene path outside project: scene={path} project={project_path}")
        return False

    def load_last_scene(self) -> None:
        from termin.project.settings import ProjectSettingsManager

        psm = ProjectSettingsManager.instance()
        project_scene = psm.get_last_scene()
        if project_scene is not None and Path(project_scene).is_file():
            self.load_scene_from_file(project_scene)

    def _sync_scene_tree(self) -> None:
        scene_tree = self._get_scene_tree_controller()
        if scene_tree is None:
            return
        scene_tree.set_scene(self._get_scene())
        scene_tree.rebuild()
