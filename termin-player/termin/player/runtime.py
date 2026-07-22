"""
Minimal game runtime for standalone player.
"""

from __future__ import annotations

import time
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from termin.player.project_runtime_support import (
    load_project_modules,
    register_project_runtime_resources,
    scan_project_assets,
)
from termin.player.project_settings import (
    ProjectPlayerWindowSettings,
    load_project_runtime_settings,
)

if TYPE_CHECKING:
    from termin.scene import TcScene as Scene


_active_runtime: "PlayerRuntime | None" = None


def active_runtime() -> "PlayerRuntime | None":
    """Return the PlayerRuntime currently executing on this thread, if any."""
    return _active_runtime


def request_quit(exit_code: int = 0) -> bool:
    """Request graceful standalone player shutdown from game code.

    Returns True when an active player runtime accepted the request. In editor
    or tool contexts there may be no standalone runtime, and callers should not
    fall back to raising SystemExit from input callbacks.
    """
    runtime = _active_runtime
    if runtime is None:
        from tcbase import log
        log.warning("[PlayerRuntime] Quit requested without an active player runtime")
        return False

    runtime.request_quit(exit_code)
    return True




def _resolve_player_window_settings(
    project_path: Path,
    *,
    width: int | None,
    height: int | None,
    fullscreen: bool | None,
):
    base = _load_project_player_window_settings(project_path)
    return ProjectPlayerWindowSettings(
        width=_resolve_positive_window_int(width, base.width, "width"),
        height=_resolve_positive_window_int(height, base.height, "height"),
        fullscreen=_resolve_window_bool(fullscreen, base.fullscreen, "fullscreen"),
        vsync=base.vsync,
    )


def _load_project_player_window_settings(project_path: Path):
    return load_project_runtime_settings(project_path).player_window


def _create_player_backend_window(
    graphics_session,
    *,
    title: str,
    width: int,
    height: int,
    vsync: bool,
):
    from termin.display import PresentationMode

    presentation_mode = PresentationMode.VSYNC if vsync else PresentationMode.IMMEDIATE
    try:
        return graphics_session.create_window(
            title,
            width,
            height,
            presentation_mode=presentation_mode,
        )
    except Exception as error:
        requested_mode = "vsync" if vsync else "immediate"
        raise RuntimeError(
            "failed to create player window with requested presentation mode "
            f"'{requested_mode}': {error}"
        ) from error


def _resolve_positive_window_int(value: object, default: int, field_name: str) -> int:
    from tcbase import log

    if value is None:
        return default
    if type(value) is not int or value <= 0:
        log.error(f"[PlayerRuntime] Window {field_name} must be a positive integer, using {default}")
        return default
    return value


def _resolve_window_bool(value: object, default: bool, field_name: str) -> bool:
    from tcbase import log

    if value is None:
        return default
    if type(value) is not bool:
        log.error(f"[PlayerRuntime] Window {field_name} must be a boolean, using {default}")
        return default
    return value

