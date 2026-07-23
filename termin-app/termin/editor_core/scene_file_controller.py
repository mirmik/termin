"""Toolkit-neutral scene file actions for editor frontends."""

from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import threading
import time
from typing import Callable

from tcbase import log
from termin.editor_core.dialog_service import DialogService
from termin.editor_core.editor_state_io import EditorStateIO
from termin.engine import (
    create_scene_with_extensions,
    default_scene_extensions,
    scene as engine_scene,
)

SceneMode = engine_scene.SceneMode


class _SceneLoadTrace:
    def __init__(self, path: str) -> None:
        self.path = path
        self.thread_id = threading.get_ident()
        self.started_at = time.perf_counter()
        log.info(
            f"[SceneLoad] begin path='{self.path}' thread={self.thread_id}"
        )

    @contextmanager
    def stage(self, name: str):
        stage_started_at = time.perf_counter()
        log.info(
            f"[SceneLoad] stage-begin stage={name} "
            f"elapsed_ms={self._elapsed_ms():.3f} path='{self.path}' "
            f"thread={self.thread_id}"
        )
        try:
            yield
        except Exception:
            log.error(
                f"[SceneLoad] stage-failed stage={name} "
                f"duration_ms={(time.perf_counter() - stage_started_at) * 1000.0:.3f} "
                f"elapsed_ms={self._elapsed_ms():.3f} path='{self.path}' "
                f"thread={self.thread_id}"
            )
            raise
        log.info(
            f"[SceneLoad] stage-end stage={name} "
            f"duration_ms={(time.perf_counter() - stage_started_at) * 1000.0:.3f} "
            f"elapsed_ms={self._elapsed_ms():.3f} path='{self.path}' "
            f"thread={self.thread_id}"
        )

    def complete(self) -> None:
        log.info(
            f"[SceneLoad] complete elapsed_ms={self._elapsed_ms():.3f} "
            f"path='{self.path}' thread={self.thread_id}"
        )

    def _elapsed_ms(self) -> float:
        return (time.perf_counter() - self.started_at) * 1000.0


