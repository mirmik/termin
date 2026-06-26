"""
Minimal game runtime for standalone player.
"""

from __future__ import annotations

import time
import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from termin.player.project_runtime_support import (
    create_asset_import_plugin_map,
    create_build_import_registry,
    load_project_modules,
    register_project_runtime_resources,
    scan_project_assets,
)

if TYPE_CHECKING:
    from termin_assets import AssetTypeRegistry
    from termin.project.settings import ProjectPlayerWindowSettings
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
    configured: "ProjectPlayerWindowSettings | None",
    width: int | None,
    height: int | None,
    fullscreen: bool | None,
):
    from termin.project.settings import ProjectPlayerWindowSettings

    base = configured if configured is not None else _load_project_player_window_settings(project_path)
    return ProjectPlayerWindowSettings(
        width=_resolve_positive_window_int(width, base.width, "width"),
        height=_resolve_positive_window_int(height, base.height, "height"),
        fullscreen=_resolve_window_bool(fullscreen, base.fullscreen, "fullscreen"),
    )


def _load_project_player_window_settings(project_path: Path):
    from tcbase import log
    from termin.project.settings import ProjectSettings

    settings_path = project_path / "project_settings" / "project.json"
    if not settings_path.exists():
        return ProjectSettings().player_window

    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        log.error(f"[PlayerRuntime] Failed to read project settings: {exc}")
        return ProjectSettings().player_window

    if not isinstance(data, dict):
        log.error("[PlayerRuntime] Project settings root must be an object")
        return ProjectSettings().player_window
    return ProjectSettings.from_dict(data).player_window


def _player_window_from_manifest(data: dict, manifest_path: Path):
    from tcbase import log
    from termin.project.settings import ProjectPlayerWindowSettings

    runtime = data.get("runtime")
    if runtime is None:
        return None
    if not isinstance(runtime, dict):
        log.error(f"[PlayerRuntime] Manifest runtime field must be an object: {manifest_path}")
        return None

    window = runtime.get("window")
    if window is None:
        return None
    return ProjectPlayerWindowSettings.from_dict(window)


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

