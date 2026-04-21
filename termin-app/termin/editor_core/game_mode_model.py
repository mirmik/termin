"""GameModeModel — UI-agnostic Play/Stop/Pause orchestration.

Encapsulates the scene-copy + rendering detach/attach + scene_manager mode
transitions that happen when the user toggles Game Mode. Both Qt
(``editor_mode_controller.py``) and tcgui (inline in ``editor_window.py``)
delegate to this model. Views react to ``state_changed`` signal to update
buttons / status bar / menu actions.
"""
from __future__ import annotations

from typing import Callable

from termin.editor_core.signal import Signal


class GameModeModel:
    def __init__(
        self,
        scene_manager,
        editor_attachment,
        rendering_controller,
        get_editor_scene_name: Callable[[], str | None],
        scene_tree_controller=None,
    ):
        self._scene_manager = scene_manager
        self._editor_attachment = editor_attachment
        self._rendering_controller = rendering_controller
        self._get_editor_scene_name = get_editor_scene_name
        self._scene_tree_controller = scene_tree_controller

        self._game_scene_name: str | None = None
        self._saved_tree_expanded_uuids: list[str] | None = None

        # Signals
        # state_changed(model) — fires after Play/Stop; view re-reads
        # is_game_mode, is_game_paused, game_scene_name and updates buttons.
        self.state_changed = Signal()
        # Called at end of start/stop to hand the new scene + expanded
        # uuids to the view, so it can rebuild the scene tree and clear
        # inspector. Signature: (is_playing, scene, expanded_uuids).
        self.mode_entered = Signal()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def game_scene_name(self) -> str | None:
        return self._game_scene_name

    @property
    def is_game_mode(self) -> bool:
        return self._game_scene_name is not None

    @property
    def is_game_paused(self) -> bool:
        if not self.is_game_mode:
            return False
        from termin.editor.scene_manager import SceneMode
        return self._scene_manager.get_mode(self._game_scene_name) == SceneMode.STOP

    # ------------------------------------------------------------------
    # Transitions
    # ------------------------------------------------------------------

    def toggle_game_mode(self) -> None:
        if self.is_game_mode:
            self._stop_game_mode()
        else:
            self._start_game_mode()

    def toggle_pause(self) -> None:
        if not self.is_game_mode or self._game_scene_name is None:
            return
        from termin.editor.scene_manager import SceneMode
        current_mode = self._scene_manager.get_mode(self._game_scene_name)
        if current_mode == SceneMode.PLAY:
            self._scene_manager.set_mode(self._game_scene_name, SceneMode.STOP)
        else:
            self._scene_manager.set_mode(self._game_scene_name, SceneMode.PLAY)
        self.state_changed.emit(self)

    def _start_game_mode(self) -> None:
        if self.is_game_mode:
            return
        editor_scene_name = self._get_editor_scene_name()
        if editor_scene_name is None:
            return

        from termin.editor.scene_manager import SceneMode
        from termin.modules import get_project_modules_runtime
        get_project_modules_runtime().rebuild_stale_modules()

        editor_scene = self._scene_manager.get_scene(editor_scene_name)
        if editor_scene is None:
            return

        self._saved_tree_expanded_uuids = None
        if self._scene_tree_controller is not None:
            self._saved_tree_expanded_uuids = (
                self._scene_tree_controller.get_expanded_entity_uuids()
            )

        self._save_editor_viewport_camera_to_scene(editor_scene)

        if self._rendering_controller is not None:
            self._rendering_controller.sync_viewport_configs_to_scene(editor_scene)

        if self._editor_attachment is not None:
            self._editor_attachment.save_state()

        self._game_scene_name = f"{editor_scene_name}(game)"
        game_scene = self._scene_manager.copy_scene(editor_scene_name, self._game_scene_name)

        if self._rendering_controller is not None:
            self._rendering_controller.detach_scene(editor_scene)

        if self._editor_attachment is not None:
            self._editor_attachment.attach(game_scene, transfer_camera_state=True)

        self._scene_manager.set_mode(editor_scene_name, SceneMode.INACTIVE)
        self._scene_manager.set_mode(self._game_scene_name, SceneMode.PLAY)

        self.state_changed.emit(self)
        self.mode_entered.emit(True, game_scene, self._saved_tree_expanded_uuids)

    def _stop_game_mode(self) -> None:
        if not self.is_game_mode:
            return

        from termin.editor.scene_manager import SceneMode

        if self._editor_attachment is not None:
            self._editor_attachment.detach(save_state=False)

        game_scene_name = self._game_scene_name
        game_scene = self._scene_manager.get_scene(game_scene_name) if game_scene_name else None
        if game_scene is not None and self._rendering_controller is not None:
            self._rendering_controller.detach_scene(game_scene)

        if game_scene_name is not None:
            self._scene_manager.close_scene(game_scene_name)
        self._game_scene_name = None

        editor_scene_name = self._get_editor_scene_name()
        if editor_scene_name is not None:
            self._scene_manager.set_mode(editor_scene_name, SceneMode.STOP)
            editor_scene = self._scene_manager.get_scene(editor_scene_name)
        else:
            editor_scene = None

        if editor_scene is not None and self._editor_attachment is not None:
            self._editor_attachment.attach(editor_scene, restore_state=True)

        self.state_changed.emit(self)
        self.mode_entered.emit(False, editor_scene, self._saved_tree_expanded_uuids)
        self._saved_tree_expanded_uuids = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _save_editor_viewport_camera_to_scene(self, scene) -> None:
        if self._rendering_controller is None:
            return
        editor_display = getattr(self._rendering_controller, "editor_display", None)
        if editor_display is None or not editor_display.viewports:
            return
        viewport = editor_display.viewports[0]
        camera_name = None
        if viewport.camera is not None and viewport.camera.entity is not None:
            camera_name = viewport.camera.entity.name
        scene.set_metadata_value("termin.editor.viewport_camera_name", camera_name)
