from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QLabel, QStatusBar

from termin.editor.scene_manager import SceneMode
from termin.editor_core.game_mode_model import GameModeModel

if TYPE_CHECKING:
    from termin.editor.editor_window import EditorWindow


class EditorModeController:
    def __init__(self, window: "EditorWindow") -> None:
        self._window = window
        self._status_bar_label: QLabel | None = None
        self._fps_smooth: float | None = None
        self._fps_alpha: float = 0.1  # f_new = f_prev*(1-α) + f_curr*α
        self._is_fullscreen: bool = False
        self._pre_fullscreen_state: dict | None = None

        # Model is created lazily in bind_late() — EditorModeController is
        # constructed at the very top of EditorWindow.__init__, before
        # scene_manager / rendering_controller / editor_attachment exist.
        self._model: GameModeModel | None = None

    def bind_late(self) -> None:
        """Called by EditorWindow once scene_manager / editor_attachment /
        rendering_controller / scene_tree_controller are all initialized."""
        self._model = GameModeModel(
            scene_manager=self._window.scene_manager,
            editor_connector=self._window,
            rendering_controller=self._window._rendering_controller,
            get_editor_scene_name=lambda: self._window._editor_scene_name,
            scene_tree_controller=self._window.scene_tree_controller,
        )
        self._model.state_changed.connect(self._on_state_changed)
        self._model.mode_entered.connect(self._on_mode_entered)

    @property
    def model(self) -> "GameModeModel | None":
        return self._model

    @property
    def game_scene_name(self) -> str | None:
        return self._model.game_scene_name if self._model is not None else None

    @property
    def is_game_mode(self) -> bool:
        return self._model.is_game_mode if self._model is not None else False

    @property
    def is_game_paused(self) -> bool:
        return self._model.is_game_paused if self._model is not None else False

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
        if self._model is None:
            return
        self._model.toggle_game_mode()

    def toggle_pause(self) -> None:
        if self._model is None:
            return
        self._model.toggle_pause()
        if self._window._pause_button is not None:
            self._window._pause_button.setChecked(self._model.is_game_paused)
        self.update_status_bar()
        self._window._request_viewport_update()

    def _on_state_changed(self, _model) -> None:
        """Called by model after toggle_pause / start / stop to refresh UI."""
        self._update_game_mode_ui()

    def _on_mode_entered(
        self,
        is_playing: bool,
        scene,
        expanded_uuids: list[str] | None,
    ) -> None:
        """Called by model after _start/_stop — rebuilds scene tree, clears
        inspector, refreshes framegraph debugger. View-specific glue."""
        self._window._sync_attachment_refs()

        if self._window.scene_tree_controller is not None:
            self._window.scene_tree_controller.set_scene(scene)
            self._window.scene_tree_controller.rebuild()
            if expanded_uuids:
                self._window.scene_tree_controller.set_expanded_entity_uuids(expanded_uuids)

        self._window.show_entity_inspector(None)
        self._window._refresh_framegraph_debugger()

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
