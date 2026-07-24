from termin.gui_native import tc_ui_document_create, tc_ui_document_destroy
import gc
import weakref

from termin.editor_core.spacemouse_controller import SpaceMouseController
from termin.editor_core.spacemouse_settings_model import SpaceMouseSettingsController
from termin.editor_native.spacemouse_settings_dialog import (
    build_native_spacemouse_settings_dialog,
)
from termin.editor_native.metrics import EDITOR_UI_METRICS
from termin.gui_native import Rect


def test_native_spacemouse_settings_applies_reopens_and_releases():
    document = tc_ui_document_create()
    renders = []
    spacemouse = SpaceMouseController()
    dialog = build_native_spacemouse_settings_dialog(
        document,
        SpaceMouseSettingsController(spacemouse),
        viewport=lambda: Rect(0.0, 0.0, 800.0, 600.0),
        request_render=lambda: renders.append(True),
    )

    assert dialog.show()
    root = dialog.dialog.widget.children[0]
    mode_row = root.children[0]
    horizon_row = root.children[1]
    assert mode_row.bounds.height == EDITOR_UI_METRICS.field_row
    assert horizon_row.bounds.height == EDITOR_UI_METRICS.compact_row
    assert mode_row.children[0].bounds.width == EDITOR_UI_METRICS.form_label
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
    tc_ui_document_destroy(document)