class SceneFileController:
    def __init__(
        self,
        *,
        scene_manager,
        get_dialog_service: Callable[[], DialogService | None],
        get_editor_scene_name: Callable[[], str | None],
        set_editor_scene_name: Callable[[str | None], None],
        get_scene: Callable[[], object | None],
        get_project_path: Callable[[], str | None],
        get_editor_state_io: Callable[[], EditorStateIO | None],
        prepare_scene_for_save: Callable[[str], bool | None],
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
        self._get_dialog_service = get_dialog_service
        self._get_editor_scene_name = get_editor_scene_name
        self._set_editor_scene_name = set_editor_scene_name
        self._get_scene = get_scene
        self._get_project_path = get_project_path
        self._get_editor_state_io = get_editor_state_io
        self._prepare_scene_for_save = prepare_scene_for_save
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
        dialogs = self._get_dialog_service()
        if dialogs is None:
            self.do_new_scene()
            return
        dialogs.show_choice(
            "New Scene",
            "Create a new scene?\n\nThis will remove all entities and resources.",
            ["Yes", "No"],
            lambda result: self.do_new_scene() if result == "Yes" else None,
            default="Yes",
            cancel="No",
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
        dialogs = self._get_dialog_service()
        if dialogs is None:
            log.error("Save Scene As requested without a dialog service")
            return
        project_path = self._get_project_path()
        directory = project_path or str(Path.home())
        dialogs.show_save_file(
            title="Save Scene As",
            directory=directory,
            filter_string="Scene Files (*.scene);;All Files (*)",
            on_result=lambda path: self.save_scene_to_file(path) if path else None,
        )

    def load_scene(self) -> None:
        dialogs = self._get_dialog_service()
        if dialogs is None:
            log.error("Load Scene requested without a dialog service")
            return
        project_path = self._get_project_path()
        directory = project_path or str(Path.home())
        dialogs.show_open_file(
            title="Load Scene",
            directory=directory,
            filter_string="Scene Files (*.scene);;All Files (*)",
            on_result=lambda path: self.load_scene_from_file(path) if path else None,
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
            prepared = self._prepare_scene_for_save(scene_name)
            if prepared is False:
                raise RuntimeError(
                    f"Failed to synchronize scene state before saving '{scene_name}'"
                )
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
        trace = _SceneLoadTrace(path)
        stage = "parse"
        staged_scene = None
        try:
            from termin.editor_core import scene_name_from_file_path

            scene_name = scene_name_from_file_path(path)
            with trace.stage("parse"):
                with open(path, "r", encoding="utf-8") as f:
                    file_data = json.load(f)

            from termin.glb.scene_animation_repair import (
                extract_scene_data,
                repair_glb_animation_player_clip_refs,
            )

            stage = "extract"
            with trace.stage(stage):
                scene_data = extract_scene_data(file_data)
            if scene_data is not None:
                stage = "repair"
                with trace.stage(stage):
                    repair_glb_animation_player_clip_refs(scene_data)

            stage = "staging-create"
            with trace.stage(stage):
                staged_scene = create_scene_with_extensions(
                    scene_name,
                    "",
                    default_scene_extensions(),
                )
                if staged_scene is None or not staged_scene.is_alive():
                    raise RuntimeError(f"Failed to create staging scene '{scene_name}'")

            if scene_data is not None:
                stage = "deserialize"
                with trace.stage(stage):
                    staged_scene.load_from_data(
                        scene_data,
                        context=None,
                        update_settings=True,
                    )

            stage = "editor-start"
            with trace.stage(stage):
                staged_scene.notify_editor_start()

            from termin.project_modules.runtime import upgrade_scene_unknown_components

            stage = "unknown-component-upgrade"
            with trace.stage(stage):
                upgrade_scene_unknown_components(staged_scene)

            stage = "editor-state"
            with trace.stage(stage):
                editor_data = EditorStateIO.extract_from_file(path)
        except Exception as e:
            if staged_scene is not None:
                try:
                    staged_scene.destroy()
                except Exception as cleanup_error:
                    log.error(
                        f"Failed to destroy staging scene for '{path}': {cleanup_error}"
                    )
            message = f"Failed to load scene '{path}' during {stage}: {e}"
            log.error(message)
            self._log_to_console(message)
            return

        try:
            with trace.stage("commit"):
                self._replace_scene(
                    scene_name=scene_name,
                    path=path,
                    staged_scene=staged_scene,
                    editor_data=editor_data,
                    trace=trace,
                )
            trace.complete()
        except Exception as e:
            message = f"Failed to load scene '{path}' during commit: {e}"
            log.error(message)
            self._log_to_console(message)

    def _replace_scene(
        self,
        *,
        scene_name: str,
        path: str,
        staged_scene,
        editor_data,
        trace: _SceneLoadTrace,
    ) -> None:
        old_scene_name = self._get_editor_scene_name()
        if (
            self._scene_manager.has_scene(scene_name)
            and scene_name != old_scene_name
        ):
            staged_scene.destroy()
            raise RuntimeError(
                f"Scene '{scene_name}' is already open and is not the active scene"
            )

        if old_scene_name and self._scene_manager.has_scene(old_scene_name):
            with trace.stage("commit-detach-editor"):
                self._detach_editor_from_scene(
                    save_state=True,
                    clear_editor_scene_name=False,
                )
            with trace.stage("commit-detach-render"):
                self._detach_scene_from_render(old_scene_name, save_state=True)
            with trace.stage("commit-close-old-scene"):
                self._scene_manager.close_scene(old_scene_name)

        with trace.stage("commit-register-scene"):
            self._scene_manager.register_scene(
                scene_name,
                staged_scene.scene_handle(),
            )
            self._scene_manager.set_scene_path(scene_name, path)
            self._scene_manager.set_mode(scene_name, SceneMode.STOP)
            self._set_editor_scene_name(scene_name)

        from termin.project.settings import ProjectSettingsManager

        with trace.stage("commit-project-settings"):
            ProjectSettingsManager.instance().set_last_scene(path)

        self._log_to_console(f"Loaded: {path}")
        with trace.stage("commit-scene-tree"):
            self._sync_scene_tree()
        with trace.stage("commit-observe-scene"):
            self._observe_scene_events(self._get_scene())
        inspector = self._get_inspector_controller()
        if inspector is not None:
            with trace.stage("commit-inspector"):
                inspector.set_scene(self._get_scene())
                inspector.clear()

        if self._has_editor_attachment():
            with trace.stage("commit-attach-editor"):
                self._attach_editor_to_scene(scene_name, restore_state=False)
            with trace.stage("commit-attach-render"):
                self._attach_scene_to_render(scene_name)

        state_io = self._get_editor_state_io()
        if state_io is not None:
            with trace.stage("commit-apply-editor-state"):
                state_io.apply(editor_data)
        with trace.stage("commit-rendering-changed"):
            self._on_rendering_changed()
        with trace.stage("commit-viewport-update"):
            self._request_viewport_update()
        with trace.stage("commit-window-title"):
            self._update_window_title()

    def validate_scene_path(self, path: str) -> bool:
        project_path = self._get_project_path()
        if not project_path:
            return True
        real_file = os.path.realpath(path)
        real_project = os.path.realpath(project_path)
        if real_file.startswith(real_project + os.sep) or real_file == real_project:
            return True

        dialogs = self._get_dialog_service()
        if dialogs is not None:
            dialogs.show_error(
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
