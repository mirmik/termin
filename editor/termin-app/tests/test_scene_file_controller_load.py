import json

import pytest

from termin.editor_core import scene_file_controller as scene_file_controller_module
from termin.editor_core.scene_file_controller import SceneFileController
from termin.glb_adapters import scene_animation_repair
from termin.project.settings import ProjectSettingsManager
from termin.project_modules import runtime as project_modules_runtime
from termin.engine import SceneKey, SceneRole


def _authoring_key(identity: str) -> SceneKey:
    return SceneKey(identity, SceneRole.AUTHORING)


class _Scene:
    def __init__(self, calls: list[object], *, load_error: Exception | None = None) -> None:
        self.calls = calls
        self.load_error = load_error
        self.alive = True

    def is_alive(self) -> bool:
        return self.alive

    def load_from_data(self, data, *, context, update_settings: bool) -> None:
        self.calls.append(("deserialize", data, context, update_settings))
        if self.load_error is not None:
            raise self.load_error

    def notify_editor_start(self) -> None:
        self.calls.append("editor-start")

    def scene_handle(self):
        return self

    def destroy(self) -> None:
        self.calls.append(("destroy-stage", self))
        self.alive = False


class _SceneManager:
    def __init__(self, calls: list[object], old_scene: _Scene) -> None:
        self.calls = calls
        self.scenes = {_authoring_key("old"): old_scene}

    def has_scene(self, key: SceneKey) -> bool:
        return key in self.scenes

    def get_scene(self, key: SceneKey):
        return self.scenes.get(key)

    def close_scene(self, key: SceneKey) -> None:
        self.calls.append(("close", key))
        del self.scenes[key]

    def register_scene(self, key: SceneKey, scene: _Scene) -> bool:
        self.calls.append(("register", key, scene))
        self.scenes[key] = scene
        return True

    def set_scene_path(self, key: SceneKey, path: str) -> bool:
        self.calls.append(("path", key, path))
        return True

    def set_mode(self, key: SceneKey, mode) -> bool:
        self.calls.append(("mode", key, mode))
        return True


class _ProjectSettings:
    def __init__(self, calls: list[object]) -> None:
        self.calls = calls

    def set_last_scene(self, path: str) -> None:
        self.calls.append(("last-scene", path))


def _build_controller(
    monkeypatch,
    calls: list[object],
    *,
    staged_scene: _Scene,
    project_root,
) -> tuple[SceneFileController, _SceneManager, list[str | None]]:
    old_scene = _Scene(calls)
    manager = _SceneManager(calls, old_scene)
    active_name: list[str | None] = ["old"]

    monkeypatch.setattr(
        scene_file_controller_module,
        "create_scene_with_extensions",
        lambda name, uuid, extensions: (
            calls.append(("stage", name, uuid, extensions)) or staged_scene
        ),
    )

    monkeypatch.setattr(
        scene_file_controller_module,
        "default_scene_extensions",
        lambda: (11, 12),
    )
    monkeypatch.setattr(
        ProjectSettingsManager,
        "instance",
        lambda: _ProjectSettings(calls),
    )
    monkeypatch.setattr(
        project_modules_runtime,
        "upgrade_scene_unknown_components",
        lambda scene: calls.append(("upgrade", scene)),
    )
    monkeypatch.setattr(
        scene_file_controller_module.EditorStateIO,
        "extract_from_file",
        lambda path: calls.append(("extract-editor", path)) or {"camera": {}},
    )
    monkeypatch.setattr(
        scene_file_controller_module.log,
        "error",
        lambda message: calls.append(("log-error", message)),
    )

    controller = SceneFileController(
        scene_manager=manager,
        get_dialog_service=lambda: None,
        get_editor_scene_name=lambda: active_name[0],
        set_editor_scene_name=lambda name: (
            calls.append(("active-name", name)),
            active_name.__setitem__(0, name),
        ),
        get_scene=lambda: (
            None if active_name[0] is None else manager.get_scene(_authoring_key(active_name[0]))
        ),
        get_project_path=lambda: str(project_root),
        get_editor_state_io=lambda: None,
        prepare_scene_for_save=lambda _name: True,
        has_editor_attachment=lambda: True,
        detach_editor_from_scene=lambda **options: calls.append(
            ("detach-editor", options)
        ),
        detach_scene_from_render=lambda name, **options: calls.append(
            ("detach-render", name, options)
        ),
        attach_editor_to_scene=lambda name, **options: calls.append(
            ("attach-editor", name, options)
        ),
        attach_scene_to_render=lambda name: calls.append(("attach-render", name)),
        get_scene_tree_controller=lambda: None,
        get_inspector_controller=lambda: None,
        observe_scene_events=lambda scene: calls.append(("observe", scene)),
        on_rendering_changed=lambda: calls.append("rendering-changed"),
        request_viewport_update=lambda: calls.append("viewport-update"),
        update_window_title=lambda: calls.append("title-update"),
    )
    return controller, manager, active_name


