from termin.editor_tcgui.game_mode_ui_controller import GameModeUiController


class _Button:
    def __init__(self) -> None:
        self.text = ""
        self.background_color = None
        self.visible = False


class _StatusBar:
    def __init__(self) -> None:
        self.text = ""


class _GameModeModel:
    def __init__(self) -> None:
        self.is_game_paused = False
        self.toggle_count = 0

    def toggle_pause(self) -> None:
        self.toggle_count += 1
        self.is_game_paused = not self.is_game_paused


def _make_controller(
    play_button: _Button,
    pause_button: _Button,
    status_bar: _StatusBar,
    play_updates: list[bool],
    title_updates: list[bool],
    viewport_updates: list[bool],
) -> GameModeUiController:
    controller = GameModeUiController(
        update_play_action=play_updates.append,
        update_window_title=lambda: title_updates.append(True),
        request_viewport_update=lambda: viewport_updates.append(True),
    )
    controller.set_widgets(
        play_button=play_button,
        pause_button=pause_button,
        status_bar=status_bar,
    )
    return controller


def test_game_mode_ui_controller_updates_playing_state() -> None:
    play_button = _Button()
    pause_button = _Button()
    status_bar = _StatusBar()
    play_updates: list[bool] = []
    title_updates: list[bool] = []
    viewport_updates: list[bool] = []
    controller = _make_controller(
        play_button,
        pause_button,
        status_bar,
        play_updates,
        title_updates,
        viewport_updates,
    )

    controller.update_mode(True)

    assert play_button.text == "Stop"
    assert pause_button.visible is True
    assert status_bar.text == "Game mode"
    assert play_updates == [True]
    assert title_updates == [True]
    assert viewport_updates == []


def test_game_mode_ui_controller_toggles_pause_state() -> None:
    play_button = _Button()
    pause_button = _Button()
    status_bar = _StatusBar()
    viewport_updates: list[bool] = []
    controller = _make_controller(
        play_button,
        pause_button,
        status_bar,
        [],
        [],
        viewport_updates,
    )
    model = _GameModeModel()

    controller.toggle_pause(model)

    assert model.toggle_count == 1
    assert model.is_game_paused is True
    assert pause_button.text == "Resume"
    assert viewport_updates == [True]