class PlayerRuntime:
    """
    Standalone game runtime.

    Manages window, scene, and game loop without editor overhead.
    Uses RenderingManager for display/viewport management.
    """

    def __init__(
        self,
        project_path: str | Path,
        scene_name: str,
        width: int | None = None,
        height: int | None = None,
        title: str = "Termin Player",
        fullscreen: bool | None = None,
        mcp_enabled: bool = False,
        mcp_options: dict | None = None,
        engine=None,
    ):
        self.project_path = Path(project_path)
        self.scene_name = scene_name
        window_settings = _resolve_player_window_settings(
            self.project_path,
            width=width,
            height=height,
            fullscreen=fullscreen,
        )
        self.width = window_settings.width
        self.height = window_settings.height
        self.title = title
        self.fullscreen = window_settings.fullscreen
        self.vsync = window_settings.vsync
        self.render_phase_names = load_project_runtime_settings(self.project_path).render_phase_names
        self.mcp_enabled = bool(mcp_enabled)
        self.mcp_options = mcp_options if mcp_options is not None else {}
        self._scene_file_data = None

        self.running = False
        self.scene: Scene | None = None
        self.window = None
        self._graphics_session = None
        self.graphics = None
        self.camera = None
        self._engine = engine
        self._owns_engine = engine is None
        self._surface_size: tuple[int, int] = (0, 0)

        # Timing
        self.target_fps = 60
        self.delta_time = 1.0 / self.target_fps
        self.last_time = 0.0

        # Display/Input (managed via RenderingManager)
        self._display = None
        self._viewport = None
        self._viewports = []
        self._fallback_render_target = None
        self._input_manager = None
        self._mcp_executor = None
        self._mcp_server = None
        self._resource_manager = None
        self._pipeline_reload_binding = None
        self.exit_code = 0

    @property
    def display(self):
        return self._display

    @property
    def viewport(self):
        return self._viewport

    @property
    def rendering_manager(self):
        if self._engine is None:
            raise RuntimeError("PlayerRuntime has no initialized EngineCore")
        return self._engine.rendering_manager

    def initialize(self) -> bool:
        """Initialize player systems."""
        from tcbase import log
        from termin.bootstrap import bootstrap_player

        bootstrap_player()
        from termin.render import configure_project_render_phases
        configure_project_render_phases(self.render_phase_names)
        self._configure_backend_default()

        # Load the app render bindings before resource preloaders touch
        # materials/shaders. Importing tgfx-only helpers first leaves some
        # build materials in a state where the runtime pipeline clears but
        # draws no scene geometry.
        self._ensure_texture_registry()

        if not self._ensure_engine_core():
            return False
        if not self._configure_shader_runtime():
            return False

        from termin.default_assets.resource_manager import DefaultResourceManager
        from termin.default_assets.render.pipeline_reload_binding import PipelineReloadBinding

        self._resource_manager = DefaultResourceManager.instance()
        self._pipeline_reload_binding = PipelineReloadBinding(
            self._resource_manager,
            self._engine.rendering_manager,
        )

        log.info(f"[PlayerRuntime] Initializing project: {self.project_path}")

        # Register components
        self._register_components()

        # Load C++ modules
        self._load_modules()

        self._scan_project_assets()

        # Create default pipeline and configure RenderingManager
        manager = self._engine.rendering_manager
        pipeline = manager.create_pipeline("Default")
        log.info(f"[PlayerRuntime] Created pipeline: {pipeline.name} with {len(pipeline.passes)} passes")

        manager.set_pipeline_factory(self._create_pipeline_for_name)

        # Create one host-owned graphics runtime before its presentation
        # window. RenderEngine reuses this device instead of creating a second
        # device with incompatible texture handles.
        from termin.display import WindowedGraphicsSession, quit_sdl

        try:
            self._graphics_session = WindowedGraphicsSession.create_native()
            self.window = _create_player_backend_window(
                self._graphics_session,
                title=self.title,
                width=self.width,
                height=self.height,
                vsync=self.vsync,
            )
            manager.render_engine.set_graphics_host(self._graphics_session.graphics)
            from tgfx import Tgfx2Context

            self.graphics = Tgfx2Context.from_runtime(self._graphics_session.graphics)
            if self.fullscreen:
                self.window.set_fullscreen(True)
        except Exception as e:
            log.error(f"[PlayerRuntime] Failed to create backend window: {e}")
            if self._graphics_session is not None:
                try:
                    self._graphics_session.close()
                except Exception as close_error:
                    log.error(f"[PlayerRuntime] Failed to close graphics runtime: {close_error}")
                self._graphics_session = None
            quit_sdl()
            return False

        # Create display
        from termin.display import Display

        self._surface_size = self.window.framebuffer_size()
        surface_width, surface_height = self._surface_size
        self._display = Display.offscreen(
            self.graphics.device, surface_width, surface_height, name="Main"
        )
        manager.set_display_factory(self._runtime_display_factory)

        # Load scene
        scene_path = self.project_path / self.scene_name
        if not scene_path.exists():
            log.error(f"[PlayerRuntime] Scene not found: {scene_path}")
            return False

        import json
        from termin.engine import create_scene

        with open(scene_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._scene_file_data = data

        # Create new scene and load data
        self.scene = create_scene(name=self.scene_name)
        self.scene.source_path = str(scene_path.resolve())
        scene_data = data.get("scene")
        if scene_data is None:
            scenes = data.get("scenes")
            if isinstance(scenes, list) and len(scenes) > 0:
                scene_data = scenes[0]
        if scene_data is None and ("entities" in data or "uuid" in data):
            scene_data = data
        if scene_data:
            from termin.glb.scene_animation_repair import repair_glb_animation_player_clip_refs

            repair_glb_animation_player_clip_refs(scene_data)
            self.scene.load_from_data(scene_data, context=None, update_settings=True)
            from termin.project_modules.runtime import upgrade_scene_unknown_components
            upgraded = upgrade_scene_unknown_components(self.scene)
            if upgraded > 0:
                log.info(f"[PlayerRuntime] Upgraded {upgraded} unknown component(s)")

        log.info(f"[PlayerRuntime] Scene loaded: {self.scene_name}")

        if not self._attach_scene_rendering(manager, pipeline):
            return False

        # Set up input handling
        self._setup_input()
        self._start_mcp_server()

        log.info("[PlayerRuntime] Initialization complete")
        return True

    def _start_mcp_server(self) -> None:
        from tcbase import log
        from termin.player.mcp_server import start_player_mcp_server

        executor, server = start_player_mcp_server(
            self,
            explicit=self.mcp_enabled,
            manifest_options=self.mcp_options,
        )
        self._mcp_executor = executor
        self._mcp_server = server
        if executor is not None and server is None:
            log.error("[PlayerRuntime] Player MCP executor was created but server did not start")

    def _runtime_display_factory(self, name: str):
        """Return the player's native display for scene-declared displays."""
        from tcbase import log

        if self._display is None:
            log.error(f"[PlayerRuntime] Display factory requested '{name}' before display initialization")
            return None

        if name != "":
            self._display.name = name
        return self._display

    def _create_pipeline_for_name(self, name: str):
        """Resolve non-default pipelines from loaded build resources."""
        if not name or name in ("Default", "(Default)"):
            return None

        rm = self._resource_manager
        if rm is None:
            raise RuntimeError("PlayerRuntime resource manager is not initialized")
        if "-" in name:
            pipeline = rm.get_pipeline_by_uuid(name)
            if pipeline is not None:
                return pipeline

        pipeline = rm.get_pipeline(name)
        if pipeline is not None:
            return pipeline

        from tcbase import log
        log.error(f"[PlayerRuntime] Pipeline not found: {name}")
        return None

    def _attach_scene_rendering(self, manager, pipeline) -> bool:
        """Attach scene rendering from saved viewport/render-target config."""
        from tcbase import log

        viewports = manager.attach_scene_full(self.scene)
        if len(viewports) > 0:
            self._viewports = list(viewports)
            self._viewport = viewports[0]
            self._disable_unrenderable_unused_render_targets(manager, viewports)
            log.info(f"[PlayerRuntime] Attached scene rendering: {len(viewports)} viewport(s)")
            return True

        log.warning("[PlayerRuntime] Scene has no attachable viewport config, creating fallback viewport")
        self._setup_camera()
        return self._create_fallback_viewport(manager, pipeline)

    def _create_fallback_viewport(self, manager, pipeline) -> bool:
        """Create a minimal runtime viewport for scenes without saved display config."""
        from tcbase import log
        from termin.render_framework import render_target_new

        if self._display is None:
            log.error("[PlayerRuntime] Cannot create fallback viewport without display")
            return False
        if self.scene is None:
            log.error("[PlayerRuntime] Cannot create fallback viewport without scene")
            return False
        if self.camera is None:
            log.error("[PlayerRuntime] Cannot create fallback viewport without camera")
            return False

        self._display.name = "Main"
        manager.add_display(self._display, "Main")

        self._fallback_render_target = render_target_new("Main")
        self._fallback_render_target.scene = self.scene.scene_handle()
        self._fallback_render_target.camera = self.camera
        self._fallback_render_target.pipeline = pipeline
        self._fallback_render_target.dynamic_resolution = True
        self._fallback_render_target.enabled = True

        self._viewport = self._display.create_viewport(
            scene=self.scene,
            camera=self.camera,
            rect=(0.0, 0.0, 1.0, 1.0),
            name="Main",
        )
        self._viewport.render_target = self._fallback_render_target
        if not manager.register_viewport_attachment(self._display, self._viewport):
            log.error("[PlayerRuntime] Failed to register fallback viewport attachment")
            self._display.remove_viewport(self._viewport)
            self._viewport = None
            return False
        self._viewports = [self._viewport]
        log.info("[PlayerRuntime] Created fallback viewport with render target 'Main'")
        return True

    def _disable_unrenderable_unused_render_targets(self, manager, viewports) -> None:
        """Keep saved helper render targets from being rendered as standalone outputs."""
        from tcbase import log

        viewport_render_targets = set()
        for viewport in viewports:
            render_target = viewport.render_target
            if render_target is not None:
                viewport_render_targets.add((render_target.index, render_target.generation))

        for render_target in manager.managed_render_targets:
            key = (render_target.index, render_target.generation)
            if key in viewport_render_targets:
                continue
            if render_target.camera is not None and render_target.pipeline is not None:
                continue

            render_target.enabled = False
            log.warning(
                "[PlayerRuntime] Disabled unused render target "
                f"'{render_target.name}' because it has no camera or pipeline"
            )

    def _configure_backend_default(self) -> None:
        """Use the source-player platform default unless explicitly overridden."""
        from tcbase import log

        if "TERMIN_BACKEND" in os.environ:
            backend = os.environ["TERMIN_BACKEND"]
            log.info(f"[PlayerRuntime] Using TERMIN_BACKEND={backend}")
            return

        default_backend = "d3d11" if sys.platform == "win32" else "vulkan"
        os.environ["TERMIN_BACKEND"] = default_backend
        log.info(
            f"[PlayerRuntime] TERMIN_BACKEND not set; using {default_backend} for standalone player"
        )

    def _configure_shader_runtime(self) -> bool:
        """Configure development shader artifacts for source-project execution."""
        from termin.shader_runtime import configure_project_shader_runtime

        return configure_project_shader_runtime(
            self.project_path,
            label="source player",
            render_engine=self._engine.rendering_manager.render_engine,
        )

    def _ensure_texture_registry(self) -> None:
        """Load the tgfx texture registry before app-native modules."""
        from tgfx import tc_texture_count

        tc_texture_count()

    def _ensure_engine_core(self) -> bool:
        """Ensure EngineCore exists so RenderingManager has a real backend."""
        from tcbase import log
        if self._engine is not None:
            return True

        try:
            from termin.engine import register_default_scene_extensions

            register_default_scene_extensions()
            from termin.engine import EngineCore

            self._engine = EngineCore()
        except TypeError as e:
            log.error(
                "[PlayerRuntime] EngineCore cannot be created from Python. "
                "Rebuild termin-engine bindings after enabling EngineCore.__init__."
            )
            log.error(f"[PlayerRuntime] EngineCore creation failed: {e}")
            return False
        except Exception as e:
            log.error(f"[PlayerRuntime] EngineCore creation failed: {e}")
            return False

        log.info("[PlayerRuntime] Created EngineCore from Python")
        return True

    def _register_components(self):
        """Register builtin components and resources."""
        register_project_runtime_resources(include_render_resources=True)

    def _load_modules(self) -> None:
        """Load all project modules through termin-modules runtime."""
        load_project_modules(
            self.project_path,
            log_prefix="[PlayerRuntime]",
            scene_manager=self._engine.scene_manager,
        )

    def _scan_project_assets(self):
        """Scan project directory for assets and register them."""
        scan_project_assets(self.project_path, log_prefix="[PlayerRuntime]")

    def _setup_camera(self):
        """Find existing camera or create default one."""
        from tcbase import log
        from termin.render_components.camera import CameraComponent

        log.info(f"[PlayerRuntime] Looking for camera in {len(self.scene.entities)} entities")

        # Look for existing camera in scene
        for entity in self.scene.entities:
            camera = entity.get_component(CameraComponent)
            if camera is not None:
                self.camera = camera
                log.info(f"[PlayerRuntime] Found camera on entity '{entity.name}'")
                return

        # Create default camera if none found
        log.warn("[PlayerRuntime] No camera found in scene, creating default")

        camera_entity = self.scene.create_entity("PlayerCamera")
        self.camera = CameraComponent()
        camera_entity.add_component(self.camera)

        if self._setup_camera_from_saved_editor(camera_entity):
            return

        # Position camera behind the scene and point it at the default content area.
        from termin.geombase import Quat, Vec3
        camera_position = Vec3(0, -6, 3)
        camera_target = Vec3(0, 0, 1)
        camera_entity.transform.set_local_position(camera_position)
        camera_entity.transform.set_local_rotation(
            Quat.look_rotation(camera_target - camera_position, Vec3(0, 0, 1))
        )
        log.info("[PlayerRuntime] Created default camera at (0, -6, 3), looking at (0, 0, 1)")

    def _setup_camera_from_saved_editor(self, camera_entity) -> bool:
        """Use saved editor camera as a runtime fallback when the scene has no game camera."""
        from tcbase import log
        from termin.geombase import Quat, Vec3

        if not isinstance(self._scene_file_data, dict):
            return False

        editor = self._scene_file_data.get("editor")
        if not isinstance(editor, dict):
            return False

        camera = editor.get("camera")
        if not isinstance(camera, dict):
            return False

        position = camera.get("position")
        rotation = camera.get("rotation")
        if not self._is_vec3_list(position) or not self._is_quat_list(rotation):
            log.warning("[PlayerRuntime] Saved editor camera is incomplete, using default fallback camera")
            return False

        camera_entity.transform.set_local_position(Vec3(position[0], position[1], position[2]))
        camera_entity.transform.set_local_rotation(Quat(rotation[0], rotation[1], rotation[2], rotation[3]))

        camera_components = camera.get("editor_entities")
        if isinstance(camera_components, dict):
            self._apply_saved_editor_camera_component(camera_components.get("camera"))

        log.info(
            "[PlayerRuntime] Created fallback camera from saved editor camera "
            f"at ({position[0]}, {position[1]}, {position[2]})"
        )
        return True

    def _apply_saved_editor_camera_component(self, components) -> None:
        if not isinstance(components, list):
            return

        for component in components:
            if not isinstance(component, dict):
                continue
            if component.get("type") != "CameraComponent":
                continue

            data = component.get("data")
            if not isinstance(data, dict):
                return

            self._apply_saved_camera_data(data)
            return

    def _apply_saved_camera_data(self, data: dict) -> None:
        near_clip = data.get("near_clip")
        if isinstance(near_clip, (int, float)):
            self.camera.near_clip = float(near_clip)

        far_clip = data.get("far_clip")
        if isinstance(far_clip, (int, float)):
            self.camera.far_clip = float(far_clip)

        ortho_size = data.get("ortho_size")
        if isinstance(ortho_size, (int, float)):
            self.camera.ortho_size = float(ortho_size)

        fov_x_degrees = data.get("fov_x_degrees")
        if isinstance(fov_x_degrees, (int, float)):
            self.camera.fov_x_degrees = float(fov_x_degrees)

        fov_y_degrees = data.get("fov_y_degrees")
        if isinstance(fov_y_degrees, (int, float)):
            self.camera.fov_y_degrees = float(fov_y_degrees)

        fov_mode = data.get("fov_mode")
        if isinstance(fov_mode, str) and fov_mode != "":
            self.camera.fov_mode = fov_mode

        layer_mask = data.get("layer_mask")
        if isinstance(layer_mask, str) and layer_mask.startswith("0x"):
            self.camera.layer_mask = int(layer_mask, 16)
        elif isinstance(layer_mask, int):
            self.camera.layer_mask = layer_mask

    def _is_vec3_list(self, value) -> bool:
        if not isinstance(value, list) or len(value) != 3:
            return False
        return all(isinstance(item, (int, float)) for item in value)

    def _is_quat_list(self, value) -> bool:
        if not isinstance(value, list) or len(value) != 4:
            return False
        return all(isinstance(item, (int, float)) for item in value)

    def _setup_input(self):
        """Set up input handling."""
        from tcbase import log
        from termin.display import BasicDisplayInputManager

        if self._display is None:
            log.error("[PlayerRuntime] Cannot set up input without display")
            return

        input_manager = BasicDisplayInputManager(self._display.handle)
        active_viewports = 0
        for viewport in self._viewports:
            mode = viewport.input_mode or "simple"
            if mode == "none" or mode == "editor":
                continue
            if mode not in ("simple", "basic"):
                log.warning(
                    f"[PlayerRuntime] Unknown viewport input mode '{mode}' for viewport '{viewport.name}'"
                )
                continue

            vp_index, vp_generation = viewport._viewport_handle()
            if input_manager.add_viewport(vp_index, vp_generation):
                active_viewports += 1
            else:
                log.error(f"[PlayerRuntime] Failed to create input manager for viewport '{viewport.name}'")

        if self.window is not None:
            self.window.set_input_display(*self._display.handle)

        self._input_manager = input_manager
        log.info(f"[PlayerRuntime] Input configured for {active_viewports} viewport(s)")

    def run(self):
        """Run the game loop."""
        from tcbase import log
        global _active_runtime

        if not self.initialize():
            log.error("[PlayerRuntime] Initialization failed")
            self.shutdown()
            return

        log.info("[PlayerRuntime] Starting game loop")
        self.running = True
        self.last_time = time.perf_counter()

        previous_runtime = _active_runtime
        _active_runtime = self
        try:
            while self.running and not self.window.should_close():
                self._tick()
        except KeyboardInterrupt:
            log.info("[PlayerRuntime] Interrupted by user")
        finally:
            _active_runtime = previous_runtime
            self.shutdown()

    def _tick(self):
        """Single frame update."""
        current_time = time.perf_counter()
        self.delta_time = current_time - self.last_time
        self.last_time = current_time

        if self.window is not None:
            self.window.poll_events()
            self._sync_surface_size()

        if self._mcp_executor is not None:
            self._mcp_executor.process_pending()

        # Update scene
        if self.scene is not None:
            self.scene.update(self.delta_time)
            self.scene.before_render()

        # Render
        self._render()

        # Frame rate limiting
        frame_time = time.perf_counter() - current_time
        target_time = 1.0 / self.target_fps
        if frame_time < target_time:
            time.sleep(target_time - frame_time)

    def _render(self):
        """Render using RenderingManager."""
        manager = self._engine.rendering_manager
        manager.render_all(present=True)
        if self.window is not None and self._display is not None:
            self.window.present(self._display.color_tex)

    def _sync_surface_size(self) -> None:
        """Resize the offscreen display surface to match the window."""
        from tcbase import log

        if self.window is None or self._display is None:
            return

        width, height = self.window.framebuffer_size()
        if width <= 0 or height <= 0:
            return
        if (width, height) == self._surface_size:
            return

        try:
            self._display.resize(width, height)
            self._display.update_all_pixel_rects()
            self._surface_size = (width, height)
        except Exception as e:
            log.error(f"[PlayerRuntime] Failed to resize render surface: {e}")

    def shutdown(self):
        """Clean up resources."""
        from tcbase import log

        log.info("[PlayerRuntime] Shutting down")

        if self._mcp_server is not None:
            self._mcp_server.stop()
            self._mcp_server = None
        self._mcp_executor = None

        if self._pipeline_reload_binding is not None:
            try:
                self._pipeline_reload_binding.close()
            except Exception as e:
                log.error(f"[PlayerRuntime] Failed to close pipeline reload binding: {e}")
            self._pipeline_reload_binding = None

        # Remove display from manager
        manager = None
        if self._engine is not None or self.scene is not None or self._display is not None:
            try:
                manager = self._engine.rendering_manager
            except Exception as e:
                log.error(f"[PlayerRuntime] Failed to access RenderingManager during shutdown: {e}")

        if manager is not None:
            manager.set_display_factory(lambda name: None)
            if self.scene is not None:
                manager.detach_scene_full(self.scene)
                self._fallback_render_target = None
                self._viewport = None

            if self._display is not None:
                manager.remove_display(self._display)

        if self.window is not None:
            self.window.set_input_display(0xFFFFFFFF, 0)
        if self._input_manager is not None:
            self._input_manager.close()
            self._input_manager = None

        if self._display is not None:
            self._display.destroy()
            self._display = None
        self.graphics = None

        try:
            from termin.bootstrap import shutdown_player

            shutdown_player()
        except Exception as e:
            log.error(f"[PlayerRuntime] Failed to shutdown bootstrap runtime: {e}")

        self.scene = None

        if self.window is not None:
            self.window.close()
            self.window = None

        if self._graphics_session is not None:
            try:
                self._graphics_session.close()
            except Exception as e:
                log.error(f"[PlayerRuntime] Failed to close graphics runtime: {e}")
            self._graphics_session = None
            try:
                from termin.display import quit_sdl

                quit_sdl()
            except Exception as e:
                log.error(f"[PlayerRuntime] Failed to quit SDL: {e}")

        # Release a borrowed wrapper only after all engine-backed resources are
        # detached. For standalone runtimes this also destroys the owned engine.
        self._engine = None
        self._resource_manager = None

        self.running = False

    def request_quit(self, exit_code: int = 0) -> None:
        """Request graceful shutdown at the next game loop boundary."""
        self.exit_code = int(exit_code)
        self.running = False
        if self.window is not None:
            self.window.set_should_close(True)


def run_project(
    project_path: str | Path,
    scene_name: str,
    width: int | None = None,
    height: int | None = None,
    title: str = "Termin Player",
    fullscreen: bool | None = None,
    mcp_enabled: bool = False,
    mcp_options: dict | None = None,
):
    """
    Run a project in standalone player mode.

    Args:
        project_path: Path to project directory
        scene_name: Scene filename to load (e.g., "main.scene")
        width: Window width
        height: Window height
        title: Window title
        fullscreen: Enable borderless desktop fullscreen after window creation
    """
    runtime = PlayerRuntime(
        project_path=project_path,
        scene_name=scene_name,
        width=width,
        height=height,
        title=title,
        fullscreen=fullscreen,
        mcp_enabled=mcp_enabled,
        mcp_options=mcp_options,
    )
    runtime.run()
