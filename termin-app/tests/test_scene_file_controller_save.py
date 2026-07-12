from termin.editor_core.scene_file_controller import SceneFileController
from termin.project.settings import ProjectSettingsManager


class _SceneManager:
    def __init__(self, calls: list[object]) -> None:
        self.calls = calls

    def save_scene(self, name: str, path: str, editor_data) -> None:
        self.calls.append(("save", name, path, editor_data))


class _ProjectSettings:
    def __init__(self, calls: list[object]) -> None:
        self.calls = calls

    def set_last_scene(self, path: str) -> None:
        self.calls.append(("last-scene", path))


def _controller(calls, prepare_scene_for_save) -> SceneFileController:
    return SceneFileController(
        scene_manager=_SceneManager(calls),
        get_dialog_service=lambda: None,
        get_editor_scene_name=lambda: "scene4",
        set_editor_scene_name=lambda _name: None,
        get_scene=lambda: None,
        get_project_path=lambda: None,
        get_editor_state_io=lambda: None,
        prepare_scene_for_save=prepare_scene_for_save,
        has_editor_attachment=lambda: False,
        detach_editor_from_scene=lambda **_options: True,
        detach_scene_from_render=lambda _name, **_options: True,
        attach_editor_to_scene=lambda _name, **_options: True,
        attach_scene_to_render=lambda _name: True,
        get_scene_tree_controller=lambda: None,
        get_inspector_controller=lambda: None,
        observe_scene_events=lambda _scene: None,
        on_rendering_changed=lambda: None,
        request_viewport_update=lambda: None,
        update_window_title=lambda: None,
        log_to_console=lambda message: calls.append(("log", message)),
    )


def test_save_synchronizes_live_render_state_before_scene_serialization(
    monkeypatch, tmp_path
) -> None:
    calls: list[object] = []
    monkeypatch.setattr(
        ProjectSettingsManager,
        "instance",
        lambda: _ProjectSettings(calls),
    )
    controller = _controller(
        calls,
        lambda name: calls.append(("prepare", name)),
    )
    path = str(tmp_path / "scene4.scene")

    controller.save_scene_to_file(path)

    assert calls[:2] == [
        ("prepare", "scene4"),
        ("save", "scene4", path, None),
    ]


def test_save_aborts_when_render_state_synchronization_fails(
    monkeypatch, tmp_path
) -> None:
    calls: list[object] = []
    monkeypatch.setattr(
        ProjectSettingsManager,
        "instance",
        lambda: _ProjectSettings(calls),
    )
    controller = _controller(calls, lambda _name: False)

    controller.save_scene_to_file(str(tmp_path / "scene4.scene"))

    assert not any(call[0] == "save" for call in calls)
    assert calls == [("log", "Error saving: Failed to synchronize scene state before saving 'scene4'")]
