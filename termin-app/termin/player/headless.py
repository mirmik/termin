"""Headless scene runtime for tests and simulation-only execution."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from termin.player.project_runtime_support import (
    load_project_modules,
    register_project_runtime_resources,
    scan_project_assets,
)


class HeadlessRuntimeError(RuntimeError):
    """Raised when a headless runtime cannot initialize a project scene."""


@dataclass(frozen=True)
class HeadlessRunStats:
    frames: int
    simulated_time: float


class HeadlessRuntime:
    """Run scene lifecycle/update without display, GPU, RenderingManager or render passes."""

    def __init__(
        self,
        project_path: str | Path,
        scene_name: str,
        *,
        load_modules: bool = True,
        load_assets: bool = True,
        register_builtin_resources: bool = True,
        include_render_resources: bool = False,
        scene_extensions: Sequence[int] = (),
    ) -> None:
        self.project_path = Path(project_path)
        self.scene_name = scene_name
        self.load_modules = load_modules
        self.load_assets = load_assets
        self.register_builtin_resources = register_builtin_resources
        self.include_render_resources = include_render_resources
        self.scene_extensions = tuple(scene_extensions)
        self.scene = None
        self.frames = 0
        self.simulated_time = 0.0
        self.initialized = False

    def initialize(self) -> None:
        from tcbase import log

        if self.initialized:
            return
        if not self.project_path.exists():
            raise HeadlessRuntimeError(f"Project path does not exist: {self.project_path}")

        log.info(f"[HeadlessRuntime] Initializing project: {self.project_path}")
        if self.register_builtin_resources:
            register_project_runtime_resources(
                include_render_resources=self.include_render_resources
            )
        if self.load_modules:
            load_project_modules(self.project_path, log_prefix="[HeadlessRuntime]")
        if self.load_assets:
            scan_project_assets(self.project_path, log_prefix="[HeadlessRuntime]")

        self.scene = self._load_scene()
        self.initialized = True
        log.info(f"[HeadlessRuntime] Scene loaded: {self.scene_name}")

    def step(self, dt: float) -> None:
        if dt < 0.0:
            raise ValueError("dt must be non-negative")
        if not self.initialized:
            self.initialize()
        if self.scene is None:
            raise HeadlessRuntimeError("Headless runtime has no scene")

        self.scene.update(float(dt))
        self.frames += 1
        self.simulated_time += float(dt)

    def run_frames(self, frames: int, dt: float = 1.0 / 60.0) -> HeadlessRunStats:
        if frames < 0:
            raise ValueError("frames must be non-negative")
        if not self.initialized:
            self.initialize()
        for _index in range(frames):
            self.step(dt)
        return HeadlessRunStats(frames=self.frames, simulated_time=self.simulated_time)

    def shutdown(self) -> None:
        if self.scene is not None and self.scene.is_alive():
            self.scene.destroy()
        self.scene = None
        self.initialized = False

    def _load_scene(self):
        scene_path = self.project_path / self.scene_name
        if not scene_path.exists():
            raise HeadlessRuntimeError(f"Scene not found: {scene_path}")

        try:
            with open(scene_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            raise HeadlessRuntimeError(f"Failed to read scene {scene_path}: {e}") from e

        scene_data = _extract_scene_data(data)

        from termin.visualization.core.scene import create_scene

        scene = create_scene(
            name=self.scene_name,
            extensions=list(self.scene_extensions),
        )
        scene.source_path = str(scene_path.resolve())
        if scene_data:
            scene.load_from_data(scene_data, context=None, update_settings=True)
            from termin.modules import upgrade_scene_unknown_components

            upgrade_scene_unknown_components(scene)
        return scene


def _extract_scene_data(data: object) -> dict:
    if not isinstance(data, dict):
        raise HeadlessRuntimeError("Scene file root must be a JSON object")

    scene_data = data.get("scene")
    if scene_data is None:
        scenes = data.get("scenes")
        if isinstance(scenes, list) and len(scenes) > 0:
            scene_data = scenes[0]
    if scene_data is None and ("entities" in data or "uuid" in data):
        scene_data = data
    if not isinstance(scene_data, dict):
        raise HeadlessRuntimeError("Scene file has no scene object")
    return scene_data


def run_headless_project(
    project_path: str | Path,
    scene_name: str,
    *,
    frames: int = 1,
    dt: float = 1.0 / 60.0,
    load_modules: bool = True,
    load_assets: bool = True,
) -> HeadlessRunStats:
    runtime = HeadlessRuntime(
        project_path=project_path,
        scene_name=scene_name,
        load_modules=load_modules,
        load_assets=load_assets,
    )
    try:
        return runtime.run_frames(frames=frames, dt=dt)
    finally:
        runtime.shutdown()
