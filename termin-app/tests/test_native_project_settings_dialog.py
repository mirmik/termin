import gc
import weakref

from termin.editor_core.project_settings_model import ProjectSettingsController
from termin.editor_native.dialog_service import NativeDialogService
from termin.editor_native.project_settings_dialog import build_native_project_settings_dialog
from termin.gui_native import Document, Rect
from termin.project.settings import ProjectSettingsManager


def test_native_project_settings_dialog_saves_reopens_and_releases(tmp_path):
    manager = ProjectSettingsManager()
    manager.set_project_path(tmp_path)
    resources = []
    renders = []
    document = Document()
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
    dialog.build_output.text = "out"
    dialog.ignored_paths.text = "cache\ngenerated/assets"
    dialog.player_width.value = 1600
    dialog.player_height.value = 900
    dialog.player_fullscreen.checked = False
    assert dialog.dialog.activate("close")

    saved = ProjectSettingsController(manager).load()
    assert saved.build_output_dir == "out"
    assert saved.ignored_resource_paths == ("cache", "generated/assets")
    assert saved.player_width == 1600
    assert saved.player_height == 900
    assert resources == [True]
    assert dialog.show()

    dialog.close()
    assert not document.is_alive(dialog.dialog.handle)
    reference = weakref.ref(dialog)
    del dialog
    gc.collect()
    assert reference() is None
    assert renders
