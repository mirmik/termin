import gc
import weakref

from termin.editor_core.spacemouse_controller import SpaceMouseController
from termin.editor_core.spacemouse_settings_model import SpaceMouseSettingsController
from termin.editor_native.spacemouse_settings_dialog import (
    build_native_spacemouse_settings_dialog,
)
from termin.gui_native import Document, Rect


def test_native_spacemouse_settings_applies_reopens_and_releases():
    document = Document()
    renders = []
    spacemouse = SpaceMouseController()
    dialog = build_native_spacemouse_settings_dialog(
        document,
        SpaceMouseSettingsController(spacemouse),
        viewport=lambda: Rect(0.0, 0.0, 800.0, 600.0),
        request_render=lambda: renders.append(True),
    )

    assert dialog.show()
    dialog.mode.selected_index = 0
    dialog.deadzone.value = 25
    dialog.inversions[0].checked = True
    dialog.apply_controls()
    assert not spacemouse.fly_mode
    assert spacemouse.deadzone == 25
    assert spacemouse.invert_x
    assert dialog.dialog.activate("close")
    assert dialog.show()

    dialog.close()
    assert not document.is_alive(dialog.dialog.handle)
    reference = weakref.ref(dialog)
    del dialog
    gc.collect()
    assert reference() is None
    assert renders
