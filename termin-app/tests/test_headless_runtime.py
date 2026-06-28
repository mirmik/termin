import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import termin.modules.runtime as modules_runtime
from termin.player.headless import HeadlessRuntime, HeadlessRuntimeError
from termin.physics_components import PhysicsWorldComponent
from termin.scene import PythonComponent
from termin.engine import create_scene, scene_ext_attached_names
from termin.render_framework import tc_pipeline_registry_count


class HeadlessCounterComponent(PythonComponent):
    def __init__(self):
        super().__init__()
        self.start_count = 0
        self.update_count = 0
        self.last_dt = 0.0

    def start(self) -> None:
        self.start_count += 1

    def update(self, dt: float) -> None:
        self.update_count += 1
        self.last_dt = dt


class HeadlessQuitComponent(PythonComponent):
    def __init__(self):
        super().__init__()
        self.update_count = 0

    def update(self, dt: float) -> None:
        from termin.player import request_quit

        self.update_count += 1
        if self.update_count >= 3:
            request_quit(7)


def _write_scene_with_component(project_path: Path, scene_name: str = "Main.scene") -> None:
    source_scene = create_scene("source", extensions=[])
    entity = source_scene.create_entity("Counter")
    entity.add_component(HeadlessCounterComponent())
    try:
        scene_data = source_scene.serialize()
    finally:
        source_scene.destroy()

    (project_path / scene_name).write_text(
        json.dumps({"scene": scene_data}),
        encoding="utf-8",
    )


def _write_scene_with_quit_component(
    project_path: Path,
    scene_name: str = "Main.scene",
) -> None:
    source_scene = create_scene("source", extensions=[])
    entity = source_scene.create_entity("Quitter")
    entity.add_component(HeadlessQuitComponent())
    try:
        scene_data = source_scene.serialize()
    finally:
        source_scene.destroy()

    (project_path / scene_name).write_text(
        json.dumps({"scene": scene_data}),
        encoding="utf-8",
    )


def _write_scene_with_physics_world(
    project_path: Path,
    scene_name: str = "Main.scene",
) -> None:
    source_scene = create_scene("source", extensions=[])
    entity = source_scene.create_entity("Physics")
    entity.add_component(PhysicsWorldComponent())
    try:
        scene_data = source_scene.serialize()
    finally:
        source_scene.destroy()

    (project_path / scene_name).write_text(
        json.dumps({"scene": scene_data}),
        encoding="utf-8",
    )


