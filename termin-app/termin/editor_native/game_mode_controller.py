"""Native command and status projection for GameModeModel."""

from __future__ import annotations


class NativeGameModeController:
    def __init__(
        self,
        model,
        *,
        menu_bar,
        game_menu_model,
        game_play_command: int,
        tool_bar,
        toolbar_model,
        toolbar_play_command: int,
        scene_hierarchy,
        status_bar,
        request_render,
    ) -> None:
        self.model = model
        self._game_menu_model = game_menu_model
        self._game_play_command = game_play_command
        self._toolbar_model = toolbar_model
        self._toolbar_play_command = toolbar_play_command
        self._scene_hierarchy = scene_hierarchy
        self._status_bar = status_bar
        self._request_render = request_render
        self._closed = False

        menu_bar.connect_activated(self._menu_activated)
        tool_bar.connect_activated(self._toolbar_activated)
        model.state_changed.connect(self._state_changed)
        model.mode_entered.connect(self._mode_entered)
        self._state_changed(model)

    def _menu_activated(self, _index: int, command_id: int, _command) -> None:
        if command_id == self._game_play_command:
            self.model.toggle_game_mode()

    def _toolbar_activated(self, _index: int, command_id: int, _command) -> None:
        if command_id == self._toolbar_play_command:
            self.model.toggle_game_mode()

    def _state_changed(self, model) -> None:
        label = "Stop" if model.is_game_mode else "Play"
        self._set_command_label(self._game_menu_model, self._game_play_command, label)
        self._set_command_label(self._toolbar_model, self._toolbar_play_command, label)
        self._status_bar.text = "Game mode" if model.is_game_mode else "Editor mode"
        self._request_render()

    def _mode_entered(self, _is_playing: bool, _scene, expanded_uuids) -> None:
        if expanded_uuids:
            self._scene_hierarchy.set_expanded_entity_uuids(expanded_uuids)
        self._request_render()

    @staticmethod
    def _set_command_label(command_model, command_id: int, label: str) -> None:
        data = command_model.command(command_id).data
        data.label = label
        command_model.update(command_id, data)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.model.state_changed.disconnect(self._state_changed)
        self.model.mode_entered.disconnect(self._mode_entered)


__all__ = ["NativeGameModeController"]
