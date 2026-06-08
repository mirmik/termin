"""Game mode toolbar and status presentation for EditorWindowTcgui."""

from __future__ import annotations

from typing import Callable


class GameModeUiController:
    def __init__(
        self,
        *,
        update_play_action: Callable[[bool], None],
        update_window_title: Callable[[], None],
        request_viewport_update: Callable[[], None],
    ) -> None:
        self._update_play_action = update_play_action
        self._update_window_title = update_window_title
        self._request_viewport_update = request_viewport_update
        self._play_button = None
        self._pause_button = None
        self._status_bar = None

    def set_widgets(
        self,
        *,
        play_button,
        pause_button,
        status_bar,
    ) -> None:
        self._play_button = play_button
        self._pause_button = pause_button
        self._status_bar = status_bar

    def toggle_pause(self, game_mode_model) -> None:
        game_mode_model.toggle_pause()
        self.update_pause_state(game_mode_model.is_game_paused)
        self._request_viewport_update()

    def update_pause_state(self, is_paused: bool) -> None:
        from tcgui.widgets.theme import current_theme as theme

        if self._pause_button is None:
            return
        if is_paused:
            self._pause_button.text = "Resume"
            self._pause_button.background_color = (0.85, 0.63, 0.29, 1.0)
        else:
            self._pause_button.text = "Pause"
            self._pause_button.background_color = theme.bg_surface

    def update_mode(self, is_playing: bool) -> None:
        from tcgui.widgets.theme import current_theme as theme

        if self._play_button is not None:
            self._play_button.text = "Stop" if is_playing else "Play"
            self._play_button.background_color = (
                theme.accent if is_playing else theme.bg_surface
            )

        if self._pause_button is not None:
            self._pause_button.visible = is_playing
            if not is_playing:
                self._pause_button.background_color = theme.bg_surface
                self._pause_button.text = "Pause"

        self._update_play_action(is_playing)
        self._update_window_title()

        if self._status_bar is not None:
            self._status_bar.text = "Game mode" if is_playing else "Editor mode"