def load_manifest_assets_with_import_plugins(
    project_path: Path,
    resources: list,
    resource_manager: object,
    import_registry: "AssetTypeRegistry",
) -> int:
    """Load plugin-backed build manifest assets without editor_core preloaders."""
    from tcbase import log

    pending = []
    for resource in resources:
        if not isinstance(resource, dict):
            continue
        if resource.get("kind") != "asset":
            continue

        resource_type = resource.get("type")
        if not isinstance(resource_type, str) or resource_type == "":
            log.warning("[PlayerRuntime] Build asset has no valid type")
            continue

        plugin = import_registry.get_import(resource_type)
        if plugin is None:
            if resource_type != "scene":
                log.warning(f"[PlayerRuntime] Build asset type is not plugin-backed yet: {resource_type}")
            continue

        build_path = resource.get("build_path")
        if not isinstance(build_path, str) or build_path == "":
            log.warning(f"[PlayerRuntime] Build asset has no build_path: {resource_type}")
            continue

        path = project_path / build_path
        pending.append((plugin.priority, str(path), plugin))

    pending.sort(key=lambda item: (item[0], item[1]))

    loaded_count = 0
    for _priority, path, plugin in pending:
        asset_path = Path(path)
        if not asset_path.exists():
            log.error(f"[PlayerRuntime] Build asset not found: {asset_path}")
            continue
        try:
            result = plugin.preload(str(asset_path))
            if result is not None:
                log.info(f"[PlayerRuntime] Loading build {result.resource_type}: {asset_path.name}")
                resource_manager.register_file(result)
                loaded_count += 1
        except Exception as e:
            log.error(f"[PlayerRuntime] Failed to load build asset {asset_path}: {e}")

    return loaded_count


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
        asset_manifest_path: str | Path | None = None,
        build_json_path: str | Path | None = None,
        mcp_enabled: bool = False,
        mcp_options: dict | None = None,
        player_window: "ProjectPlayerWindowSettings | None" = None,
    ):
        self.project_path = Path(project_path)
        self.scene_name = scene_name
        window_settings = _resolve_player_window_settings(
            self.project_path,
            configured=player_window,
            width=width,
            height=height,
            fullscreen=fullscreen,
        )
        self.width = window_settings.width
        self.height = window_settings.height
        self.title = title
        self.fullscreen = window_settings.fullscreen
        self.asset_manifest_path = Path(asset_manifest_path) if asset_manifest_path is not None else None
        self.build_json_path = Path(build_json_path) if build_json_path is not None else None
        self.mcp_enabled = bool(mcp_enabled)
        self.mcp_options = mcp_options if mcp_options is not None else {}
        self._scene_file_data = None

        self.running = False
        self.scene: Scene | None = None
        self.window = None
        self.graphics = None
        self.surface = None
        self.camera = None
        self._engine = None
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
        self.exit_code = 0

    @property
    def display(self):
        return self._display

    @property
    def viewport(self):
        return self._viewport

    def initialize(self) -> bool:
        """Initialize player systems."""
        from tcbase import log
        from termin.bootstrap import bootstrap_player

        bootstrap_player()
        self._configure_backend_default()
        if not self._configure_shader_runtime():
            return False

        # Load the app render bindings before resource preloaders touch
        # materials/shaders. Importing tgfx-only helpers first leaves some
        # build materials in a state where the runtime pipeline clears but
        # draws no scene geometry.
        from termin.engine import RenderingManager

        self._ensure_texture_registry()

        if not self._ensure_engine_core():
            return False

        if self.build_json_path is not None:
            log.info(f"[PlayerRuntime] Initializing build: {self.build_json_path}")
        else:
            log.info(f"[PlayerRuntime] Initializing project: {self.project_path}")

        # Register components
        self._register_components()

        # Load C++ modules
        self._load_modules()

        if self.asset_manifest_path is not None:
            self._load_manifest_assets()
        else:
            self._scan_project_assets()

        # Ensure GLSL fallback loader is set up for app ResourceManager includes.
        from termin.shader_runtime import configure_glsl_preprocessor_fallback

        configure_glsl_preprocessor_fallback()

        # Create default pipeline and configure RenderingManager
        pipeline = RenderingManager.instance().create_pipeline("Default")
        log.info(f"[PlayerRuntime] Created pipeline: {pipeline.name} with {len(pipeline.passes)} passes")

        manager = RenderingManager.instance()
        manager.set_pipeline_factory(self._create_pipeline_for_name)

        # Create native backend window first. Its constructor publishes the
        # host tgfx2 device so RenderEngine reuses it instead of creating a
        # second device with incompatible texture handles.
        from termin.display._platform_native import SDLBackendWindow
        from termin.display import FBOSurface

        try:
            self.window = SDLBackendWindow(self.title, self.width, self.height)
            if self.fullscreen:
                self.window.set_fullscreen(True)
        except Exception as e:
            log.error(f"[PlayerRuntime] Failed to create backend window: {e}")
            return False

        # Create display
        from termin.display import Display

        self._surface_size = self.window.framebuffer_size()
        surface_width, surface_height = self._surface_size
        self.surface = FBOSurface(self.window.device(), surface_width, surface_height)
        self._display = Display(surface=self.surface, name="Main")
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
            self.scene.load_from_data(scene_data, context=None, update_settings=True)
            from termin.modules import upgrade_scene_unknown_components
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

        from termin.default_assets.resource_manager import DefaultResourceManager

        rm = DefaultResourceManager.instance()
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
        """Use the project-wide primary graphics backend unless overridden."""
        from tcbase import log

        if "TERMIN_BACKEND" in os.environ:
            log.info(f"[PlayerRuntime] Using TERMIN_BACKEND={os.environ['TERMIN_BACKEND']}")
            return

        default_backend = "d3d11" if sys.platform == "win32" else "vulkan"
        os.environ["TERMIN_BACKEND"] = default_backend
        log.info(
            f"[PlayerRuntime] TERMIN_BACKEND not set; using {default_backend} for standalone player"
        )

    def _configure_build_shader_runtime(self) -> None:
        """Make build.json runs consume prebuilt shader artifacts from the build."""
        if self.build_json_path is None or self.asset_manifest_path is None:
            return

        from tcbase import log

        manifest_path = self.asset_manifest_path
        if not manifest_path.is_absolute():
            manifest_path = self.project_path / manifest_path
        artifact_root = manifest_path.parent
        cache_root = self.project_path / ".build" / "shader-cache"
        try:
            cache_root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            log.error(f"[PlayerRuntime] Failed to create build shader cache: {exc}")
            return

        os.environ["TERMIN_SHADER_ARTIFACT_ROOT"] = str(artifact_root)
        os.environ["TERMIN_SHADER_CACHE_ROOT"] = str(cache_root)
        os.environ["TERMIN_SHADER_DEV_COMPILE"] = "0"

        try:
            import tgfx

            tgfx.configure_shader_runtime(
                artifact_root=str(artifact_root),
                cache_root=str(cache_root),
                shader_compiler=os.environ.get("TERMIN_SHADERC", ""),
                dev_compile=False,
            )
        except Exception as exc:
            log.error(f"[PlayerRuntime] Failed to configure build shader runtime: {exc}")
            return

        log.info(
            "[PlayerRuntime] Build shader runtime configured: "
            f"artifact_root='{artifact_root}' cache_root='{cache_root}' dev_compile=False"
        )

    def _configure_shader_runtime(self) -> bool:
        """Configure shader artifacts for source-project or packaged execution."""
        if self.build_json_path is not None or self.asset_manifest_path is not None:
            self._configure_build_shader_runtime()
            return True

        from termin.shader_runtime import configure_project_shader_runtime

        return configure_project_shader_runtime(self.project_path, label="source player")

    def _ensure_texture_registry(self) -> None:
        """Load the tgfx texture registry before app-native modules."""
        from tgfx import tc_texture_count

        tc_texture_count()

    def _ensure_engine_core(self) -> bool:
        """Ensure EngineCore exists so RenderingManager has a real backend."""
        from tcbase import log
        from termin.engine import EngineCore

        engine = EngineCore.instance()
        if engine is not None:
            self._engine = engine
            return True

        try:
            from termin.engine import register_default_scene_extensions

            register_default_scene_extensions()
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
        load_project_modules(self.project_path, log_prefix="[PlayerRuntime]")

    def _create_build_import_registry(self) -> "AssetTypeRegistry":
        return create_build_import_registry()

    def _create_asset_import_plugin_map(self):
        return create_asset_import_plugin_map()

    def _scan_project_assets(self):
        """Scan project directory for assets and register them."""
        scan_project_assets(self.project_path, log_prefix="[PlayerRuntime]")

    def _load_manifest_assets(self) -> None:
        """Load build resources listed by manifest.json."""
        from tcbase import log
        from termin.default_assets.resource_manager import DefaultResourceManager

        if self.asset_manifest_path is None:
            log.error("[PlayerRuntime] No asset manifest path set")
            return

        manifest_path = self.asset_manifest_path
        if not manifest_path.is_absolute():
            manifest_path = self.project_path / manifest_path

        if not manifest_path.exists():
            log.error(f"[PlayerRuntime] Asset manifest not found: {manifest_path}")
            return

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)
        except Exception as e:
            log.error(f"[PlayerRuntime] Failed to read asset manifest {manifest_path}: {e}")
            return

        resources = manifest_data.get("resources")
        if not isinstance(resources, list):
            log.error(f"[PlayerRuntime] Invalid asset manifest resources: {manifest_path}")
            return

        if self._is_runtime_package_manifest(resources):
            from termin.player.runtime_package_loader import load_runtime_package_assets

            load_runtime_package_assets(manifest_path.parent, manifest_path)
            return

        for diagnostic in manifest_data.get("diagnostics", []):
            if not isinstance(diagnostic, dict):
                continue
            level = diagnostic.get("level")
            path = diagnostic.get("path")
            message = diagnostic.get("message")
            log.warning(f"[PlayerRuntime] Build diagnostic {level}: {path}: {message}")

        rm = DefaultResourceManager.instance()
        import_registry = self._create_build_import_registry()
        loaded_count = load_manifest_assets_with_import_plugins(
            project_path=self.project_path,
            resources=resources,
            resource_manager=rm,
            import_registry=import_registry,
        )

        log.info(f"[PlayerRuntime] Loaded {loaded_count} build assets from manifest")

    def _is_runtime_package_manifest(self, resources: list) -> bool:
        for resource in resources:
            if not isinstance(resource, dict):
                continue
            if resource.get("kind") == "asset":
                return False
            resource_type = resource.get("type")
            if resource_type in {"shader", "mesh", "material", "pipeline", "foliage_data"}:
                return True
        return False

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

        input_manager = BasicDisplayInputManager(self._display.tc_display_ptr)
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
            self.window.set_input_manager(input_manager.tc_input_manager_ptr)
        if self.surface is not None:
            self.surface.set_input_manager(input_manager.tc_input_manager_ptr)

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
        from termin.engine import RenderingManager

        manager = RenderingManager.instance()
        manager.render_all(present=True)
        if self.window is not None and self.surface is not None:
            self.window.present(self.surface.color_tex)

    def _sync_surface_size(self) -> None:
        """Resize the offscreen display surface to match the window."""
        from tcbase import log

        if self.window is None or self.surface is None or self._display is None:
            return

        width, height = self.window.framebuffer_size()
        if width <= 0 or height <= 0:
            return
        if (width, height) == self._surface_size:
            return

        try:
            self.surface.resize(width, height)
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

        # Remove display from manager
        manager = None
        if self._engine is not None or self.scene is not None or self._display is not None:
            try:
                from termin.engine import RenderingManager

                manager = RenderingManager.instance()
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

        if self._display is not None:
            self._display.destroy()
            self._display = None

        try:
            from termin.bootstrap import shutdown_player

            shutdown_player()
        except Exception as e:
            log.error(f"[PlayerRuntime] Failed to shutdown bootstrap runtime: {e}")

        self.scene = None
        self._engine = None

        if self.surface is not None:
            self.surface.close()
            self.surface = None

        if self.window is not None:
            self.window.close()
            self.window = None

        self.running = False

    def request_quit(self, exit_code: int = 0) -> None:
        """Request graceful shutdown at the next game loop boundary."""
        from tcbase import log

        self.exit_code = int(exit_code)
        self.running = False
        if self.window is not None:
            self.window.set_should_close(True)
        if self._display is not None:
            try:
                self._display.should_close = True
            except Exception as e:
                log.error(f"[PlayerRuntime] Failed to mark display closed: {e}")


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


