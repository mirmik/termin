from termin.editor_core.game_mode_session_connectors import (
    EditorGameModeConnector,
)
from termin.engine import SceneKey, SceneRole


class _SceneManager:
    def __init__(self, scene) -> None:
        self.scene = scene

    def get_scene(self, key):
        return self.scene if key == SceneKey("Scene", SceneRole.RUNTIME) else None


class _EditorSession:
    def __init__(self) -> None:
        self.calls = []

    def attach(self, scene, **options):
        self.calls.append(("attach", scene, options))
        return True

    def detach(self, **options):
        self.calls.append(("detach", options))
        return True


def test_game_mode_session_connectors_preserve_transition_options() -> None:
    scene = object()
    editor_session = _EditorSession()
    editor = EditorGameModeConnector(_SceneManager(scene), editor_session)
    assert editor.attach_editor_to_scene(
        SceneKey("Scene", SceneRole.RUNTIME),
        restore_state=False,
        transfer_camera_state=True,
        update_editor_scene_name=False,
    )
    assert editor.detach_editor_from_scene(
        save_state=True,
        clear_editor_scene_name=False,
    )
    assert editor_session.calls == [
        (
            "attach",
            scene,
            {"restore_state": False, "transfer_camera_state": True},
        ),
        ("detach", {"save_state": True}),
    ]
