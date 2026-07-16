"""GameModeModel — UI-agnostic Play/Stop/Pause orchestration.

Encapsulates the scene-copy + rendering detach/attach + scene_manager mode
transitions that happen when the user toggles Game Mode. The tcgui editor
delegates to this model and reacts to ``state_changed`` to update buttons /
status bar / menu actions.
"""
from __future__ import annotations

from typing import Callable

from tcbase import log
from termin.editor_core.signal import Signal


class _GameModeSession:
    def __init__(
        self,
        *,
        editor_scene_name: str,
        game_scene_name: str,
        game_scene: object,
        render_binding: object,
        saved_tree_expanded_uuids: list[str] | None,
    ) -> None:
        self.editor_scene_name = editor_scene_name
        self.game_scene_name = game_scene_name
        self.game_scene = game_scene
        self.render_binding = render_binding
        self.saved_tree_expanded_uuids = saved_tree_expanded_uuids


class GameModeModel:
    def __init__(
        self,
        scene_manager,
        editor_connector,
        rendering_controller,
        get_editor_scene_name: Callable[[], str | None],
        render_binding_factory: Callable[[str], object],
        scene_tree_controller=None,
        prepare_code_for_play: Callable[[], bool] | None = None,
    ):
        self._scene_manager = scene_manager
        self._editor_connector = editor_connector
        self._rendering_controller = rendering_controller
        self._get_editor_scene_name = get_editor_scene_name
        self._render_binding_factory = render_binding_factory
        self._scene_tree_controller = scene_tree_controller
        self._prepare_code_for_play = prepare_code_for_play or (lambda: True)

        self._game_session: _GameModeSession | None = None
        self._transitioning = False

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
        session = self._game_session
        return None if session is None else session.game_scene_name

    @property
    def is_game_mode(self) -> bool:
        return self._game_session is not None

    @property
    def is_game_paused(self) -> bool:
        if not self.is_game_mode:
            return False
        from termin.engine import scene as engine_scene
        SceneMode = engine_scene.SceneMode
        session = self._game_session
        assert session is not None
        return self._scene_manager.get_mode(session.game_scene_name) == SceneMode.STOP

    # ------------------------------------------------------------------
    # Transitions
    # ------------------------------------------------------------------

    def toggle_game_mode(self) -> None:
        if self._transitioning:
            log.error("[GameModeModel] Reentrant Play/Stop transition rejected")
            return
        self._transitioning = True
        try:
            if self.is_game_mode:
                self._stop_game_mode()
            else:
                self._start_game_mode()
        finally:
            self._transitioning = False

    def toggle_pause(self) -> None:
        session = self._game_session
        if self._transitioning or session is None:
            return
        from termin.engine import scene as engine_scene
        SceneMode = engine_scene.SceneMode
        current_mode = self._scene_manager.get_mode(session.game_scene_name)
        if current_mode == SceneMode.PLAY:
            self._scene_manager.set_mode(session.game_scene_name, SceneMode.STOP)
        else:
            self._scene_manager.set_mode(session.game_scene_name, SceneMode.PLAY)
        self.state_changed.emit(self)

    def _start_game_mode(self) -> None:
        if self.is_game_mode:
            return
        editor_scene_name = self._get_editor_scene_name()
        if editor_scene_name is None:
            return

        try:
            code_ready = self._prepare_code_for_play()
        except Exception:
            log.exception("[GameModeModel] Code preparation before Play failed")
            return
        if not code_ready:
            log.error("[GameModeModel] Play blocked because code update failed")
            return

        editor_scene = self._scene_manager.get_scene(editor_scene_name)
        if editor_scene is None:
            log.error(
                f"[GameModeModel] Play blocked because editor scene "
                f"'{editor_scene_name}' is missing"
            )
            return

        from termin.engine import scene as engine_scene
        SceneMode = engine_scene.SceneMode

        saved_tree_expanded_uuids = None
        if self._scene_tree_controller is not None:
            saved_tree_expanded_uuids = (
                self._scene_tree_controller.get_expanded_entity_uuids()
            )

        self._save_editor_viewport_camera_to_scene(editor_scene)

        editor_mode = self._scene_manager.get_mode(editor_scene_name)
        game_scene_name = f"{editor_scene_name}(game)"
        try:
            render_binding = self._render_binding_factory(editor_scene_name)
        except Exception:
            log.exception("[GameModeModel] Failed to create primary render binding")
            return
        editor_switch_attempted = False

        try:
            render_binding.sync_current()
            game_scene = self._scene_manager.copy_scene(
                editor_scene_name,
                game_scene_name,
            )
            if game_scene is None:
                raise RuntimeError(
                    f"failed to copy editor scene '{editor_scene_name}'"
                )

            render_binding.rebind(game_scene_name)
            editor_switch_attempted = True
            self._attach_editor(
                game_scene_name,
                restore_state=False,
                transfer_camera_state=True,
                update_editor_scene_name=False,
            )

            self._scene_manager.set_mode(editor_scene_name, SceneMode.INACTIVE)
            self._scene_manager.set_mode(game_scene_name, SceneMode.PLAY)
        except Exception:
            log.exception("[GameModeModel] Play transition failed; rolling back")
            rollback_ok = self._rollback_failed_start(
                editor_scene_name=editor_scene_name,
                editor_mode=editor_mode,
                game_scene_name=game_scene_name,
                render_binding=render_binding,
                editor_switch_attempted=editor_switch_attempted,
            )
            if rollback_ok and self._scene_manager.has_scene(game_scene_name):
                self._scene_manager.close_scene(game_scene_name)
            elif self._scene_manager.has_scene(game_scene_name):
                log.error(
                    f"[GameModeModel] Candidate game scene '{game_scene_name}' retained "
                    "because transition rollback was incomplete"
                )
            return

        session = _GameModeSession(
            editor_scene_name=editor_scene_name,
            game_scene_name=game_scene_name,
            game_scene=game_scene,
            render_binding=render_binding,
            saved_tree_expanded_uuids=saved_tree_expanded_uuids,
        )
        self._game_session = session
        self.state_changed.emit(self)
        self.mode_entered.emit(True, game_scene, saved_tree_expanded_uuids)

    def _stop_game_mode(self) -> None:
        session = self._game_session
        if session is None:
            return

        from termin.engine import scene as engine_scene
        SceneMode = engine_scene.SceneMode

        editor_scene = self._scene_manager.get_scene(session.editor_scene_name)
        if editor_scene is None:
            log.error(
                f"[GameModeModel] Stop transition failed: editor scene "
                f"'{session.editor_scene_name}' is missing"
            )
            return

        editor_mode = self._scene_manager.get_mode(session.editor_scene_name)
        game_mode = self._scene_manager.get_mode(session.game_scene_name)
        editor_switch_attempted = False

        try:
            session.render_binding.rebind(session.editor_scene_name)
            editor_switch_attempted = True
            self._attach_editor(
                session.editor_scene_name,
                restore_state=True,
                transfer_camera_state=False,
                update_editor_scene_name=True,
            )
            self._scene_manager.set_mode(session.editor_scene_name, SceneMode.STOP)
            self._scene_manager.set_mode(session.game_scene_name, SceneMode.STOP)
            self._scene_manager.close_scene(session.game_scene_name)
        except Exception:
            log.exception("[GameModeModel] Stop transition failed; rolling back")
            if self._scene_manager.has_scene(session.game_scene_name):
                self._rollback_failed_stop(
                    session=session,
                    editor_mode=editor_mode,
                    game_mode=game_mode,
                    editor_switch_attempted=editor_switch_attempted,
                )
                return
            log.error(
                "[GameModeModel] Game scene was destroyed during a failed Stop; "
                "committing the restored editor state"
            )

        self._game_session = None
        self.state_changed.emit(self)
        self.mode_entered.emit(
            False,
            editor_scene,
            session.saved_tree_expanded_uuids,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _attach_editor(
        self,
        scene_name: str,
        *,
        restore_state: bool,
        transfer_camera_state: bool,
        update_editor_scene_name: bool,
    ) -> None:
        result = self._editor_connector.attach_editor_to_scene(
            scene_name,
            restore_state=restore_state,
            transfer_camera_state=transfer_camera_state,
            update_editor_scene_name=update_editor_scene_name,
        )
        if result is False:
            raise RuntimeError(f"failed to attach editor to scene '{scene_name}'")

    def _rollback_failed_start(
        self,
        *,
        editor_scene_name: str,
        editor_mode,
        game_scene_name: str,
        render_binding,
        editor_switch_attempted: bool,
    ) -> bool:
        rollback_ok = True
        if editor_switch_attempted:
            try:
                self._attach_editor(
                    editor_scene_name,
                    restore_state=True,
                    transfer_camera_state=False,
                    update_editor_scene_name=True,
                )
            except Exception:
                rollback_ok = False
                log.exception(
                    f"[GameModeModel] Play rollback failed to restore editor scene "
                    f"'{editor_scene_name}'"
                )

        if render_binding.scene_name != editor_scene_name:
            try:
                render_binding.rebind(editor_scene_name)
            except Exception:
                rollback_ok = False
                log.exception(
                    f"[GameModeModel] Play rollback failed to restore primary render "
                    f"scene '{editor_scene_name}'"
                )
        if render_binding.may_reference(game_scene_name):
            rollback_ok = False

        try:
            self._scene_manager.set_mode(editor_scene_name, editor_mode)
        except Exception:
            rollback_ok = False
            log.exception(
                "[GameModeModel] Play rollback failed to restore editor scene mode"
            )
        return rollback_ok

    def _rollback_failed_stop(
        self,
        *,
        session: _GameModeSession,
        editor_mode,
        game_mode,
        editor_switch_attempted: bool,
    ) -> None:
        try:
            self._scene_manager.set_mode(session.editor_scene_name, editor_mode)
            self._scene_manager.set_mode(session.game_scene_name, game_mode)
        except Exception:
            log.exception("[GameModeModel] Stop rollback failed to restore scene modes")

        if editor_switch_attempted:
            try:
                self._attach_editor(
                    session.game_scene_name,
                    restore_state=False,
                    transfer_camera_state=True,
                    update_editor_scene_name=False,
                )
            except Exception:
                log.exception(
                    "[GameModeModel] Stop rollback failed to restore game editor attachment"
                )

        if session.render_binding.scene_name != session.game_scene_name:
            try:
                session.render_binding.rebind(session.game_scene_name)
            except Exception:
                log.exception(
                    "[GameModeModel] Stop rollback failed to restore game render attachment"
                )

    def _save_editor_viewport_camera_to_scene(self, scene) -> None:
        if self._rendering_controller is None:
            return
        editor_display = self._rendering_controller.editor_display
        if editor_display is None or not editor_display.viewports:
            return
        viewport = editor_display.viewports[0]
        render_target = viewport.render_target
        camera_name = None
        if render_target is not None and render_target.camera is not None and render_target.camera.entity is not None:
            camera_name = render_target.camera.entity.name
        scene.set_metadata_value("termin.editor.viewport_camera_name", camera_name or "")
