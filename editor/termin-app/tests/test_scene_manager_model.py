import pytest

from termin.editor_core.scene_manager_model import SceneManagerController, SceneMode
from termin.engine import SceneKey, SceneManager, SceneRole


def _authoring_key(identity: str) -> SceneKey:
    return SceneKey(identity, SceneRole.AUTHORING)


def test_scene_manager_controller_snapshots_modes_copy_and_unload():
    manager = SceneManager()
    scene = manager.create_scene(_authoring_key("Editor"), [])
    manager.set_mode(_authoring_key("Editor"), SceneMode.STOP)
    changed = []
    controller = SceneManagerController(manager, on_changed=lambda: changed.append(True))
    try:
        value = controller.refresh()
        assert value.scenes[0].handle == f"{scene.scene_handle().index}:{scene.scene_handle().generation}"
        assert value.selected_key == _authoring_key("Editor")
        copied = controller.duplicate_selected("Copy")
        assert copied.selected_key == _authoring_key("Copy")
        controller.set_selected_mode(SceneMode.PLAY)
        assert controller.refresh().playing_count == 1
        controller.unload_selected()
        assert not manager.has_scene(_authoring_key("Copy"))
        assert len(changed) == 3
    finally:
        manager.close_all_scenes()


def test_scene_manager_controller_requires_detach_before_unloading_edited_scene():
    manager = SceneManager()
    scene = manager.create_scene(_authoring_key("Editor"), [])
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
    manager.create_scene(_authoring_key("Editor"), [])
    controller = SceneManagerController(manager, on_render_attach=lambda _name: False)
    try:
        controller.refresh()
        with pytest.raises(RuntimeError, match="render attach failed"):
            controller.render_attach_selected()
    finally:
        manager.close_all_scenes()


def test_scene_manager_controller_editor_attachment_actions_are_idempotent():
    manager = SceneManager()
    scene = manager.create_scene(_authoring_key("Editor"), [])
    attachment = type("Attachment", (), {"scene": scene})()
    calls = []
    controller = SceneManagerController(
        manager,
        get_editor_attachment=lambda: attachment,
        on_editor_attach=lambda name: calls.append(("attach", name)),
        on_editor_detach=lambda: calls.append(("detach", None)),
    )
    try:
        controller.refresh()
        controller.editor_attach_selected()
        assert calls == []
        controller.editor_detach()
        assert calls == [("detach", None)]
    finally:
        manager.close_all_scenes()


def test_scene_manager_controller_selects_same_identity_by_exact_role():
    manager = SceneManager()
    authoring_key = _authoring_key("Shared")
    runtime_key = SceneKey("Shared", SceneRole.RUNTIME)
    manager.create_scene(authoring_key, [])
    manager.create_scene(runtime_key, [])
    controller = SceneManagerController(manager)
    try:
        snapshot = controller.refresh()
        assert {item.key for item in snapshot.scenes} == {authoring_key, runtime_key}

        selected = controller.select(runtime_key)
        assert selected.selected_key == runtime_key
        controller.set_selected_mode(SceneMode.PLAY)
        assert manager.get_mode(runtime_key) == SceneMode.PLAY
        assert manager.get_mode(authoring_key) != SceneMode.PLAY
    finally:
        manager.close_all_scenes()
