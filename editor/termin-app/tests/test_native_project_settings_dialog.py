import gc
import weakref

import pytest

from termin.editor_core.project_settings_model import ProjectSettingsController
from termin.editor_native.dialog_service import NativeDialogService
from termin.editor_native.metrics import EDITOR_UI_METRICS
from termin.editor_native.project_settings_dialog import build_native_project_settings_dialog
from termin.gui_native import Rect, tc_ui_document_create, tc_ui_document_destroy
from termin.project.settings import ProjectSettingsManager


def test_native_project_settings_dialog_saves_reopens_and_releases(tmp_path):
    manager = ProjectSettingsManager()
    manager.set_project_path(tmp_path)
    resources = []
    renders = []
    document = tc_ui_document_create()
    viewport = lambda: Rect(0.0, 0.0, 900.0, 650.0)
    render = lambda: renders.append(True)
    service = NativeDialogService(document, viewport=viewport, request_render=render)
    dialog = build_native_project_settings_dialog(
        document,
        ProjectSettingsController(
            manager,
            on_resource_settings_changed=lambda: resources.append(True),
        ),
        dialog_service=service,
        viewport=viewport,
        request_render=render,
    )

    assert dialog.show()
    root = dialog.dialog.widget.children[0]
    first_row = root.children[0]
    assert first_row.bounds.height == EDITOR_UI_METRICS.field_row
    assert first_row.children[0].bounds.width == EDITOR_UI_METRICS.form_label
    assert root.children[-1].bounds.height == EDITOR_UI_METRICS.status_row
    dialog.build_output.text = "out"
    dialog.application_id.text = "com.example.native"
    dialog.application_label.text = "Native Game"
    dialog.version_code.value = 9
    dialog.version_name.text = "3.0"
    dialog.world_controller_module.text = " avalon.game "
    dialog.world_controller_type.text = " avalon.GameDirector "
    dialog.ignored_paths.text = "cache\ngenerated/assets"
    dialog.player_width.value = 1600
    dialog.player_height.value = 900
    dialog.player_fullscreen.checked = False
    dialog.player_vsync.checked = False
    assert dialog.dialog.activate("close")

    saved = ProjectSettingsController(manager).load()
    assert saved.build_output_dir == "out"
    assert saved.application_id == "com.example.native"
    assert saved.application_label == "Native Game"
    assert saved.version_code == 9
    assert saved.version_name == "3.0"
    assert saved.world_controller is not None
    assert saved.world_controller.module == "avalon.game"
    assert saved.world_controller.type_name == "avalon.GameDirector"
    assert saved.ignored_resource_paths == ("cache", "generated/assets")
    assert saved.player_width == 1600
    assert saved.player_height == 900
    assert not saved.player_vsync
    assert resources == [True]
    assert dialog.show()

    dialog.world_controller_module.text = ""
    dialog.world_controller_type.text = ""
    dialog.save()
    assert ProjectSettingsController(manager).load().world_controller is None

    dialog.close()
    assert not document.is_alive(dialog.dialog.handle)
    reference = weakref.ref(dialog)
    del dialog
    gc.collect()
    assert reference() is None
    assert renders
    tc_ui_document_destroy(document)


def test_native_project_settings_dialog_rejects_partial_world_controller(tmp_path):
    manager = ProjectSettingsManager()
    manager.set_project_path(tmp_path)
    document = tc_ui_document_create()
    viewport = lambda: Rect(0.0, 0.0, 900.0, 650.0)
    service = NativeDialogService(
        document,
        viewport=viewport,
        request_render=lambda: None,
    )
    dialog = build_native_project_settings_dialog(
        document,
        ProjectSettingsController(manager),
        dialog_service=service,
        viewport=viewport,
        request_render=lambda: None,
    )
    dialog.apply_snapshot(ProjectSettingsController(manager).load())
    dialog.world_controller_module.text = "avalon.game"

    with pytest.raises(ValueError, match="world_controller.type"):
        dialog.save()

    assert ProjectSettingsController(manager).load().world_controller is None
    dialog.close()
    tc_ui_document_destroy(document)
