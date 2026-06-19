import json
import subprocess
import sys
from pathlib import Path

import pytest

from termin.player.headless import HeadlessRuntime, HeadlessRuntimeError
from termin.scene import PythonComponent
from termin.visualization.core.scene import create_scene, scene_ext_attached_names


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
        assert scene_ext_attached_names(runtime.scene) == []

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

