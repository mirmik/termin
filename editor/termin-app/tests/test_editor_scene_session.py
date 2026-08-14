import pytest

from termin.editor_core.editor_scene_session import EditorSceneSession


class _Scene:
    def __init__(self, index):
        self._handle = type("Handle", (), {"index": index, "generation": 1})()

    def scene_handle(self):
        return self._handle


class _Attachment:
    def __init__(self, scene):
        self.scene = scene
        self.fail_for = None

    def attach(self, scene, *, restore_state, transfer_camera_state):
        if scene is self.fail_for:
            raise RuntimeError("attach failed")
        self.scene = scene

    def detach(self, *, save_state):
        self.scene = None


class _Model:
    def __init__(self):
        self.scene = None

    def set_scene(self, scene, **_kwargs):
        self.scene = scene


def _session(attachment, events):
    models = [_Model() for _ in range(5)]
    session = EditorSceneSession(
        attachment,
        scene_hierarchy=models[0],
        entity_inspector=models[1],
        scene_properties=models[2],
        scene_names=models[3],
        shadow_settings=models[4],
        clear_selection=lambda: events.append("clear"),
        before_switch=lambda: events.append("before"),
        on_switched=lambda scene: events.append(scene),
    )
    return session, models


def test_editor_scene_session_rebinds_every_scene_owner_and_detaches():
    first = _Scene(1)
    second = _Scene(2)
    events = []
    session, models = _session(_Attachment(first), events)

    assert session.attach(second)
    assert all(model.scene is second for model in models)
    assert events == ["before", "clear", second]
    assert session.detach()
    assert models[0].scene is None
    assert models[1].scene is None
    assert all(model.scene is None for model in models)
    assert session.scene is None


def test_editor_scene_session_rolls_back_attachment_and_models():
    first = _Scene(1)
    second = _Scene(2)
    attachment = _Attachment(first)
    attachment.fail_for = second
    session, models = _session(attachment, [])

    with pytest.raises(RuntimeError, match="attach failed"):
        session.attach(second)

    assert attachment.scene is first
    assert all(model.scene is first for model in models)
