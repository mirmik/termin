"""Headless scene runtime for tests and simulation-only execution."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from termin.player.project_runtime_support import (
    close_project_modules,
    create_project_world_controller,
    load_project_modules,
    register_project_runtime_resources,
    scan_project_assets,
)

_RENDER_SCENE_EXTENSION_KEYS = frozenset({"render_mount", "render_state"})


class HeadlessRuntimeError(RuntimeError):
    """Raised when a headless runtime cannot initialize a project scene."""


@dataclass(frozen=True)
class HeadlessRunStats:
    frames: int
    simulated_time: float
    exit_code: int = 0


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
        scene_extensions: Sequence[int] | None = None,
        scene_manager=None,
        manage_bootstrap: bool = True,
    ) -> None:
        self.project_path = Path(project_path)
        self.scene_name = scene_name
        self.load_modules = load_modules
        self.load_assets = load_assets
        self.register_builtin_resources = register_builtin_resources
        self.include_render_resources = include_render_resources
        self.scene_extensions = None if scene_extensions is None else tuple(scene_extensions)
        self.scene_manager = scene_manager
        self.manage_bootstrap = manage_bootstrap
        self._engine = None
        self._project_modules_runtime = None
        self._session_started = False
        self._bootstrap_started = False
        self.scene = None
        self.frames = 0
        self.simulated_time = 0.0
        self.initialized = False
        self.running = False
        self.exit_code = 0

    def initialize(self) -> None:
        from tcbase import log
        from termin.bootstrap import bootstrap_player

        if self.initialized:
            return
        if not self.project_path.exists():
            raise HeadlessRuntimeError(f"Project path does not exist: {self.project_path}")

        bootstrap_player()
        self._bootstrap_started = self.manage_bootstrap
        try:
            if self.scene_extensions is None:
                self.scene_extensions = _default_headless_scene_extensions()
            _validate_headless_scene_extensions(self.scene_extensions)
            from termin.engine import EngineCore

            self._engine = EngineCore()
            log.info(f"[HeadlessRuntime] Initializing project: {self.project_path}")
            if self.register_builtin_resources:
                register_project_runtime_resources(
                    include_render_resources=self.include_render_resources
                )
            if self.load_modules:
                module_scene_manager = self.scene_manager or self._engine.scene_manager
                self._project_modules_runtime = load_project_modules(
                    self.project_path,
                    log_prefix="[HeadlessRuntime]",
                    scene_manager=module_scene_manager,
                )
            controller = create_project_world_controller(
                self.project_path,
                log_prefix="[HeadlessRuntime]",
            )
            if not self._engine.begin_session(controller):
                raise HeadlessRuntimeError("EngineCore refused to start RuntimeSession")
            self._session_started = True
            self._engine.scene_manager.set_scene_elevator(self._elevate_scene)
            if self.load_assets:
                scan_project_assets(self.project_path, log_prefix="[HeadlessRuntime]")

            self.scene = self._load_scene()
            self._activate_primary_scene()
            self.initialized = True
            log.info(f"[HeadlessRuntime] Scene loaded: {self.scene_name}")
        except BaseException:
            self.shutdown()
            raise

    def step(self, dt: float) -> None:
        if dt < 0.0:
            raise ValueError("dt must be non-negative")
        if not self.initialized:
            self.initialize()
        if self.scene is None:
            raise HeadlessRuntimeError("Headless runtime has no scene")

        if self._engine is None:
            raise HeadlessRuntimeError("Headless runtime has no EngineCore")
        self._engine.tick(float(dt))
        self.frames += 1
        self.simulated_time += float(dt)

    def run_frames(self, frames: int, dt: float = 1.0 / 60.0) -> HeadlessRunStats:
        if frames < 0:
            raise ValueError("frames must be non-negative")
        return self._run_loop(frame_limit=frames, dt=dt, realtime=False)

    def run_forever(
        self,
        dt: float = 1.0 / 60.0,
        *,
        realtime: bool = True,
    ) -> HeadlessRunStats:
        return self._run_loop(frame_limit=None, dt=dt, realtime=realtime)

    def request_quit(self, exit_code: int = 0) -> None:
        self.exit_code = int(exit_code)
        self.running = False

    def shutdown(self) -> None:
        from tcbase import log

        if self._session_started and self._engine is not None:
            if not self._engine.end_session():
                log.error("[HeadlessRuntime] RuntimeSession shutdown reported lifecycle failures")
            self._session_started = False
            self._engine.scene_manager.set_scene_elevator(None)

        if self._engine is not None:
            from termin.engine import SceneRole

            self._engine.scene_manager.close_scenes(SceneRole.RUNTIME)
            if not self._engine.shutdown():
                log.error("[HeadlessRuntime] EngineCore shutdown reported lifecycle failures")
        self.scene = None
        self._engine = None

        close_project_modules(
            self._project_modules_runtime,
            log_prefix="[HeadlessRuntime]",
        )
        self._project_modules_runtime = None

        if self._bootstrap_started:
            try:
                from termin.bootstrap import shutdown_player

                shutdown_player()
            except Exception as error:
                log.error(f"[HeadlessRuntime] Failed to shutdown bootstrap runtime: {error}")
            self._bootstrap_started = False
        self.initialized = False
        self.running = False

    def _run_loop(
        self,
        *,
        frame_limit: int | None,
        dt: float,
        realtime: bool,
    ) -> HeadlessRunStats:
        if dt < 0.0:
            raise ValueError("dt must be non-negative")
        if not self.initialized:
            self.initialize()

        from tcbase import log
        import termin.player.runtime as player_runtime

        previous_runtime = player_runtime._active_runtime
        player_runtime._active_runtime = self
        self.running = True
        completed = 0
        try:
            while self.running and (frame_limit is None or completed < frame_limit):
                frame_started_at = time.perf_counter()
                self.step(dt)
                completed += 1
                if realtime and dt > 0.0:
                    elapsed = time.perf_counter() - frame_started_at
                    remaining = dt - elapsed
                    if remaining > 0.0:
                        time.sleep(remaining)
        except KeyboardInterrupt:
            log.info("[HeadlessRuntime] Interrupted by user")
        finally:
            player_runtime._active_runtime = previous_runtime
            self.running = False

        return HeadlessRunStats(
            frames=self.frames,
            simulated_time=self.simulated_time,
            exit_code=self.exit_code,
        )

    def _load_scene(self):
        return self._materialize_scene(self.scene_name, bind=True)

    def _elevate_scene(self, key) -> bool:
        from tcbase import log
        from termin.engine import SceneRole

        if key.role != SceneRole.RUNTIME:
            log.error(
                f"[HeadlessRuntime] Refusing to elevate non-runtime scene '{key.identity}'"
            )
            return False
        try:
            self._materialize_scene(key.identity, bind=False)
            return True
        except Exception as error:
            log.error(
                f"[HeadlessRuntime] Failed to elevate runtime scene "
                f"'{key.identity}': {error}"
            )
            return False

    def _materialize_scene(self, identity: str, *, bind: bool):
        scene_path = self.project_path / identity
        from termin.project.scene_paths import project_scene_identity

        try:
            canonical_identity = project_scene_identity(self.project_path, scene_path)
        except ValueError as error:
            raise HeadlessRuntimeError(
                f"Invalid runtime scene identity '{identity}': {error}"
            ) from error
        if canonical_identity != identity:
            raise HeadlessRuntimeError(
                f"Runtime scene identity '{identity}' resolves as '{canonical_identity}'"
            )
        if not scene_path.exists():
            raise HeadlessRuntimeError(f"Scene not found: {scene_path}")

        try:
            with open(scene_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            raise HeadlessRuntimeError(f"Failed to read scene {scene_path}: {e}") from e

        scene_data, ignored_extensions = _prepare_headless_scene_data(data)
        if ignored_extensions:
            from tcbase import log

            log.info(
                "[HeadlessRuntime] Ignoring render-only scene extensions: "
                + ", ".join(ignored_extensions)
            )

        if self._engine is None:
            raise HeadlessRuntimeError("Headless runtime has no EngineCore")
        from termin.engine import scene as engine_scene

        scene_key = engine_scene.SceneKey(identity, engine_scene.SceneRole.RUNTIME)
        scene = self._engine.scene_manager.create_scene(
            scene_key,
            list(self.scene_extensions),
        )
        if scene is None:
            raise HeadlessRuntimeError(f"Failed to create scene: {identity}")
        bound = False
        if bind and not self._engine.bind_runtime_scene(scene):
            self._engine.scene_manager.close_scene(scene)
            raise HeadlessRuntimeError(
                f"Failed to bind scene to RuntimeSession: {identity}"
            )
        bound = bind
        try:
            scene.source_path = str(scene_path.resolve())
            if scene_data:
                from termin.glb_adapters.scene_animation_repair import repair_glb_animation_player_clip_refs

                repair_glb_animation_player_clip_refs(scene_data)
                scene.load_from_data(scene_data, context=None, update_settings=True)
                from termin.project_modules.runtime import upgrade_scene_unknown_components

                upgrade_scene_unknown_components(scene)
        except BaseException:
            if scene.is_alive():
                if bound:
                    self._engine.unbind_runtime_scene(scene)
                self._engine.scene_manager.close_scene(scene)
            raise
        return scene

    def _activate_primary_scene(self) -> None:
        from termin.engine import require_world_context

        if self._engine is None or self.scene is None:
            raise HeadlessRuntimeError("Cannot activate a headless scene without EngineCore")
        context = require_world_context(self.scene, "HeadlessRuntime initial scene")
        if not context.transition_to(self.scene_name):
            raise HeadlessRuntimeError("RuntimeSession rejected the initial headless scene")
        self._engine.tick(0.0)

        primary = context.primary_scene
        primary_handle = primary.scene_handle() if primary is not None else None
        scene_handle = self.scene.scene_handle()
        if (
            primary_handle is None
            or primary_handle.index != scene_handle.index
            or primary_handle.generation != scene_handle.generation
        ):
            raise HeadlessRuntimeError("RuntimeSession failed to activate the headless scene")


def _prepare_headless_scene_data(data: object) -> tuple[dict, tuple[str, ...]]:
    scene_data = dict(_extract_scene_data(data))
    extensions = scene_data.get("extensions")
    if not isinstance(extensions, dict):
        return scene_data, ()

    headless_extensions = dict(extensions)
    ignored_extensions = tuple(
        sorted(_RENDER_SCENE_EXTENSION_KEYS.intersection(headless_extensions))
    )
    for key in ignored_extensions:
        del headless_extensions[key]

    if headless_extensions:
        scene_data["extensions"] = headless_extensions
    else:
        scene_data.pop("extensions", None)
    return scene_data, ignored_extensions


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


def _validate_headless_scene_extensions(scene_extensions: Sequence[int]) -> None:
    from termin.render import SCENE_EXT_TYPE_RENDER_MOUNT, SCENE_EXT_TYPE_RENDER_STATE

    incompatible_names = {
        SCENE_EXT_TYPE_RENDER_MOUNT: "render_mount",
        SCENE_EXT_TYPE_RENDER_STATE: "render_state",
    }
    requested = sorted(
        incompatible_names[extension]
        for extension in set(scene_extensions)
        if extension in incompatible_names
    )
    if requested:
        message = (
            "Headless runtime cannot attach render-only scene extensions "
            f"without a RenderingManager or graphics host: {', '.join(requested)}"
        )
        from tcbase import log

        log.error(f"[HeadlessRuntime] {message}")
        raise HeadlessRuntimeError(message)


def _default_headless_scene_extensions() -> tuple[int, ...]:
    from termin_nanobind.runtime import preload_sdk_libs

    preload_sdk_libs("termin_graphics", "termin_graphics2")

    from termin.engine import SCENE_EXT_TYPE_COLLISION_WORLD, register_default_scene_extensions

    register_default_scene_extensions()
    return (SCENE_EXT_TYPE_COLLISION_WORLD,)


def run_headless_project(
    project_path: str | Path,
    scene_name: str,
    *,
    frames: int | None = None,
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
        if frames is None:
            return runtime.run_forever(dt=dt)
        return runtime.run_frames(frames=frames, dt=dt)
    finally:
        runtime.shutdown()
