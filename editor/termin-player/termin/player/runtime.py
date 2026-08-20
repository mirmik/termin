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
    close_project_modules,
    create_project_world_controller,
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
    from termin.display.window import PresentationMode

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

        self.running = False
        self.scene: Scene | None = None
        self.window = None
        self._graphics_session = None
        self.graphics = None
        self._engine = engine
        self._owns_engine = engine is None
        self._project_modules_runtime = None
        self._session_started = False
        self._bootstrap_started = False
        self._surface_size: tuple[int, int] = (0, 0)

        # Timing
        self.target_fps = 60
        self.delta_time = 1.0 / self.target_fps
        self.last_time = 0.0

        # Display/Input (managed via RenderingManager)
        self._display = None
        self._viewport = None
        self._viewports = []
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
    def camera(self):
        """Return the camera of the currently presented primary viewport."""
        viewport = self._viewport
        if viewport is None:
            return None
        render_target = viewport.render_target
        if render_target is None:
            return None
        return render_target.camera

    @property
    def resource_manager(self):
        return self._resource_manager

    @property
    def rendering_manager(self):
        if self._engine is None:
            raise RuntimeError("PlayerRuntime has no initialized EngineCore")
        return self._engine.rendering_manager

    def initialize(self) -> bool:
        """Initialize transactionally and release every acquired runtime layer on failure."""
        from tcbase import log

        try:
            return self._initialize()
        except Exception as error:
            log.error(f"[PlayerRuntime] Unexpected initialization failure: {error}")
            self.shutdown()
            return False

    def _initialize(self) -> bool:
        """Initialize player systems."""
        from tcbase import log
        from termin.bootstrap import bootstrap_player

        bootstrap_player()
        self._bootstrap_started = True
        from termin.render import configure_project_render_phases
        configure_project_render_phases(self.render_phase_names)
        self._configure_backend_default()

        # Load the app render bindings before resource preloaders touch
        # materials/shaders. Importing tgfx-only helpers first leaves some
        # build materials in a state where the runtime pipeline clears but
        # draws no scene geometry.
        self._ensure_texture_registry()

        if not self._ensure_engine_core():
            self.shutdown()
            return False
        if not self._configure_shader_runtime():
            self.shutdown()
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
        try:
            self._start_project_session()
        except Exception as error:
            log.error(f"[PlayerRuntime] Failed to start project runtime session: {error}")
            self.shutdown()
            return False

        self._scan_project_assets()

        # Create default pipeline and configure RenderingManager
        manager = self._engine.rendering_manager
        pipeline = manager.create_pipeline("Default")
        log.info(f"[PlayerRuntime] Created pipeline: {pipeline.name} with {len(pipeline.passes)} passes")

        manager.set_pipeline_factory(self._create_pipeline_for_name)

        # Create one host-owned graphics runtime before its presentation
        # window. RenderEngine reuses this device instead of creating a second
        # device with incompatible texture handles.
        from termin.display.window import WindowedGraphicsSession

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
            self.shutdown()
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
            self.shutdown()
            return False

        import json
        from termin.engine import default_scene_extensions, scene as engine_scene

        with open(scene_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Register and bind the empty scene before deserialization so component
        # construction can resolve the active WorldContext and controller.
        scene_key = engine_scene.SceneKey(self.scene_name, engine_scene.SceneRole.RUNTIME)
        self.scene = self._engine.scene_manager.create_scene(
            scene_key,
            default_scene_extensions(),
        )
        if self.scene is None:
            log.error(f"[PlayerRuntime] Failed to create scene: {self.scene_name}")
            self.shutdown()
            return False
        if not self._engine.bind_runtime_scene(self.scene):
            log.error(f"[PlayerRuntime] Failed to bind scene to RuntimeSession: {self.scene_name}")
            self._engine.scene_manager.close_scene(self.scene)
            self.scene = None
            self.shutdown()
            return False
        self.scene.source_path = str(scene_path.resolve())
        scene_data = data.get("scene")
        if scene_data is None:
            scenes = data.get("scenes")
            if isinstance(scenes, list) and len(scenes) > 0:
                scene_data = scenes[0]
        if scene_data is None and ("entities" in data or "uuid" in data):
            scene_data = data
        try:
            if scene_data:
                from termin.glb_adapters.scene_animation_repair import repair_glb_animation_player_clip_refs

                repair_glb_animation_player_clip_refs(scene_data)
                self.scene.load_from_data(scene_data, context=None, update_settings=True)
                from termin.project_modules.runtime import upgrade_scene_unknown_components
                upgraded = upgrade_scene_unknown_components(self.scene)
                if upgraded > 0:
                    log.info(f"[PlayerRuntime] Upgraded {upgraded} unknown component(s)")
        except Exception as error:
            log.error(f"[PlayerRuntime] Failed to deserialize scene {self.scene_name}: {error}")
            self.shutdown()
            return False

        log.info(f"[PlayerRuntime] Scene loaded: {self.scene_name}")

        if not self._activate_primary_scene(manager):
            self.shutdown()
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

    def _activate_primary_scene(self, manager) -> bool:
        """Commit the initial renderable scene through EngineCore RuntimeSession."""
        from tcbase import log
        from termin.engine import require_world_context

        if self.scene is None:
            log.error("[PlayerRuntime] Cannot activate a missing scene")
            return False
        context = require_world_context(self.scene, "PlayerRuntime initial scene")
        if not context.transition_to(self.scene_name):
            log.error("[PlayerRuntime] RuntimeSession rejected the initial primary scene request")
            return False
        self._engine.tick_and_render(0.0)

        primary = context.primary_scene
        primary_handle = primary.scene_handle() if primary is not None else None
        scene_handle = self.scene.scene_handle()
        if (
            primary_handle is None
            or primary_handle.index != scene_handle.index
            or primary_handle.generation != scene_handle.generation
        ):
            log.error(
                "[PlayerRuntime] Initial scene has no attachable render topology; "
                "source player requires a saved runtime viewport configuration"
            )
            return False
        viewports = list(manager.topology.viewports(self.scene))
        if not viewports:
            log.error("[PlayerRuntime] Primary scene committed without a viewport")
            return False
        self._viewports = viewports
        self._viewport = viewports[0]
        self._disable_unrenderable_unused_render_targets(manager, viewports)
        log.info(f"[PlayerRuntime] Activated primary scene with {len(viewports)} viewport(s)")
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

    def _load_modules(self):
        """Load all project modules through termin-modules runtime."""
        return load_project_modules(
            self.project_path,
            log_prefix="[PlayerRuntime]",
            scene_manager=self._engine.scene_manager,
        )

    def _start_project_session(self) -> None:
        """Publish project modules, create the selected controller and transfer it."""
        self._project_modules_runtime = self._load_modules()
        controller = create_project_world_controller(
            self.project_path,
            log_prefix="[PlayerRuntime]",
        )
        if not self._engine.begin_session(controller):
            raise RuntimeError("EngineCore refused to start RuntimeSession")
        self._session_started = True

    def _scan_project_assets(self):
        """Scan project directory for assets and register them."""
        scan_project_assets(self.project_path, log_prefix="[PlayerRuntime]")

    def _setup_input(self):
        """Set up input handling."""
        from tcbase import log
        from termin.display import BasicDisplayInputManager
        from termin.display.window import attach_window_input_display

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
            attach_window_input_display(self.window, *self._display.handle)

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

        if self._engine is not None:
            self._engine.tick_and_render(self.delta_time)
        self._present()

        # Frame rate limiting
        frame_time = time.perf_counter() - current_time
        target_time = 1.0 / self.target_fps
        if frame_time < target_time:
            time.sleep(target_time - frame_time)

    def _present(self):
        """Present the display rendered by EngineCore."""
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

        if self._mcp_executor is not None:
            self._mcp_executor.close()
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

        manager = None
        if self._engine is not None:
            try:
                manager = self._engine.rendering_manager
            except Exception as e:
                log.error(f"[PlayerRuntime] Failed to access RenderingManager during shutdown: {e}")

        if self._session_started and self._engine is not None:
            if not self._engine.end_session():
                log.error("[PlayerRuntime] RuntimeSession shutdown reported lifecycle failures")
            self._session_started = False

        if manager is not None:
            manager.set_display_factory(lambda name: None)
            if self.scene is not None and manager.topology.is_attached(self.scene):
                manager.detach_scene_full(self.scene)
            self._viewport = None
            self._viewports = []

            if self._display is not None:
                manager.remove_display(self._display)

        if self.window is not None:
            from termin.display.window import attach_window_input_display

            attach_window_input_display(self.window, 0xFFFFFFFF, 0)
        if self._input_manager is not None:
            self._input_manager.close()
            self._input_manager = None

        if self._display is not None:
            self._display.destroy()
            self._display = None
        self.graphics = None

        if self._engine is not None and self.scene is not None and self.scene.is_alive():
            self._engine.scene_manager.close_scene(self.scene)
        self.scene = None

        if self._owns_engine and self._engine is not None:
            if not self._engine.shutdown():
                log.error("[PlayerRuntime] EngineCore shutdown reported lifecycle failures")

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
                from termin.display.window import quit_sdl

                quit_sdl()
            except Exception as e:
                log.error(f"[PlayerRuntime] Failed to quit SDL: {e}")

        close_project_modules(
            self._project_modules_runtime,
            log_prefix="[PlayerRuntime]",
        )
        self._project_modules_runtime = None

        if self._bootstrap_started:
            try:
                from termin.bootstrap import shutdown_player

                shutdown_player()
            except Exception as e:
                log.error(f"[PlayerRuntime] Failed to shutdown bootstrap runtime: {e}")
            self._bootstrap_started = False

        # Release a borrowed wrapper only after all runtime-owned objects are gone.
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