def run_build(
    build_json_path: str | Path,
    width: int | None = None,
    height: int | None = None,
    title: str = "Termin Player",
    fullscreen: bool | None = None,
    mcp_enabled: bool = False,
    mcp_options: dict | None = None,
):
    """
    Run a built project from build.json.

    Args:
        build_json_path: Path to build.json produced by termin.project_builder
        width: Window width
        height: Window height
        title: Window title
        fullscreen: Enable borderless desktop fullscreen after window creation
    """
    build_path = Path(build_json_path).resolve()
    with open(build_path, "r", encoding="utf-8") as f:
        build_data = json.load(f)

    entry_scene = build_data.get("entry_scene")
    asset_manifest = build_data.get("asset_manifest")
    if not isinstance(entry_scene, str) or entry_scene == "":
        raise ValueError(f"build.json has no entry_scene: {build_path}")
    if not isinstance(asset_manifest, str) or asset_manifest == "":
        raise ValueError(f"build.json has no asset_manifest: {build_path}")

    runtime = PlayerRuntime(
        project_path=build_path.parent,
        scene_name=entry_scene,
        width=width,
        height=height,
        title=title,
        fullscreen=fullscreen,
        asset_manifest_path=asset_manifest,
        build_json_path=build_path,
        player_window=_player_window_from_manifest(build_data, build_path),
        mcp_enabled=mcp_enabled,
        mcp_options=mcp_options,
    )
    runtime.run()