def _write_scene(tmp_path) -> str:
    path = tmp_path / "loaded.scene"
    path.write_text(json.dumps({"scene": {"entities": []}}), encoding="utf-8")
    return str(path)


def _assert_old_scene_untouched(
    calls: list[object],
    manager: _SceneManager,
    active_name: list[str | None],
) -> None:
    assert active_name == ["old"]
    assert manager.has_scene(_authoring_key("old"))
    assert not any(
        isinstance(call, tuple)
        and call[0] in {"close", "register", "detach-editor", "detach-render"}
        for call in calls
    )


def test_malformed_scene_does_not_replace_active_scene(monkeypatch, tmp_path) -> None:
    calls: list[object] = []
    staged_scene = _Scene(calls)
    controller, manager, active_name = _build_controller(
        monkeypatch,
        calls,
        staged_scene=staged_scene,
        project_root=tmp_path,
    )
    path = tmp_path / "broken.scene"
    path.write_text("{", encoding="utf-8")

    controller.load_scene_from_file(str(path))

    _assert_old_scene_untouched(calls, manager, active_name)
    assert not any(isinstance(call, tuple) and call[0] == "stage" for call in calls)
    assert any(
        isinstance(call, tuple)
        and call[0] == "log-error"
        and str(path) in call[1]
        and "during parse" in call[1]
        for call in calls
    )


def test_repair_failure_does_not_create_or_replace_scene(monkeypatch, tmp_path) -> None:
    calls: list[object] = []
    staged_scene = _Scene(calls)
    controller, manager, active_name = _build_controller(
        monkeypatch,
        calls,
        staged_scene=staged_scene,
        project_root=tmp_path,
    )
    monkeypatch.setattr(
        scene_animation_repair,
        "repair_glb_animation_player_clip_refs",
        lambda _data: (_ for _ in ()).throw(RuntimeError("repair failed")),
    )
    path = _write_scene(tmp_path)

    controller.load_scene_from_file(path)

    _assert_old_scene_untouched(calls, manager, active_name)
    assert not any(isinstance(call, tuple) and call[0] == "stage" for call in calls)
    assert any(
        isinstance(call, tuple)
        and call[0] == "log-error"
        and path in call[1]
        and "during repair" in call[1]
        for call in calls
    )


@pytest.mark.parametrize("failure_stage", ["deserialize", "editor-state"])
def test_failure_after_staging_creation_destroys_only_staging_scene(
    monkeypatch,
    tmp_path,
    failure_stage: str,
) -> None:
    calls: list[object] = []
    staged_scene = _Scene(
        calls,
        load_error=(
            RuntimeError("load failed") if failure_stage == "deserialize" else None
        ),
    )
    controller, manager, active_name = _build_controller(
        monkeypatch,
        calls,
        staged_scene=staged_scene,
        project_root=tmp_path,
    )
    if failure_stage == "editor-state":
        monkeypatch.setattr(
            scene_file_controller_module.EditorStateIO,
            "extract_from_file",
            lambda _path: (_ for _ in ()).throw(RuntimeError("editor state failed")),
        )
    path = _write_scene(tmp_path)

    controller.load_scene_from_file(path)

    _assert_old_scene_untouched(calls, manager, active_name)
    assert not staged_scene.alive
    assert calls.count(("destroy-stage", staged_scene)) == 1
    assert any(
        isinstance(call, tuple)
        and call[0] == "log-error"
        and path in call[1]
        and f"during {failure_stage}" in call[1]
        for call in calls
    )


