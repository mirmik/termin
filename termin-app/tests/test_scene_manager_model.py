import pytest

from termin.editor_core.scene_manager_model import SceneManagerController, SceneMode
from termin.engine import SceneManager


def test_scene_manager_controller_snapshots_modes_copy_and_unload():
    manager = SceneManager()
    scene = manager.create_scene("Editor", [])
    manager.set_mode("Editor", SceneMode.STOP)
    changed = []
    controller = SceneManagerController(manager, on_changed=lambda: changed.append(True))
    try:
        value = controller.refresh()
        assert value.scenes[0].handle == f"{scene.scene_handle().index}:{scene.scene_handle().generation}"
        assert value.selected_name == "Editor"
        copied = controller.duplicate_selected("Copy")
        assert copied.selected_name == "Copy"
        controller.set_selected_mode(SceneMode.PLAY)
        assert controller.refresh().playing_count == 1
        controller.unload_selected()
        assert not manager.has_scene("Copy")
        assert len(changed) == 3
    finally:
        manager.close_all_scenes()


def test_scene_manager_controller_requires_detach_before_unloading_edited_scene():
    manager = SceneManager()
    scene = manager.create_scene("Editor", [])
    attachment = type("Attachment", (), {"scene": scene})()
    controller = SceneManagerController(manager, get_editor_attachment=lambda: attachment)
    try:
        controller.refresh()
        with pytest.raises(RuntimeError, match="editor-attached"):
            controller.unload_selected()
    finally:
        manager.close_all_scenes()


def test_scene_manager_controller_checks_callback_results():
    manager = SceneManager()
    manager.create_scene("Editor", [])
    controller = SceneManagerController(manager, on_render_attach=lambda _name: False)
    try:
        controller.refresh()
        with pytest.raises(RuntimeError, match="render attach failed"):
            controller.render_attach_selected()
    finally:
        manager.close_all_scenes()
