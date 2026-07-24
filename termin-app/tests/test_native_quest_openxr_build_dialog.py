from termin.gui_native import tc_ui_document_create, tc_ui_document_destroy
from types import SimpleNamespace

from termin.editor_native.quest_openxr_build_dialog import (
    build_native_quest_openxr_build_dialog,
)
from termin.editor_native.metrics import EDITOR_UI_METRICS
from termin.gui_native import Rect


def test_native_quest_openxr_dialog_projects_entry_and_releases(tmp_path) -> None:
    document = tc_ui_document_create()
    renders = []
    dialog = build_native_quest_openxr_build_dialog(
        document,
        viewport=lambda: Rect(0.0, 0.0, 1280.0, 720.0),
        request_render=lambda: renders.append(True),
    )
    entry = SimpleNamespace(
        project_root=tmp_path / "Project",
        scene_rel_path=tmp_path / "Project" / "Scenes" / "Main.scene",
        output_dir=tmp_path / "Project" / "dist",
    )

    assert dialog.show_entry(entry)
    assert dialog.dialog.open
    root = dialog.dialog.widget.children[0]
    assert all(
        child.bounds.height == EDITOR_UI_METRICS.status_row
        for child in root.children[:3]
    )
    assert root.children[3].bounds.height == EDITOR_UI_METRICS.action_row
    assert dialog.project_label.text == "Project: Project"
    assert "Scenes/Main.scene" in dialog.scene_label.text
    assert dialog.status.text == "Idle"
    assert "Connect and wake" in dialog.log_view.text
    assert renders

    handle = dialog.dialog.handle
    dialog.close()
    assert not document.is_alive(handle)
    tc_ui_document_destroy(document)
