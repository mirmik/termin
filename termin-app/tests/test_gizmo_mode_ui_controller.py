import pytest

from termin.editor_tcgui.gizmo_mode_ui_controller import GizmoModeUiController


class _Button:
    def __init__(self) -> None:
        self.text = ""
        self.background_color = None


class _TransformGizmo:
    def __init__(self) -> None:
        self.modes: list[str] = []

    def set_orientation_mode(self, mode: str) -> None:
        self.modes.append(mode)


class _InteractionSystem:
    def __init__(self) -> None:
        self.transform_gizmo = _TransformGizmo()


def test_gizmo_mode_controller_initializes_local_mode() -> None:
    interaction_system = _InteractionSystem()
    button = _Button()
    viewport_updates: list[bool] = []
    controller = GizmoModeUiController(
        get_interaction_system=lambda: interaction_system,
        request_viewport_update=lambda: viewport_updates.append(True),
    )

    controller.set_widgets(orientation_button=button)

    assert controller.orientation_mode == "local"
    assert button.text == "Local"
    assert interaction_system.transform_gizmo.modes == ["local"]
    assert viewport_updates == []


def test_gizmo_mode_controller_toggles_world_and_local() -> None:
    interaction_system = _InteractionSystem()
    button = _Button()
    viewport_updates: list[bool] = []
    controller = GizmoModeUiController(
        get_interaction_system=lambda: interaction_system,
        request_viewport_update=lambda: viewport_updates.append(True),
    )
    controller.set_widgets(orientation_button=button)

    controller.toggle_orientation_mode()
    controller.toggle_orientation_mode()

    assert controller.orientation_mode == "local"
    assert button.text == "Local"
    assert interaction_system.transform_gizmo.modes == ["local", "world", "local"]
    assert viewport_updates == [True, True]


def test_gizmo_mode_controller_rejects_invalid_mode() -> None:
    controller = GizmoModeUiController(
        get_interaction_system=lambda: None,
        request_viewport_update=lambda: None,
    )

    with pytest.raises(ValueError):
        controller.set_orientation_mode("screen")  # type: ignore[arg-type]

