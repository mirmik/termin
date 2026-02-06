from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QLabel, QStatusBar

from termin.editor.scene_manager import SceneMode

if TYPE_CHECKING:
    from termin.editor.editor_window import EditorWindow


class EditorModeController:
    def __init__(self, window: "EditorWindow") -> None:
        self._window = window
        self._status_bar_label: QLabel | None = None
        self._fps_smooth: float | None = None
        self._fps_alpha: float = 0.1  # f_new = f_prev*(1-α) + f_curr*α
        self._game_scene_name: str | None = None
        self._saved_tree_expanded_uuids: list[str] | None = None
        self._is_fullscreen: bool = False
        self._pre_fullscreen_state: dict | None = None

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
        return self._window.scene_manager.get_mode(self._game_scene_name) == SceneMode.STOP

    @property
    def is_fullscreen(self) -> bool:
        return self._is_fullscreen

    # ----------- status bar -----------#

    def init_status_bar(self) -> None:
        """
        Создаёт полосу статуса внизу окна. FPS будем писать сюда в игровом режиме.
        """
        status_bar: QStatusBar = self._window.statusBar()
        status_bar.setSizeGripEnabled(False)

        label = QLabel("Editor mode")
        status_bar.addPermanentWidget(label, 1)
        self._status_bar_label = label

    def update_status_bar(self) -> None:
        """Заполняет текст статус-бара (FPS в игре, режим редактора вне игры)."""
        if self._status_bar_label is None:
            return

        if not self.is_game_mode:
            self._status_bar_label.setText("Editor mode")
            return

        if self.is_game_paused:
            self._status_bar_label.setText("Game mode (PAUSED)")
            return

        if self._fps_smooth is None:
            self._status_bar_label.setText("FPS: --")
            return

        self._status_bar_label.setText(f"FPS: {self._fps_smooth:.1f}")

    def reset_fps_smooth(self) -> None:
        self._fps_smooth = None

    # ----------- fullscreen -----------#

    def toggle_fullscreen(self) -> None:
        """Toggle fullscreen mode - expand viewport to fill entire screen."""
        if self._is_fullscreen:
            self._exit_fullscreen()
        else:
            self._enter_fullscreen()

    def exit_fullscreen(self) -> None:
        """Exit fullscreen mode if active."""
        if self._is_fullscreen:
            self._exit_fullscreen()

    def _enter_fullscreen(self) -> None:
        """Enter fullscreen mode."""
        # Save current state - which widgets were visible
        self._pre_fullscreen_state = {
            "left_visible": self._window.leftTabWidget.isVisible() if self._window.leftTabWidget else True,
            "inspector_visible": self._window.inspectorContainer.isVisible() if self._window.inspectorContainer else True,
            "bottom_visible": self._get_bottom_widget_visible(),
            "toolbar_visible": self._window._viewport_toolbar.isVisible() if self._window._viewport_toolbar else True,
            "tabbar_visible": self._window._center_tab_widget.tabBar().isVisible() if self._window._center_tab_widget else True,
            "menubar_visible": self._window.menuBar().isVisible(),
            "statusbar_visible": self._window.statusBar().isVisible(),
            "window_state": self._window.windowState(),
        }

        # Hide side panels directly
        if self._window.leftTabWidget:
            self._window.leftTabWidget.hide()
        if self._window.inspectorContainer:
            self._window.inspectorContainer.hide()

        # Hide bottom panel (project browser area)
        self._set_bottom_widget_visible(False)

        # Hide viewport toolbar (with Play button)
        if self._window._viewport_toolbar:
            self._window._viewport_toolbar.hide()

        # Hide tab bar of center tab widget
        if self._window._center_tab_widget:
            self._window._center_tab_widget.tabBar().hide()

        # Hide menu and status bars
        self._window.menuBar().hide()
        self._window.statusBar().hide()

        # Enter fullscreen
        self._window.showFullScreen()
        self._is_fullscreen = True

        # Update menu checkbox
        if self._window._menu_bar_controller:
            self._window._menu_bar_controller.update_fullscreen_action()

    def _exit_fullscreen(self) -> None:
        """Exit fullscreen mode."""
        # Exit fullscreen first
        self._window.showNormal()

        # Restore saved state
        if self._pre_fullscreen_state:
            state = self._pre_fullscreen_state

            # Restore window state
            if state.get("window_state"):
                self._window.setWindowState(state["window_state"])

            # Restore menu and status bars
            if state.get("menubar_visible", True):
                self._window.menuBar().show()
            if state.get("statusbar_visible", True):
                self._window.statusBar().show()

            # Restore side panels
            if self._window.leftTabWidget and state.get("left_visible", True):
                self._window.leftTabWidget.show()
            if self._window.inspectorContainer and state.get("inspector_visible", True):
                self._window.inspectorContainer.show()

            # Restore bottom panel
            if state.get("bottom_visible", True):
                self._set_bottom_widget_visible(True)

            # Restore viewport toolbar
            if self._window._viewport_toolbar and state.get("toolbar_visible", True):
                self._window._viewport_toolbar.show()

            # Restore tab bar
            if self._window._center_tab_widget and state.get("tabbar_visible", True):
                self._window._center_tab_widget.tabBar().show()

            self._pre_fullscreen_state = None

        self._is_fullscreen = False

        # Update menu checkbox
        if self._window._menu_bar_controller:
            self._window._menu_bar_controller.update_fullscreen_action()

    def _get_bottom_widget_visible(self) -> bool:
        """Get visibility of bottom area in vertical splitter."""
        if self._window.verticalSplitter and self._window.verticalSplitter.count() > 1:
            widget = self._window.verticalSplitter.widget(1)
            return widget.isVisible() if widget else True
        return True

    def _set_bottom_widget_visible(self, visible: bool) -> None:
        """Set visibility of bottom area in vertical splitter."""
        if self._window.verticalSplitter and self._window.verticalSplitter.count() > 1:
            widget = self._window.verticalSplitter.widget(1)
            if widget:
                if visible:
                    widget.show()
                else:
                    widget.hide()

    # ----------- game mode -----------#

    def toggle_game_mode(self) -> None:
        """Переключает режим игры."""
        if self.is_game_mode:
            self._stop_game_mode()
        else:
            self._start_game_mode()

    def toggle_pause(self) -> None:
        """Переключает паузу в игровом режиме."""
        if not self.is_game_mode or self._game_scene_name is None:
            return

        current_mode = self._window.scene_manager.get_mode(self._game_scene_name)
        if current_mode == SceneMode.PLAY:
            # Pause: PLAY -> STOP
            self._window.scene_manager.set_mode(self._game_scene_name, SceneMode.STOP)
            if self._window._pause_button is not None:
                self._window._pause_button.setChecked(True)
        else:
            # Resume: STOP -> PLAY
            self._window.scene_manager.set_mode(self._game_scene_name, SceneMode.PLAY)
            if self._window._pause_button is not None:
                self._window._pause_button.setChecked(False)

        self.update_status_bar()
        self._window._request_viewport_update()

    def _start_game_mode(self) -> None:
        """Входит в игровой режим."""
        if self.is_game_mode:
            return
        if self._window._editor_scene_name is None:
            return

        editor_scene = self._window.scene_manager.get_scene(self._window._editor_scene_name)
        if editor_scene is None:
            return

        # Сохраняем раскрытые ноды дерева (для переноса в game scene и обратно)
        self._saved_tree_expanded_uuids = None
        if self._window.scene_tree_controller is not None:
            self._saved_tree_expanded_uuids = (
                self._window.scene_tree_controller.get_expanded_entity_uuids()
            )

        # Сохраняем камеру editor viewport в editor сцену
        self._save_editor_viewport_camera_to_scene(editor_scene)

        # Сохраняем viewport_configs перед копированием (для восстановления через attach_scene)
        if self._window._rendering_controller is not None:
            self._window._rendering_controller.sync_viewport_configs_to_scene(editor_scene)

        # Сохраняем состояние EditorEntities в editor_scene для восстановления после game mode
        if self._window._editor_attachment is not None:
            self._window._editor_attachment.save_state()

        # Создаём копию сцены для game mode (копируется и editor_viewport_camera_name)
        self._game_scene_name = f"{self._window._editor_scene_name}(game)"
        game_scene = self._window.scene_manager.copy_scene(
            self._window._editor_scene_name,
            self._game_scene_name,
        )

        # Detach from editor_scene, attach to game_scene with same camera state
        if self._window._editor_attachment is not None:
            self._window._editor_attachment.attach(game_scene, transfer_camera_state=True)
        self._window._sync_attachment_refs()

        # Устанавливаем режимы (таймер запустится автоматически)
        self._window.scene_manager.set_mode(self._window._editor_scene_name, SceneMode.INACTIVE)
        self._window.scene_manager.set_mode(self._game_scene_name, SceneMode.PLAY)

        # Detach editor scene from RenderingManager before attaching game scene
        if self._window._rendering_controller is not None:
            self._window._rendering_controller.detach_scene(editor_scene)

        self._on_game_mode_changed(True, game_scene, self._saved_tree_expanded_uuids)

    def _stop_game_mode(self) -> None:
        """Выходит из игрового режима."""
        if not self.is_game_mode:
            return

        # Detach from game_scene (don't save state - we discard game changes)
        if self._window._editor_attachment is not None:
            self._window._editor_attachment.detach(save_state=False)

        # Detach game scene from RenderingManager before closing
        game_scene = self._window.scene_manager.get_scene(self._game_scene_name)
        if game_scene is not None and self._window._rendering_controller is not None:
            self._window._rendering_controller.detach_scene(game_scene)

        # Закрываем game сцену (теперь is_game_mode станет False)
        if self._game_scene_name is not None:
            self._window.scene_manager.close_scene(self._game_scene_name)
        self._game_scene_name = None

        # Возвращаемся к editor сцене
        self._window.scene_manager.set_mode(self._window._editor_scene_name, SceneMode.STOP)
        editor_scene = self._window.scene_manager.get_scene(self._window._editor_scene_name)

        # Attach to editor_scene, restore state from scene.editor_entities_data
        if self._window._editor_attachment is not None:
            self._window._editor_attachment.attach(editor_scene, restore_state=True)
        self._window._sync_attachment_refs()

        # Создаём viewports для editor сцены (камера читается из scene.editor_viewport_camera_name)
        # Передаём сохранённые expanded_uuids для восстановления состояния дерева
        self._on_game_mode_changed(False, editor_scene, self._saved_tree_expanded_uuids)
        self._saved_tree_expanded_uuids = None  # Очищаем после использования

    def _save_editor_viewport_camera_to_scene(self, scene) -> None:
        """Сохраняет имя камеры editor viewport в сцену."""
        if self._window._rendering_controller is None:
            return
        editor_display = self._window._rendering_controller.editor_display
        if editor_display is None or not editor_display.viewports:
            return
        viewport = editor_display.viewports[0]
        camera_name = None
        if viewport.camera is not None and viewport.camera.entity is not None:
            camera_name = viewport.camera.entity.name
        scene.set_metadata_value("termin.editor.viewport_camera_name", camera_name)

    def _on_game_mode_changed(
        self,
        is_playing: bool,
        scene,
        expanded_uuids: list[str] | None = None,
    ) -> None:
        """Колбэк при изменении игрового режима."""
        if self._window._rendering_controller is None:
            return

        # Обычные дисплеи (не Editor) - через attach_scene (читает scene.viewport_configs)
        self._window._rendering_controller.attach_scene(scene)

        # Editor display - viewport уже создан через EditorSceneAttachment.attach()
        # C++ EditorDisplayInputManager handles both modes

        # Обновляем scene tree на новую сцену
        if self._window.scene_tree_controller is not None:
            self._window.scene_tree_controller.set_scene(scene)
            self._window.scene_tree_controller.rebuild()
            # Восстанавливаем раскрытые ноды (сохранённые из editor scene)
            if expanded_uuids:
                self._window.scene_tree_controller.set_expanded_entity_uuids(expanded_uuids)

        # Очищаем инспектор (выбранный entity мог измениться)
        self._window.show_entity_inspector(None)

        # Обновляем framegraph debugger если открыт
        self._window._refresh_framegraph_debugger()

        # Сбрасываем сглаженное значение FPS при входе/выходе
        self._fps_smooth = None
        self._update_game_mode_ui()
        self._window._request_viewport_update()

    def _update_game_mode_ui(self) -> None:
        """Update UI elements based on game mode state."""
        is_playing = self.is_game_mode

        if self._window._menu_bar_controller is not None:
            self._window._menu_bar_controller.update_play_action(is_playing)

        # Обновляем кнопку Play в toolbar
        if self._window._play_button is not None:
            self._window._play_button.setChecked(is_playing)
            self._window._play_button.setText("Stop" if is_playing else "Play")

        # Показываем/скрываем кнопку Pause
        if self._window._pause_button is not None:
            self._window._pause_button.setVisible(is_playing)
            if not is_playing:
                self._window._pause_button.setChecked(False)

        self._window._update_window_title()
        self.update_status_bar()
