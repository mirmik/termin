from termin.gui_native import tc_ui_document_create, tc_ui_document_destroy
import gc
import weakref

from termin.editor_core.scene_manager_model import SceneManagerController, SceneMode
from termin.editor_native.dialog_service import NativeDialogService
from termin.editor_native.metrics import EDITOR_UI_METRICS
from termin.editor_native.scene_manager_dialog import build_native_scene_manager_dialog
from termin.engine import SceneManager
from termin.gui_native import Rect


def test_native_scene_manager_selects_mutates_reopens_and_releases():
    manager = SceneManager()
    manager.create_scene("A", [])
    manager.create_scene("B", [])
    document = tc_ui_document_create()
    renders = []
    viewport = lambda: Rect(0.0, 0.0, 1000.0, 700.0)
    render = lambda: renders.append(True)
    service = NativeDialogService(document, viewport=viewport, request_render=render)
    controller = SceneManagerController(manager)
    dialog = build_native_scene_manager_dialog(
        document,
        controller,
        dialog_service=service,
        viewport=viewport,
        request_render=render,
    )
    try:
        assert dialog.show()
        root = dialog.dialog.widget.children[0]
        assert root.children[0].bounds.height == EDITOR_UI_METRICS.field_row
        assert root.children[-1].bounds.height == EDITOR_UI_METRICS.action_row
        dialog.select(1)
        assert dialog.snapshot.selected_name == "B"
        dialog.perform(lambda: controller.set_selected_mode(SceneMode.PLAY))
        assert manager.get_mode("B") == SceneMode.PLAY
        assert dialog.dialog.activate("close")
        assert dialog.show()
        dialog.close()
        assert not document.is_alive(dialog.dialog.handle)
        reference = weakref.ref(dialog)
        del dialog
        gc.collect()
        assert reference() is None
        assert renders
    finally:
        manager.close_all_scenes()
    tc_ui_document_destroy(document)
