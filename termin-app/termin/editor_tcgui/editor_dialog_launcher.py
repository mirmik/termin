"""Dialog and viewer launch helpers for EditorWindowTcgui."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from tcbase import log


class EditorDialogLauncher:
    def __init__(
        self,
        *,
        get_editor: Callable[[], object],
        get_ui: Callable[[], object | None],
        get_scene: Callable[[], object | None],
        scene_manager,
        get_game_scene_name: Callable[[], str | None],
        get_project_path: Callable[[], str | None],
        get_rendering_controller: Callable[[], object | None],
        get_fbo_surface: Callable[[], object | None],
        get_project_file_watcher: Callable[[], object | None],
        get_editor_attachment: Callable[[], object | None],
        attach_scene_to_render: Callable[[str], bool],
        detach_scene_from_render: Callable[..., bool],
        attach_editor_to_scene: Callable[..., bool],
        detach_editor_from_scene: Callable[..., bool],
        request_viewport_update: Callable[[], None],
        push_undo_command: Callable[..., None],
        undo_stack,
        undo_stack_changed,
        log_to_console: Callable[[str], None],
        get_spacemouse: Callable[[], object | None],
        set_spacemouse: Callable[[object | None], None],
    ) -> None:
        self._get_editor = get_editor
        self._get_ui = get_ui
        self._get_scene = get_scene
        self._scene_manager = scene_manager
        self._get_game_scene_name = get_game_scene_name
        self._get_project_path = get_project_path
        self._get_rendering_controller = get_rendering_controller
        self._get_fbo_surface = get_fbo_surface
        self._get_project_file_watcher = get_project_file_watcher
        self._get_editor_attachment = get_editor_attachment
        self._attach_scene_to_render = attach_scene_to_render
        self._detach_scene_from_render = detach_scene_from_render
        self._attach_editor_to_scene = attach_editor_to_scene
        self._detach_editor_from_scene = detach_editor_from_scene
        self._request_viewport_update = request_viewport_update
        self._push_undo_command = push_undo_command
        self._undo_stack = undo_stack
        self._undo_stack_changed = undo_stack_changed
        self._log_to_console = log_to_console
        self._get_spacemouse = get_spacemouse
        self._set_spacemouse = set_spacemouse
        self._framegraph_debugger = None

    def show_settings(self) -> None:
        ui = self._get_ui()
        if ui is None:
            return
        from termin.editor_tcgui.dialogs.settings_dialog import show_settings_dialog

        show_settings_dialog(ui)

    def show_about(self) -> None:
        ui = self._get_ui()
        if ui is None:
            return
        rendering_controller = self._get_rendering_controller()
        backend_name = None
        if rendering_controller is not None:
            backend_name = rendering_controller.backend_name()
        from termin.editor_tcgui.dialogs.about_dialog import show_about_dialog

        show_about_dialog(ui, backend_name=backend_name)

    def show_python_console(self) -> None:
        ui = self._get_ui()
        if ui is None:
            return
        from termin.editor_tcgui.dialogs.python_console_dialog import show_python_console_dialog

        show_python_console_dialog(
            ui,
            editor=self._get_editor(),
            get_scene=self._get_scene,
            get_project_path=self._get_project_path,
        )

    def show_project_settings(self) -> None:
        ui = self._get_ui()
        if ui is None:
            return
        from termin.editor_tcgui.dialogs.project_settings_dialog import show_project_settings_dialog

        show_project_settings_dialog(ui, on_changed=self._request_viewport_update)

    def show_scene_properties(self) -> None:
        ui = self._get_ui()
        scene = self._get_scene()
        if ui is None or scene is None:
            return
        from termin.editor_tcgui.dialogs.scene_inspector import show_scene_properties_dialog

        show_scene_properties_dialog(
            ui,
            scene,
            push_undo_command=self._push_undo_command,
            on_changed=self._request_viewport_update,
        )

    def show_layers_settings(self) -> None:
        ui = self._get_ui()
        scene = self._get_scene()
        if ui is None or scene is None:
            return
        from termin.editor_tcgui.dialogs.layers_dialog import show_layers_dialog

        show_layers_dialog(ui, scene)

    def show_shadow_settings(self) -> None:
        ui = self._get_ui()
        scene = self._get_scene()
        if ui is None or scene is None:
            return
        from termin.editor_tcgui.dialogs.shadow_settings_dialog import show_shadow_settings_dialog

        mirror_scenes = []
        game_scene_name = self._get_game_scene_name()
        if game_scene_name is not None:
            game_scene = self._scene_manager.get_scene(game_scene_name)
            if game_scene is not None:
                scene = game_scene
                mirror_scenes.append(self._get_scene())
        show_shadow_settings_dialog(
            ui,
            scene,
            mirror_scenes=mirror_scenes,
            on_changed=self._request_viewport_update,
        )

    def show_agent_types(self) -> None:
        ui = self._get_ui()
        if ui is None:
            return
        from termin.editor_tcgui.dialogs.agent_types_dialog import show_agent_types_dialog

        show_agent_types_dialog(ui)

    def show_navmesh_areas(self) -> None:
        ui = self._get_ui()
        if ui is None:
            return
        from termin.editor_tcgui.dialogs.navmesh_areas_dialog import show_navmesh_areas_dialog

        show_navmesh_areas_dialog(ui, on_changed=self._request_viewport_update)

    def show_spacemouse_settings(self) -> None:
        ui = self._get_ui()
        if ui is None:
            return
        if self._get_spacemouse() is None:
            self.init_spacemouse()
        spacemouse = self._get_spacemouse()
        if spacemouse is None:
            log.warn("SpaceMouse not available")
            return
        from termin.editor_tcgui.dialogs.spacemouse_settings_dialog import show_spacemouse_settings_dialog

        show_spacemouse_settings_dialog(ui, spacemouse)

    def init_spacemouse(self) -> None:
        from termin.editor_core.spacemouse_controller import SpaceMouseController

        spacemouse = SpaceMouseController()
        if spacemouse.open(self._get_editor_attachment(), self._request_viewport_update):
            self._set_spacemouse(spacemouse)
            self._log_to_console("[SpaceMouse] Device connected")
        else:
            self._set_spacemouse(None)

    def show_resource_manager_viewer(self) -> None:
        ui = self._get_ui()
        if ui is None:
            return
        from termin.editor_tcgui.dialogs.resource_manager_viewer import show_resource_manager_viewer

        show_resource_manager_viewer(ui, project_file_watcher=self._get_project_file_watcher())

    def show_core_registry_viewer(self) -> None:
        ui = self._get_ui()
        if ui is None:
            return
        from termin.editor_tcgui.dialogs.core_registry_viewer import show_core_registry_viewer

        show_core_registry_viewer(ui)

    def show_inspect_registry_viewer(self) -> None:
        ui = self._get_ui()
        if ui is None:
            return
        from termin.editor_tcgui.dialogs.inspect_registry_viewer import show_inspect_registry_viewer

        show_inspect_registry_viewer(ui)

    def show_navmesh_registry_viewer(self) -> None:
        ui = self._get_ui()
        if ui is None:
            return
        from termin.editor_tcgui.dialogs.navmesh_registry_viewer import show_navmesh_registry_viewer

        show_navmesh_registry_viewer(ui)

    def show_framegraph_debugger(self) -> None:
        ui = self._get_ui()
        if ui is None:
            return
        if self._framegraph_debugger is not None and self._framegraph_debugger.visible:
            return
        from termin.editor_tcgui.dialogs.framegraph_debugger import show_framegraph_debugger

        self._framegraph_debugger = show_framegraph_debugger(
            ui,
            self._get_rendering_controller(),
            self._get_fbo_surface(),
            on_request_update=self._request_viewport_update,
        )

    def update_framegraph_debugger(self) -> None:
        if self._framegraph_debugger is not None and self._framegraph_debugger.visible:
            self._framegraph_debugger.update()

    def show_audio_debugger(self) -> None:
        ui = self._get_ui()
        if ui is None:
            return
        from termin.editor_tcgui.dialogs.audio_debugger import show_audio_debugger

        show_audio_debugger(ui)

    def show_scene_manager_viewer(self) -> None:
        ui = self._get_ui()
        if ui is None:
            return
        from termin.editor_tcgui.dialogs.scene_manager_viewer import show_scene_manager_viewer

        show_scene_manager_viewer(
            ui,
            self._scene_manager,
            get_editor_attachment=self._get_editor_attachment,
            on_render_attach=lambda name: self._attach_scene_to_render(name),
            on_render_detach=lambda name: self._detach_scene_from_render(name, save_state=True),
            on_editor_attach=lambda name: self._attach_editor_to_scene(
                name,
                restore_state=True,
                transfer_camera_state=False,
            ),
            on_editor_detach=lambda: self._detach_editor_from_scene(save_state=True),
        )

    def show_pipeline_editor(self) -> None:
        ui = self._get_ui()
        if ui is None:
            return
        self._open_pipeline_editor(
            directory=self._get_project_path() or str(Path.home()),
            initial_file=None,
        )

    def open_pipeline_file_for_edit(self, file_path: str) -> None:
        ui = self._get_ui()
        if ui is None:
            return
        self._open_pipeline_editor(
            directory=str(Path(file_path).parent),
            initial_file=file_path,
        )

    def _open_pipeline_editor(self, *, directory: str, initial_file: str | None) -> None:
        ui = self._get_ui()
        if ui is None:
            return
        try:
            from termin.editor_tcgui.pipeline_editor_window import open_pipeline_editor_window

            open_pipeline_editor_window(ui, directory=directory, initial_file=initial_file)
        except Exception as e:
            if initial_file:
                log.error(f"[EditorWindowTcgui] Failed to open Pipeline Editor for {initial_file}: {e}")
            else:
                log.error(f"[EditorWindowTcgui] Failed to open Pipeline Editor: {e}")
            self._log_to_console(f"Pipeline Editor error: {e}")

    def show_undo_stack_viewer(self) -> None:
        ui = self._get_ui()
        if ui is None:
            return
        from termin.editor_tcgui.dialogs.undo_stack_viewer import show_undo_stack_viewer

        show_undo_stack_viewer(
            ui,
            self._undo_stack,
            stack_changed_signal=self._undo_stack_changed,
        )
