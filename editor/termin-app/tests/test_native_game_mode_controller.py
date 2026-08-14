from termin.gui_native import tc_ui_document_create, tc_ui_document_destroy
from termin.editor_core.signal import Signal
from termin.editor_native.game_mode_controller import NativeGameModeController
from termin.editor_native.shell import build_native_editor_shell
from tcbase import Key


class _GameModeModel:
    def __init__(self) -> None:
        self.is_game_mode = False
        self.state_changed = Signal()
        self.mode_entered = Signal()

    def toggle_game_mode(self) -> None:
        self.is_game_mode = not self.is_game_mode
        self.state_changed.emit(self)
        self.mode_entered.emit(self.is_game_mode, object(), ["expanded"])


class _SceneHierarchy:
    def __init__(self) -> None:
        self.expanded = []

    def set_expanded_entity_uuids(self, uuids) -> None:
        self.expanded = list(uuids)


def test_native_game_mode_controller_projects_f5_play_and_stop() -> None:
    document = tc_ui_document_create()
    shell = build_native_editor_shell(document)
    model = _GameModeModel()
    hierarchy = _SceneHierarchy()
    renders = []
    controller = NativeGameModeController(
        model,
        menu_bar=shell.menu_bar,
        game_menu_model=shell.game_menu_model,
        game_play_command=shell.game_play_command,
        tool_bar=shell.tool_bar,
        toolbar_model=shell.toolbar_model,
        toolbar_play_command=shell.toolbar_play_command,
        scene_hierarchy=hierarchy,
        status_bar=shell.status_bar,
        request_render=lambda: renders.append(True),
    )

    assert shell.menu_bar.dispatch_shortcut(Key.F5.value, 0)
    assert model.is_game_mode
    assert shell.game_menu_model.command(shell.game_play_command).data.label == "Stop"
    assert shell.toolbar_model.command(shell.toolbar_play_command).data.label == "Stop"
    assert shell.status_bar.text == "Game mode"
    assert hierarchy.expanded == ["expanded"]

    assert shell.menu_bar.dispatch_shortcut(Key.F5.value, 0)
    assert not model.is_game_mode
    assert shell.game_menu_model.command(shell.game_play_command).data.label == "Play"
    assert shell.status_bar.text == "Editor mode"
    assert renders

    controller.close()
    tc_ui_document_destroy(document)


def test_native_game_mode_controller_can_disable_all_play_entry_points() -> None:
    document = tc_ui_document_create()
    shell = build_native_editor_shell(document)
    model = _GameModeModel()
    controller = NativeGameModeController(
        model,
        menu_bar=shell.menu_bar,
        game_menu_model=shell.game_menu_model,
        game_play_command=shell.game_play_command,
        tool_bar=shell.tool_bar,
        toolbar_model=shell.toolbar_model,
        toolbar_play_command=shell.toolbar_play_command,
        scene_hierarchy=_SceneHierarchy(),
        status_bar=shell.status_bar,
        request_render=lambda: None,
    )

    controller.set_available(False)

    assert not shell.game_menu_model.command(shell.game_play_command).data.enabled
    assert not shell.toolbar_model.command(shell.toolbar_play_command).data.enabled
    assert not shell.menu_bar.dispatch_shortcut(Key.F5.value, 0)
    assert not model.is_game_mode

    controller.set_available(True)
    assert shell.menu_bar.dispatch_shortcut(Key.F5.value, 0)
    assert model.is_game_mode

    controller.close()
    tc_ui_document_destroy(document)
