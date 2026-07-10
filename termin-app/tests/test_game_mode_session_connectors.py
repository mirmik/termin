from termin.editor_core.game_mode_session_connectors import (
    EditorGameModeConnector,
    RenderGameModeConnector,
)


class _SceneManager:
    def __init__(self, scene) -> None:
        self.scene = scene

    def get_scene(self, name):
        return self.scene if name == "Scene" else None


class _EditorSession:
    def __init__(self) -> None:
        self.calls = []

    def attach(self, scene, **options):
        self.calls.append(("attach", scene, options))
        return True

    def detach(self, **options):
        self.calls.append(("detach", options))
        return True


class _RenderSession:
    def __init__(self) -> None:
        self.calls = []

    def sync_scene_render_state(self, name):
        self.calls.append(("sync", name))

    def attach(self, name):
        self.calls.append(("attach", name))
        return True

    def detach(self, name, **options):
        self.calls.append(("detach", name, options))
        return True


def test_game_mode_session_connectors_preserve_transition_options() -> None:
    scene = object()
    editor_session = _EditorSession()
    editor = EditorGameModeConnector(_SceneManager(scene), editor_session)
    assert editor.attach_editor_to_scene(
        "Scene",
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

    render_session = _RenderSession()
    render = RenderGameModeConnector(render_session)
    render.sync_scene_render_state("Scene")
    assert render.attach_scene_to_render("Scene")
    assert render.detach_scene_from_render("Scene", save_state=False)
    assert render_session.calls == [
        ("sync", "Scene"),
        ("attach", "Scene"),
        ("detach", "Scene", {"save_state": False}),
    ]
