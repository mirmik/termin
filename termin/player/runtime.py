"""
Minimal game runtime for standalone player.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene


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
        width: int = 1280,
        height: int = 720,
        title: str = "Termin Player",
    ):
        self.project_path = Path(project_path)
        self.scene_name = scene_name
        self.width = width
        self.height = height
        self.title = title

        self.running = False
        self.scene: Scene | None = None
        self.window = None
        self.graphics = None
        self.surface = None
        self.camera = None

        # Timing
        self.target_fps = 60
        self.delta_time = 1.0 / self.target_fps
        self.last_time = 0.0

        # Display/Input (managed via RenderingManager)
        self._display = None
        self._viewport = None
        self._input_manager = None

    def initialize(self) -> bool:
        """Initialize player systems."""
        from termin._native import log

        log.info(f"[PlayerRuntime] Initializing project: {self.project_path}")

        # Register components
        self._register_components()

        # Load C++ modules
        self._load_modules()

        # Scan project assets
        self._scan_project_assets()

        # Ensure GLSL fallback loader is set up (import triggers setup)
        import termin.visualization.render.glsl_preprocessor  # noqa: F401

        # Create default pipeline and configure RenderingManager
        from termin.visualization.core.viewport import make_default_pipeline
        from termin.visualization.render import RenderingManager

        pipeline = make_default_pipeline()
        log.info(f"[PlayerRuntime] Created pipeline: {pipeline.name} with {len(pipeline.passes)} passes")

        manager = RenderingManager.instance()
        manager.set_default_pipeline(pipeline)

        # Create graphics backend
        from termin.graphics import OpenGLGraphicsBackend
        self.graphics = OpenGLGraphicsBackend()
        manager.set_graphics(self.graphics)

        # Create window
        from termin.visualization.platform.backends.glfw import GLFWWindowHandle
        self.window = GLFWWindowHandle(
            self.width, self.height, self.title,
            graphics=self.graphics,
        )

        # Create render surface and display
        from termin.visualization.render.surface import WindowRenderSurface
        from termin.visualization.core.display import Display

        self.surface = WindowRenderSurface(self.window)
        self._display = Display(self.surface)
        manager.add_display(self._display, "Main")

        # Load scene
        scene_path = self.project_path / self.scene_name
        if not scene_path.exists():
            log.error(f"[PlayerRuntime] Scene not found: {scene_path}")
            return False

        import json
        from termin.visualization.core.scene import Scene

        with open(scene_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Create new scene and load data
        self.scene = Scene(name=self.scene_name)
        scene_data = data.get("scene") or (data.get("scenes", [None])[0])
        if scene_data:
            self.scene.load_from_data(scene_data, context=None, update_settings=True)

        log.info(f"[PlayerRuntime] Scene loaded: {self.scene_name}")

        # Find or create camera
        self._setup_camera()

        # Mount scene to display
        self._viewport = manager.mount_scene(
            scene=self.scene,
            display=self._display,
            camera=self.camera,
        )

        # Set up input handling
        self._setup_input()

        log.info("[PlayerRuntime] Initialization complete")
        return True

    def _register_components(self):
        """Register builtin components and resources."""
        from termin.assets.resources import ResourceManager
        rm = ResourceManager.instance()
        rm.register_builtin_components()
        rm.register_builtin_materials()
        rm.register_builtin_meshes()
        rm.register_builtin_frame_passes()
        rm.register_builtin_post_effects()

    def _load_modules(self) -> None:
        """Load all C++ modules from the project directory."""
        from termin._native import log
        from termin.editor.module_scanner import ModuleScanner

        def on_loaded(name: str, success: bool, error: str) -> None:
            if success:
                log.info(f"[PlayerRuntime] Loaded module: {name}")
            else:
                log.error(f"[PlayerRuntime] Failed to load module {name}: {error}")

        scanner = ModuleScanner(on_module_loaded=on_loaded)
        loaded, failed = scanner.scan_and_load(str(self.project_path))

        log.info(f"[PlayerRuntime] Modules: {loaded} loaded, {failed} failed")

    def _scan_project_assets(self):
        """Scan project directory for assets and register them."""
        import os
        from termin._native import log
        from termin.assets.resources import ResourceManager

        rm = ResourceManager.instance()

        # Create pre-loaders
        from termin.editor.file_processors import (
            MaterialPreLoader,
            ShaderFileProcessor,
            TextureFileProcessor,
            ComponentFileProcessor,
            MeshFileProcessor,
            GLBPreLoader,
            PrefabPreLoader,
            AudioPreLoader,
            GlslPreLoader,
            NavMeshProcessor,
            VoxelGridProcessor,
        )

        preloaders = [
            GlslPreLoader(rm),
            ShaderFileProcessor(rm),
            TextureFileProcessor(rm),
            MaterialPreLoader(rm),
            ComponentFileProcessor(rm),
            MeshFileProcessor(rm),
            GLBPreLoader(rm),
            PrefabPreLoader(rm),
            AudioPreLoader(rm),
            NavMeshProcessor(rm),
            VoxelGridProcessor(rm),
        ]

        # Build extension -> preloader map
        ext_map = {}
        for pl in preloaders:
            for ext in pl.extensions:
                ext_map[ext] = pl

        # Collect files sorted by priority
        pending = []  # (priority, path, preloader)
        for root, dirs, files in os.walk(self.project_path):
            dirs[:] = [d for d in dirs if not d.startswith((".", "__"))]
            for filename in files:
                if filename.startswith("."):
                    continue
                ext = os.path.splitext(filename)[1].lower()
                if ext in ext_map:
                    pl = ext_map[ext]
                    path = os.path.join(root, filename)
                    pending.append((pl.priority, path, pl))

        # Sort by priority
        pending.sort(key=lambda x: (x[0], x[1]))

        # Process files
        loaded_count = 0
        for _priority, path, pl in pending:
            try:
                result = pl.preload(path)
                if result is not None:
                    log.info(f"[PlayerRuntime] Loading {result.resource_type}: {os.path.basename(path)}")
                    rm.register_file(result)
                    loaded_count += 1
            except Exception as e:
                log.error(f"[PlayerRuntime] Failed to load {path}: {e}")

        log.info(f"[PlayerRuntime] Loaded {loaded_count} project assets")

    def _setup_camera(self):
        """Find existing camera or create default one."""
        from termin._native import log
        from termin.visualization.core.camera import CameraComponent

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

        # Position camera
        camera_entity.transform.set_local_position(0, 2, 5)
        log.info("[PlayerRuntime] Created default camera at (0, 2, 5)")

    def _setup_input(self):
        """Set up input handling."""
        from termin.visualization.platform.input_manager import SimpleDisplayInputManager

        self._input_manager = SimpleDisplayInputManager(self._display.tc_display_ptr)

        # Connect input manager to surface
        surface = self._display.surface
        if hasattr(surface, "set_input_manager"):
            surface.set_input_manager(self._input_manager.tc_input_manager_ptr)

    def run(self):
        """Run the game loop."""
        from termin._native import log

        if not self.initialize():
            log.error("[PlayerRuntime] Initialization failed")
            return

        log.info("[PlayerRuntime] Starting game loop")
        self.running = True
        self.last_time = time.perf_counter()

        try:
            while self.running and not self.window.should_close():
                self._tick()
        except KeyboardInterrupt:
            log.info("[PlayerRuntime] Interrupted by user")
        finally:
            self.shutdown()

    def _tick(self):
        """Single frame update."""
        import glfw

        # Calculate delta time
        current_time = time.perf_counter()
        self.delta_time = current_time - self.last_time
        self.last_time = current_time

        # Process window events
        glfw.poll_events()

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
        from termin.visualization.render import RenderingManager

        manager = RenderingManager.instance()
        manager.render_display(self._display, present=True)

    def shutdown(self):
        """Clean up resources."""
        import glfw
        from termin._native import log
        from termin.visualization.render import RenderingManager

        log.info("[PlayerRuntime] Shutting down")

        # Remove display from manager
        manager = RenderingManager.instance()
        if self._display is not None:
            manager.remove_display(self._display)

        self.scene = None

        if self.window is not None:
            self.window.close()
            self.window = None

        glfw.terminate()
        self.running = False


def run_project(
    project_path: str | Path,
    scene_name: str,
    width: int = 1280,
    height: int = 720,
    title: str = "Termin Player",
):
    """
    Run a project in standalone player mode.

    Args:
        project_path: Path to project directory
        scene_name: Scene filename to load (e.g., "main.scene")
        width: Window width
        height: Window height
        title: Window title
    """
    runtime = PlayerRuntime(
        project_path=project_path,
        scene_name=scene_name,
        width=width,
        height=height,
        title=title,
    )
    runtime.run()