def test_successful_load_commits_staged_scene_once(monkeypatch, tmp_path) -> None:
    calls: list[object] = []
    staged_scene = _Scene(calls)
    controller, manager, active_name = _build_controller(
        monkeypatch,
        calls,
        staged_scene=staged_scene,
        project_root=tmp_path,
    )
    replace_calls = 0
    original_replace = controller._replace_scene

    def replace_scene(**kwargs) -> None:
        nonlocal replace_calls
        replace_calls += 1
        original_replace(**kwargs)

    monkeypatch.setattr(controller, "_replace_scene", replace_scene)
    path = _write_scene(tmp_path)

    controller.load_scene_from_file(path)

    assert replace_calls == 1
    assert active_name == ["loaded.scene"]
    assert not manager.has_scene(_authoring_key("old"))
    assert manager.get_scene(_authoring_key("loaded.scene")) is staged_scene
    assert staged_scene.alive
    assert not any(
        isinstance(call, tuple) and call[0] == "destroy-stage" for call in calls
    )
    detach_editor_index = next(
        index
        for index, call in enumerate(calls)
        if isinstance(call, tuple) and call[0] == "detach-editor"
    )
    deserialize_index = next(
        index
        for index, call in enumerate(calls)
        if isinstance(call, tuple) and call[0] == "deserialize"
    )
    assert deserialize_index < detach_editor_index
    assert calls.count(("register", _authoring_key("loaded.scene"), staged_scene)) == 1
    assert ("stage", "loaded", "", (11, 12)) in calls
    assert ("attach-editor", "loaded.scene", {"restore_state": False}) in calls
    assert ("attach-render", "loaded.scene") in calls
    assert ("last-scene", path) in calls


def test_equal_stems_in_different_directories_have_distinct_identities(
    monkeypatch, tmp_path
) -> None:
    calls: list[object] = []
    staged_scene = _Scene(calls)
    controller, manager, active_name = _build_controller(
        monkeypatch,
        calls,
        staged_scene=staged_scene,
        project_root=tmp_path,
    )
    other_key = _authoring_key("Scenes/B/Main.scene")
    other_scene = _Scene(calls)
    manager.scenes[other_key] = other_scene
    path = tmp_path / "Scenes" / "A" / "Main.scene"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"scene": {"entities": []}}), encoding="utf-8")

    controller.load_scene_from_file(str(path))

    loaded_key = _authoring_key("Scenes/A/Main.scene")
    assert active_name == [loaded_key.identity]
    assert manager.get_scene(loaded_key) is staged_scene
    assert manager.get_scene(other_key) is other_scene
    assert ("stage", "Main", "", (11, 12)) in calls


def test_successful_load_logs_realtime_stage_boundaries(monkeypatch, tmp_path) -> None:
    calls: list[object] = []
    messages: list[str] = []
    staged_scene = _Scene(calls)
    controller, _manager, _active_name = _build_controller(
        monkeypatch,
        calls,
        staged_scene=staged_scene,
        project_root=tmp_path,
    )
    monkeypatch.setattr(scene_file_controller_module.log, "info", messages.append)
    path = _write_scene(tmp_path)

    controller.load_scene_from_file(path)

    expected_stages = [
        "parse",
        "extract",
        "repair",
        "staging-create",
        "deserialize",
        "editor-start",
        "unknown-component-upgrade",
        "editor-state",
        "commit",
        "commit-detach-editor",
        "commit-detach-render",
        "commit-close-old-scene",
        "commit-register-scene",
        "commit-project-settings",
        "commit-scene-tree",
        "commit-observe-scene",
        "commit-attach-editor",
        "commit-attach-render",
        "commit-rendering-changed",
        "commit-viewport-update",
        "commit-window-title",
    ]
    begin_positions = [
        next(
            index
            for index, message in enumerate(messages)
            if f"stage-begin stage={stage} " in message
        )
        for stage in expected_stages
    ]

    assert messages[0].startswith(f"[SceneLoad] begin path='{path}' thread=")
    assert begin_positions == sorted(begin_positions)
    assert all(
        any(
            f"stage-end stage={stage} " in message
            and "duration_ms=" in message
            and "elapsed_ms=" in message
            for message in messages
        )
        for stage in expected_stages
    )
    assert messages[-1].startswith("[SceneLoad] complete elapsed_ms=")
