"""Editor Play/Stop/Pause composition over EngineCore RuntimeSession."""

from __future__ import annotations

from collections.abc import Callable

from tcbase import log
from termin.editor_core.signal import Signal


class _GameModeSession:
    def __init__(
        self,
        *,
        editor_scene_name: str,
        editor_mode,
        runtime_scene,
        context,
        saved_tree_expanded_uuids: list[str] | None,
    ) -> None:
        self.editor_scene_name = editor_scene_name
        self.editor_mode = editor_mode
        self.runtime_scene = runtime_scene
        self.context = context
        self.primary_scene = None
        self.saved_tree_expanded_uuids = saved_tree_expanded_uuids


class GameModeModel:
    """Own editor composition around one EngineCore world run.

    EngineCore/RuntimeSession own the gameplay primary association and render
    transaction. This model owns only the runtime copy and editor presentation.
    """

    def __init__(
        self,
        engine,
        editor_connector,
        render_scene_session,
        rendering_controller,
        get_editor_scene_name: Callable[[], str | None],
        scene_tree_controller=None,
        prepare_code_for_play: Callable[[], bool] | None = None,
        create_controller_for_play: Callable[[], object | None] | None = None,
    ) -> None:
        self._engine = engine
        self._scene_manager = engine.scene_manager
        self._editor_connector = editor_connector
        self._render_scene_session = render_scene_session
        self._rendering_controller = rendering_controller
        self._get_editor_scene_name = get_editor_scene_name
        self._scene_tree_controller = scene_tree_controller
        self._prepare_code_for_play = prepare_code_for_play or (lambda: True)
        self._create_controller_for_play = create_controller_for_play or (lambda: None)

        self._game_session: _GameModeSession | None = None
        self._transitioning = False

        self.state_changed = Signal()
        self.mode_entered = Signal()

    @property
    def game_scene_name(self) -> str | None:
        session = self._game_session
        if session is None:
            return None
        scene = session.primary_scene or session.runtime_scene
        return scene.name

    @property
    def is_game_mode(self) -> bool:
        return self._game_session is not None

    @property
    def is_game_paused(self) -> bool:
        session = self._game_session
        if session is None:
            return False
        primary = session.context.primary_scene
        if primary is None:
            return False
        from termin.engine import scene as engine_scene

        return self._scene_manager.get_mode(primary.name) == engine_scene.SceneMode.STOP

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
        primary = session.context.primary_scene
        if primary is None:
            log.error("[GameModeModel] Cannot pause before the primary scene is active")
            return
        from termin.engine import scene as engine_scene

        current_mode = self._scene_manager.get_mode(primary.name)
        next_mode = (
            engine_scene.SceneMode.STOP
            if current_mode == engine_scene.SceneMode.PLAY
            else engine_scene.SceneMode.PLAY
        )
        self._scene_manager.set_mode(primary.name, next_mode)
        self.state_changed.emit(self)

    def refresh_primary_scene(self) -> None:
        """Observe an EngineCore commit and update editor-owned presentation."""
        session = self._game_session
        if session is None or self._transitioning:
            return
        primary = session.context.primary_scene
        if primary is None:
            return
        if session.primary_scene is not None and primary.equal(session.primary_scene):
            return

        try:
            self._render_scene_session.reconcile_attached_scene(primary)
        except Exception:
            log.exception(
                "[GameModeModel] Failed to reconcile editor rendering for "
                f"primary scene '{primary.name}'"
            )
        try:
            self._attach_editor(
                primary.name,
                restore_state=False,
                transfer_camera_state=True,
                update_editor_scene_name=False,
            )
        except Exception:
            log.exception(
                "[GameModeModel] Failed to present committed primary scene "
                f"'{primary.name}' in the editor"
            )

        session.primary_scene = primary
        self.state_changed.emit(self)
        self.mode_entered.emit(
            True,
            primary,
            session.saved_tree_expanded_uuids,
        )

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

        try:
            controller = self._create_controller_for_play()
        except Exception:
            log.exception("[GameModeModel] Failed to create the selected WorldController")
            return
        if not self._engine.begin_session(controller):
            log.error("[GameModeModel] EngineCore refused to begin RuntimeSession")
            return

        from termin.engine import require_world_context
        from termin.engine import scene as engine_scene

        saved_tree_expanded_uuids = None
        if self._scene_tree_controller is not None:
            saved_tree_expanded_uuids = self._scene_tree_controller.get_expanded_entity_uuids()

        self._save_editor_viewport_camera_to_scene(editor_scene)
        editor_mode = self._scene_manager.get_mode(editor_scene_name)
        runtime_scene_name = f"{editor_scene_name}(game)"
        runtime_scene = None
        runtime_bound = False
        editor_render_detached = False
        try:
            self._render_scene_session.sync_scene_render_state(editor_scene_name)
            runtime_scene = self._scene_manager.copy_scene(
                editor_scene_name,
                runtime_scene_name,
            )
            if runtime_scene is None:
                raise RuntimeError(f"failed to copy editor scene '{editor_scene_name}'")
            if not self._engine.bind_runtime_scene(runtime_scene):
                raise RuntimeError(f"failed to bind runtime scene '{runtime_scene_name}'")
            runtime_bound = True

            self._render_scene_session.detach(editor_scene_name, save_state=False)
            editor_render_detached = True
            context = require_world_context(runtime_scene, "Editor Play")
            if not context.request_primary_scene(runtime_scene):
                raise RuntimeError(f"failed to request primary scene '{runtime_scene_name}'")
            self._scene_manager.set_mode(
                editor_scene_name,
                engine_scene.SceneMode.INACTIVE,
            )
        except Exception:
            log.exception("[GameModeModel] Play setup failed; restoring editor state")
            if runtime_bound and runtime_scene is not None:
                if not self._engine.unbind_runtime_scene(runtime_scene):
                    log.error("[GameModeModel] Failed to unbind rejected runtime copy")
            if runtime_scene is not None and self._scene_manager.has_scene(runtime_scene_name):
                self._scene_manager.close_scene(runtime_scene_name)
            if editor_render_detached:
                try:
                    self._render_scene_session.attach(editor_scene_name)
                except Exception:
                    log.exception("[GameModeModel] Failed to restore editor render attachment")
            try:
                self._scene_manager.set_mode(editor_scene_name, editor_mode)
            except Exception:
                log.exception("[GameModeModel] Failed to restore editor scene mode")
            if not self._engine.end_session():
                log.error("[GameModeModel] RuntimeSession cleanup reported a failure")
            return

        self._game_session = _GameModeSession(
            editor_scene_name=editor_scene_name,
            editor_mode=editor_mode,
            runtime_scene=runtime_scene,
            context=context,
            saved_tree_expanded_uuids=saved_tree_expanded_uuids,
        )
        self.state_changed.emit(self)

    def _stop_game_mode(self) -> None:
        session = self._game_session
        if session is None:
            return
        editor_scene = self._scene_manager.get_scene(session.editor_scene_name)
        if editor_scene is None:
            log.error(
                f"[GameModeModel] Stop blocked because editor scene "
                f"'{session.editor_scene_name}' is missing"
            )
            return

        editor_presented = False
        editor_render_attached = False
        try:
            self._attach_editor(
                session.editor_scene_name,
                restore_state=True,
                transfer_camera_state=False,
                update_editor_scene_name=True,
            )
            editor_presented = True
            self._render_scene_session.attach(session.editor_scene_name)
            editor_render_attached = True
        except Exception:
            log.exception("[GameModeModel] Stop could not release editor presentation")
            if editor_render_attached:
                try:
                    self._render_scene_session.detach(
                        session.editor_scene_name,
                        save_state=False,
                    )
                except Exception:
                    log.exception("[GameModeModel] Failed to remove partial editor render restore")
            if editor_presented and session.primary_scene is not None:
                try:
                    self._attach_editor(
                        session.primary_scene.name,
                        restore_state=False,
                        transfer_camera_state=True,
                        update_editor_scene_name=False,
                    )
                except Exception:
                    log.exception("[GameModeModel] Failed to restore gameplay editor presentation")
            return

        ended_cleanly = self._engine.end_session()
        if self._engine.has_runtime_session:
            log.error("[GameModeModel] EngineCore refused to end RuntimeSession")
            try:
                self._render_scene_session.detach(
                    session.editor_scene_name,
                    save_state=False,
                )
            except Exception:
                log.exception(
                    "[GameModeModel] Failed to undo editor render restore after rejected Stop"
                )
            return
        if not ended_cleanly:
            log.error("[GameModeModel] RuntimeSession ended with lifecycle failures")

        try:
            self._render_scene_session.reconcile_attached_scene(editor_scene)
        except Exception:
            log.exception("[GameModeModel] Failed to reconcile editor rendering after Stop")

        runtime_scene_name = session.runtime_scene.name
        if self._scene_manager.has_scene(runtime_scene_name):
            self._scene_manager.close_scene(runtime_scene_name)
        self._scene_manager.set_mode(session.editor_scene_name, session.editor_mode)

        self._game_session = None
        self.state_changed.emit(self)
        self.mode_entered.emit(
            False,
            editor_scene,
            session.saved_tree_expanded_uuids,
        )

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

    def _save_editor_viewport_camera_to_scene(self, scene) -> None:
        if self._rendering_controller is None:
            return
        editor_display = self._rendering_controller.editor_display
        if editor_display is None or not editor_display.viewports:
            return
        viewport = editor_display.viewports[0]
        render_target = viewport.render_target
        camera_name = None
        if (
            render_target is not None
            and render_target.camera is not None
            and render_target.camera.entity is not None
        ):
            camera_name = render_target.camera.entity.name
        scene.set_metadata_value("termin.editor.viewport_camera_name", camera_name or "")
