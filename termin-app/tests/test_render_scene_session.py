from types import SimpleNamespace

import pytest

from termin.editor_core.render_scene_session import RenderSceneSession


class _SceneManager:
    def __init__(self, scene):
        self.scene = scene

    def get_scene(self, name):
        return self.scene if name == "Scene" else None


class _RenderingModel:
    def __init__(self, display, viewport):
        self.manager = SimpleNamespace(get_display_for_viewport=lambda _viewport: display)
        self.viewport = viewport
        self.detached = []
        self.synced = []

    def attach_scene(self, _scene):
        return [self.viewport]

    def detach_scene(self, scene):
        self.detached.append(scene)
        return {2}

    def sync_viewport_configs_to_scene(self, scene):
        self.synced.append(("viewports", scene))

    def sync_render_target_configs_to_scene(self, scene):
        self.synced.append(("targets", scene))


class _Workspace:
    def __init__(self, display, *, fail=False):
        self.editor = SimpleNamespace(tc_display_ptr=1, viewports=[])
        self.display = display
        self.displays = (self.editor, display)
        self.fail = fail
        self.configured = []
        self.removed = []

    def is_editor_display(self, display):
        return display is self.editor

    def configure_viewport_input(self, display, viewport):
        if self.fail:
            raise RuntimeError("input failed")
        self.configured.append((display, viewport))

    def remove_display(self, display):
        self.removed.append(display)


def _session(*, fail=False):
    scene = object()
    viewport = object()
    display = SimpleNamespace(tc_display_ptr=2, viewports=[])
    model = _RenderingModel(display, viewport)
    workspace = _Workspace(display, fail=fail)
    events = []
    session = RenderSceneSession(
        _SceneManager(scene),
        model,
        workspace,
        sync_viewports=lambda: events.append("sync"),
        request_render=lambda: events.append("render"),
    )
    return session, scene, viewport, display, model, workspace, events


def test_render_scene_session_attaches_configures_and_detaches():
    session, scene, viewport, display, model, workspace, events = _session()
    assert session.attach("Scene")
    assert workspace.configured == [(display, viewport)]
    assert events == ["sync", "render"]

    assert session.detach("Scene")
    assert model.synced == [("viewports", scene), ("targets", scene)]
    assert model.detached == [scene]
    assert workspace.removed == [display]
    assert events == ["sync", "render", "sync", "render"]


def test_render_scene_session_rolls_back_failed_input_setup():
    session, scene, _viewport, display, model, workspace, _events = _session(fail=True)
    with pytest.raises(RuntimeError, match="input failed"):
        session.attach("Scene")
    assert model.detached == [scene]
    assert workspace.removed == [display]


def test_render_scene_session_rejects_unknown_scene():
    session, *_rest = _session()
    with pytest.raises(ValueError, match="does not exist"):
        session.attach("Missing")
