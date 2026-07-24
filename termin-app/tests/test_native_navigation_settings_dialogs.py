from termin.gui_native import tc_ui_document_create, tc_ui_document_destroy
import gc
import weakref

from termin.editor_core.navigation_settings_model import NavigationSettingsController
from termin.editor_native.dialog_service import NativeDialogService
from termin.editor_native.metrics import EDITOR_UI_METRICS
from termin.editor_native.navigation_settings_dialogs import (
    build_native_agent_types_dialog,
    build_native_navmesh_areas_dialog,
)
from termin.gui_native import Rect

from test_navigation_settings_model import _Manager


def _host():
    document = tc_ui_document_create()
    renders = []
    viewport = lambda: Rect(0.0, 0.0, 1000.0, 700.0)
    render = lambda: renders.append(True)
    service = NativeDialogService(document, viewport=viewport, request_render=render)
    return document, renders, viewport, render, service
    tc_ui_document_destroy(document)


def test_native_agent_types_dialog_stages_cancel_saves_and_releases():
    document, renders, viewport, render, service = _host()
    manager = _Manager()
    dialog = build_native_agent_types_dialog(
        document, NavigationSettingsController(manager), dialog_service=service,
        viewport=viewport, request_render=render,
    )
    assert dialog.show()
    root = dialog.dialog.widget.children[0]
    assert root.children[0].bounds.height == EDITOR_UI_METRICS.field_row
    assert root.children[0].children[0].bounds.width == EDITOR_UI_METRICS.form_label
    assert root.children[1].bounds.height == EDITOR_UI_METRICS.field_row
    dialog.add()
    assert dialog.dialog.activate("cancel")
    assert len(manager.settings.agent_types) == 1
    assert dialog.show()
    dialog.add()
    assert dialog.dialog.activate("ok")
    assert len(manager.settings.agent_types) == 2
    dialog.close()
    reference = weakref.ref(dialog)
    del dialog
    gc.collect()
    assert reference() is None
    assert renders


def test_native_navmesh_areas_dialog_saves_and_reopens():
    document, _renders, viewport, render, service = _host()
    manager = _Manager()
    dialog = build_native_navmesh_areas_dialog(
        document, NavigationSettingsController(manager), dialog_service=service,
        viewport=viewport, request_render=render,
    )
    assert dialog.show()
    root = dialog.dialog.widget.children[0]
    assert root.children[0].bounds.height == EDITOR_UI_METRICS.section_row
    names = dialog.names.text.split("\n")
    names[7] = "Jump"
    dialog.names.text = "\n".join(names)
    assert dialog.dialog.activate("ok")
    assert manager.settings.navmesh_area_names[7] == "Jump"
    assert dialog.show()
    dialog.close()
