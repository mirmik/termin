from termin.editor_core import scene_file_controller as scene_file_controller_module
from termin.editor_core.scene_file_controller import SceneFileController
from termin.project.settings import ProjectSettingsManager
from termin.engine import SceneKey, SceneRole


class _SceneManager:
    def __init__(
        self,
        calls: list[object],
        scene_path: str | None = None,
    ) -> None:
        self.calls = calls
        self.scene_path = scene_path

    def get_scene_path(self, _key: SceneKey) -> str | None:
        return self.scene_path

    def save_scene(self, key: SceneKey, path: str, editor_data) -> None:
        self.calls.append(("save", key, path, editor_data))


class _ProjectSettings:
    def __init__(self, calls: list[object]) -> None:
        self.calls = calls

    def set_last_scene(self, path: str) -> None:
        self.calls.append(("last-scene", path))


def _controller(
    monkeypatch,
    calls,
    prepare_scene_for_save,
    *,
    scene_manager=None,
    dialog_service=None,
) -> SceneFileController:
    monkeypatch.setattr(
        scene_file_controller_module.log,
        "error",
        lambda message: calls.append(("log-error", message)),
    )
    return SceneFileController(
        scene_manager=scene_manager or _SceneManager(calls),
        get_dialog_service=lambda: dialog_service,
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
        monkeypatch,
        calls,
        lambda name: calls.append(("prepare", name)),
    )
    path = str(tmp_path / "scene4.scene")

    controller.save_scene_to_file(path)

    assert calls[:2] == [
        ("prepare", "scene4"),
        ("save", SceneKey("scene4", SceneRole.AUTHORING), path, None),
    ]


def test_save_aborts_when_render_state_synchronization_fails(
    monkeypatch, tmp_path
) -> None:
    calls: list[object] = []
    path = str(tmp_path / "scene4.scene")
    monkeypatch.setattr(
        ProjectSettingsManager,
        "instance",
        lambda: _ProjectSettings(calls),
    )
    controller = _controller(
        monkeypatch,
        calls,
        lambda _name: False,
        scene_manager=_SceneManager(calls, path),
    )
    completions: list[bool] = []

    controller.save_scene(completions.append)

    assert completions == [False]
    assert not any(call[0] == "save" for call in calls)
    assert calls == [
        (
            "log-error",
            "Failed to save scene: "
            "Failed to synchronize scene state before saving 'scene4'",
        )
    ]


def test_save_existing_scene_reports_success_after_persistence(
    monkeypatch, tmp_path
) -> None:
    calls: list[object] = []
    path = str(tmp_path / "scene4.scene")
    monkeypatch.setattr(
        ProjectSettingsManager,
        "instance",
        lambda: _ProjectSettings(calls),
    )
    controller = _controller(
        monkeypatch,
        calls,
        lambda _name: True,
        scene_manager=_SceneManager(calls, path),
    )
    completions: list[bool] = []

    controller.save_scene(completions.append)

    assert completions == [True]
    assert ("save", SceneKey("scene4", SceneRole.AUTHORING), path, None) in calls


class _SaveDialog:
    def __init__(self) -> None:
        self.on_result = None

    def show_save_file(
        self,
        *,
        title,
        directory,
        filter_string,
        on_result,
        default_name="",
    ) -> None:
        self.on_result = on_result


def test_save_as_completes_only_after_dialog_result(monkeypatch, tmp_path) -> None:
    calls: list[object] = []
    dialogs = _SaveDialog()
    monkeypatch.setattr(
        ProjectSettingsManager,
        "instance",
        lambda: _ProjectSettings(calls),
    )
    controller = _controller(
        monkeypatch,
        calls,
        lambda _name: True,
        dialog_service=dialogs,
    )
    completions: list[bool] = []

    controller.save_scene(completions.append)

    assert completions == []
    assert dialogs.on_result is not None
    path = str(tmp_path / "saved.scene")
    dialogs.on_result(path)
    assert completions == [True]
    assert ("save", SceneKey("scene4", SceneRole.AUTHORING), path, None) in calls


def test_save_as_cancellation_reports_failure(monkeypatch) -> None:
    calls: list[object] = []
    dialogs = _SaveDialog()
    controller = _controller(
        monkeypatch,
        calls,
        lambda _name: True,
        dialog_service=dialogs,
    )
    completions: list[bool] = []

    controller.save_scene(completions.append)

    assert dialogs.on_result is not None
    dialogs.on_result(None)
    assert completions == [False]
    assert not any(call[0] == "save" for call in calls)