def _write_hot_reload_project(project_path: Path) -> None:
    (project_path / "gameplay").mkdir()
    (project_path / "gameplay.pymodule").write_text(
        "\n".join(
            [
                "name: gameplay",
                "type: python",
                "root: .",
                "packages: [gameplay]",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (project_path / "gameplay" / "__init__.py").write_text(
        "from .components import HotReloadProbeComponent\n",
        encoding="utf-8",
    )
    _write_hot_reload_component_sources(project_path, step=1, mtime=1_800_000_001)
    (project_path / "Main.scene").write_text(
        json.dumps(
            {
                "scene": {
                    "entities": [
                        {
                            "uuid": "00000000-0000-0000-7000-000000000001",
                            "name": "Probe",
                            "priority": 0,
                            "visible": True,
                            "enabled": True,
                            "pickable": True,
                            "selectable": True,
                            "layer": 0,
                            "flags": 0,
                            "pose": {
                                "position": [0, 0, 0],
                                "rotation": [0, 0, 0, 1],
                            },
                            "scale": [1, 1, 1],
                            "components": [
                                {
                                    "type": "HotReloadProbeComponent",
                                    "data": {"value": 5},
                                }
                            ],
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )


def _write_hot_reload_component_sources(project_path: Path, *, step: int, mtime: int) -> None:
    package = project_path / "gameplay"
    version_path = package / "version.py"
    component_path = package / "components.py"

    version_path.write_text(f"STEP = {step}\n", encoding="utf-8")
    component_path.write_text(
        "\n".join(
            [
                "from termin.inspect import InspectField",
                "from termin.scene import PythonComponent",
                "from .version import STEP",
                "",
                "",
                "class HotReloadProbeComponent(PythonComponent):",
                "    inspect_fields = {",
                "        'value': InspectField(path='value', label='Value', kind='int'),",
                "    }",
                "",
                "    def __init__(self):",
                "        super().__init__()",
                "        self.value = 0",
                "        self.step = STEP",
                "",
                "    def update(self, dt: float) -> None:",
                "        self.value += STEP",
                "        self.step = STEP",
                "",
            ]
        ),
        encoding="utf-8",
    )
    os.utime(version_path, (mtime, mtime))
    os.utime(component_path, (mtime, mtime))


def _write_broken_hot_reload_component_source(project_path: Path, *, mtime: int) -> None:
    component_path = project_path / "gameplay" / "components.py"
    component_path.write_text(
        "\n".join(
            [
                "from termin.scene import PythonComponent",
                "",
                "",
                "class HotReloadProbeComponent(PythonComponent):",
                "    def update(self, dt: float) -> None:",
                "        self.value += ",
                "",
            ]
        ),
        encoding="utf-8",
    )
    os.utime(component_path, (mtime, mtime))


def _reset_project_modules_runtime() -> None:
    runtime = modules_runtime._instance
    if runtime is not None:
        for record in runtime.records():
            if record.state.name == "Loaded":
                runtime.unload_module(record.id)
    modules_runtime._instance = None


def test_python_module_load_discovers_components_without_descriptor_list(tmp_path: Path) -> None:
    _reset_project_modules_runtime()
    _write_hot_reload_project(tmp_path)

    try:
        project_modules = modules_runtime.get_project_modules_runtime()

        assert project_modules.load_project(tmp_path), project_modules.last_error
        record = project_modules.find("gameplay")
        assert record is not None
        assert record.state.name == "Loaded"
    finally:
        _reset_project_modules_runtime()


def test_headless_runtime_reloads_python_module_component_in_live_scene(tmp_path: Path) -> None:
    from termin.engine import SceneManager

    _reset_project_modules_runtime()
    _write_hot_reload_project(tmp_path)
    scene_manager = SceneManager()
    runtime = HeadlessRuntime(
        tmp_path,
        "Main.scene",
        load_modules=True,
        load_assets=False,
        register_builtin_resources=False,
    )

    try:
        runtime.initialize()
        # TermModulesIntegration discovers live scenes through SceneManager.
        scene_manager.register_scene("Main.scene", runtime.scene.scene_handle())
        components = runtime.scene.get_components_of_type("HotReloadProbeComponent")
        assert len(components) == 1
        component = components[0]
        assert component.value == 5
        assert component.step == 1
        assert runtime.scene.get_component_type_counts().get("UnknownComponent") is None

        runtime.run_frames(frames=1, dt=0.01)
        assert component.value == 6

        _write_hot_reload_component_sources(tmp_path, step=10, mtime=1_800_000_010)

        project_modules = modules_runtime.get_project_modules_runtime()
        assert project_modules.reload_module("gameplay"), project_modules.last_error

        reloaded_components = runtime.scene.get_components_of_type("HotReloadProbeComponent")
        assert len(reloaded_components) == 1
        reloaded = reloaded_components[0]
        assert reloaded is not component
        assert reloaded.value == 6
        assert reloaded.step == 10
        assert runtime.scene.get_component_type_counts().get("UnknownComponent") is None

        runtime.run_frames(frames=1, dt=0.01)
        assert reloaded.value == 16
        assert reloaded.step == 10
    finally:
        scene_manager.unregister_scene("Main.scene")
        runtime.shutdown()
        _reset_project_modules_runtime()


def test_headless_runtime_keeps_unknown_component_after_failed_python_reload(
    tmp_path: Path,
) -> None:
    from termin.engine import SceneManager

    _reset_project_modules_runtime()
    _write_hot_reload_project(tmp_path)
    scene_manager = SceneManager()
    runtime = HeadlessRuntime(
        tmp_path,
        "Main.scene",
        load_modules=True,
        load_assets=False,
        register_builtin_resources=False,
    )

    try:
        runtime.initialize()
        scene_manager.register_scene("Main.scene", runtime.scene.scene_handle())

        components = runtime.scene.get_components_of_type("HotReloadProbeComponent")
        assert len(components) == 1
        runtime.run_frames(frames=1, dt=0.01)
        assert components[0].value == 6

        _write_broken_hot_reload_component_source(tmp_path, mtime=1_800_000_020)

        project_modules = modules_runtime.get_project_modules_runtime()
        assert not project_modules.reload_module("gameplay")
        record = project_modules.find("gameplay")
        assert record is not None
        assert record.state.name == "Failed"
        assert "Failed to import package 'gameplay'" in project_modules.last_error
        assert runtime.scene.get_component_type_counts().get("HotReloadProbeComponent") is None
        assert runtime.scene.get_component_type_counts().get("UnknownComponent") == 1

        _write_hot_reload_component_sources(tmp_path, step=10, mtime=1_800_000_030)

        assert project_modules.reload_module("gameplay"), project_modules.last_error
        reloaded_components = runtime.scene.get_components_of_type("HotReloadProbeComponent")
        assert len(reloaded_components) == 1
        reloaded = reloaded_components[0]
        assert reloaded.value == 6
        assert reloaded.step == 10
        assert runtime.scene.get_component_type_counts().get("UnknownComponent") is None

        runtime.run_frames(frames=1, dt=0.01)
        assert reloaded.value == 16
    finally:
        scene_manager.unregister_scene("Main.scene")
        runtime.shutdown()
        _reset_project_modules_runtime()


def test_headless_runtime_ticks_scene_without_render_extensions(tmp_path: Path) -> None:
    _write_scene_with_component(tmp_path)
    runtime = HeadlessRuntime(
        tmp_path,
        "Main.scene",
        load_modules=False,
        load_assets=False,
        register_builtin_resources=False,
    )

    try:
        runtime.initialize()
        attached_exts = scene_ext_attached_names(runtime.scene)
        assert "render_mount" not in attached_exts
        assert "render_state" not in attached_exts

        components = runtime.scene.get_components_of_type("HeadlessCounterComponent")
        assert len(components) == 1

        stats = runtime.run_frames(frames=3, dt=0.125)

        component = components[0]
        assert component.start_count == 1
        assert component.update_count == 3
        assert component.last_dt == pytest.approx(0.125)
        assert stats.frames == 3
        assert stats.simulated_time == pytest.approx(0.375)
    finally:
        runtime.shutdown()


def test_headless_runtime_run_forever_stops_on_request_quit(tmp_path: Path) -> None:
    _write_scene_with_quit_component(tmp_path)
    runtime = HeadlessRuntime(
        tmp_path,
        "Main.scene",
        load_modules=False,
        load_assets=False,
        register_builtin_resources=False,
    )

    try:
        stats = runtime.run_forever(dt=0.01, realtime=False)

        components = runtime.scene.get_components_of_type("HeadlessQuitComponent")
        assert len(components) == 1
        assert components[0].update_count == 3
        assert stats.frames == 3
        assert stats.simulated_time == pytest.approx(0.03)
        assert stats.exit_code == 7
    finally:
        runtime.shutdown()


def test_headless_runtime_attaches_collision_world_for_physics(tmp_path: Path) -> None:
    _write_scene_with_physics_world(tmp_path)
    baseline_pipeline_count = tc_pipeline_registry_count()
    runtime = HeadlessRuntime(
        tmp_path,
        "Main.scene",
        load_modules=False,
        load_assets=False,
    )

    try:
        runtime.initialize()
        assert tc_pipeline_registry_count() == baseline_pipeline_count
        attached_exts = scene_ext_attached_names(runtime.scene)
        assert attached_exts == ["collision_world"]

        components = runtime.scene.get_components_of_type("PhysicsWorldComponent")
        assert len(components) == 1

        runtime.run_frames(frames=1, dt=0.01)
        assert tc_pipeline_registry_count() == baseline_pipeline_count

        component = components[0]
        assert component.physics_world.collision_world() is not None
    finally:
        runtime.shutdown()


def test_headless_runtime_rejects_missing_scene(tmp_path: Path) -> None:
    runtime = HeadlessRuntime(
        tmp_path,
        "Missing.scene",
        load_modules=False,
        load_assets=False,
        register_builtin_resources=False,
    )

    with pytest.raises(HeadlessRuntimeError, match="Scene not found"):
        runtime.initialize()


def test_player_cli_runs_headless_empty_scene(tmp_path: Path) -> None:
    (tmp_path / "Main.scene").write_text(
        json.dumps({"scene": {"entities": []}}),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "termin.player",
            str(tmp_path),
            "--scene",
            "Main.scene",
            "--headless",
            "--frames",
            "2",
            "--dt",
            "0.01",
            "--no-assets",
            "--no-modules",
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
