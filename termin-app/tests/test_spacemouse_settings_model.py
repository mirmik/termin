import pytest

from termin.editor_core.spacemouse_controller import SpaceMouseController
from termin.editor_core.spacemouse_settings_model import (
    SpaceMouseSettingsController,
    SpaceMouseSettingsSnapshot,
)


def test_spacemouse_settings_controller_applies_and_validates():
    spacemouse = SpaceMouseController()
    changed = []
    controller = SpaceMouseSettingsController(spacemouse, on_changed=lambda: changed.append(True))
    initial = controller.load()
    value = SpaceMouseSettingsSnapshot(
        False, initial.horizon_lock, 0.00003, 0.00006, 0.003, 0.0002, 20,
        True, False, True, False, True, False,
    )

    saved = controller.apply(value)

    assert not spacemouse.fly_mode
    assert saved.deadzone == 20
    assert saved.invert_x
    assert changed == [True]
    with pytest.raises(ValueError):
        controller.apply(SpaceMouseSettingsSnapshot(
            True, True, 1.0, 0.00005, 0.002, 0.0001, 15,
            False, False, False, False, False, False,
        ))