def run_bundle(
    app_manifest_path: str | Path,
    width: int | None = None,
    height: int | None = None,
    title: str = "Termin Player",
    fullscreen: bool | None = None,
    mcp_enabled: bool = False,
    mcp_options: dict | None = None,
):
    """Run a packaged desktop bundle from app.json."""
    app_path = Path(app_manifest_path).resolve()
    with open(app_path, "r", encoding="utf-8") as f:
        app_data = json.load(f)

    package = app_data.get("package")
    entry = app_data.get("entry")
    if not isinstance(package, dict):
        raise ValueError(f"app.json has no package object: {app_path}")
    if not isinstance(entry, dict):
        raise ValueError(f"app.json has no entry object: {app_path}")

    runtime_manifest = app_data.get("runtime")
    manifest_mcp_options: dict = {}
    if isinstance(runtime_manifest, dict):
        mcp_value = runtime_manifest.get("mcp")
        if isinstance(mcp_value, dict):
            manifest_mcp_options.update(mcp_value)
    if mcp_options is not None:
        manifest_mcp_options.update(mcp_options)

    package_root_value = package.get("root")
    package_manifest_value = package.get("manifest")
    entry_scene_value = entry.get("scene")
    if not isinstance(package_root_value, str) or package_root_value == "":
        raise ValueError(f"app.json has no package.root: {app_path}")
    if not isinstance(package_manifest_value, str) or package_manifest_value == "":
        raise ValueError(f"app.json has no package.manifest: {app_path}")
    if not isinstance(entry_scene_value, str) or entry_scene_value == "":
        raise ValueError(f"app.json has no entry.scene: {app_path}")

    bundle_root = app_path.parent
    package_root = (bundle_root / package_root_value).resolve()
    manifest_path = (bundle_root / package_manifest_value).resolve()
    scene_path = (bundle_root / entry_scene_value).resolve()
    scene_name = scene_path.relative_to(package_root).as_posix()

    runtime = PlayerRuntime(
        project_path=package_root,
        scene_name=scene_name,
        width=width,
        height=height,
        title=title,
        fullscreen=fullscreen,
        asset_manifest_path=manifest_path,
        build_json_path=app_path,
        player_window=_player_window_from_manifest(app_data, app_path),
        mcp_enabled=mcp_enabled,
        mcp_options=manifest_mcp_options,
    )
    runtime.run()
