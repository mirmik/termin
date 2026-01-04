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
        self.render_engine = None
        self.surface = None
        self.camera = None
        self._pipeline = None
        self._viewport_state = None

        # Timing
        self.target_fps = 60
        self.delta_time = 1.0 / self.target_fps
        self.last_time = 0.0

    def initialize(self) -> bool:
        """Initialize player systems."""
        from termin._native import log

        log.info(f"[PlayerRuntime] Initializing project: {self.project_path}")

        # Register components
        self._register_components()

        # Create default pipeline
        from termin.visualization.core.viewport import make_default_pipeline
        self._pipeline = make_default_pipeline()
        log.info(f"[PlayerRuntime] Created pipeline: {self._pipeline.name} with {len(self._pipeline.passes)} passes")

        # Create graphics backend
        from termin.graphics import OpenGLGraphicsBackend
        self.graphics = OpenGLGraphicsBackend()

        # Create window
        from termin.visualization.platform.backends.glfw import GLFWWindowHandle
        self.window = GLFWWindowHandle(
            self.width, self.height, self.title,
            graphics=self.graphics,
        )

        # Create render surface
        from termin.visualization.render.surface import WindowRenderSurface
        self.surface = WindowRenderSurface(self.window)

        # Create render engine
        from termin.visualization.render.engine import RenderEngine
        self.render_engine = RenderEngine(self.graphics)

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
        self.scene = Scene()
        scene_data = data.get("scene") or (data.get("scenes", [None])[0])
        if scene_data:
            self.scene.load_from_data(scene_data, context=None, update_settings=True)

        log.info(f"[PlayerRuntime] Scene loaded: {self.scene_name}")

        # Find or create camera
        self._setup_camera()

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

        # Render (includes present/swap_buffers)
        self._render()

        # Frame rate limiting
        frame_time = time.perf_counter() - current_time
        target_time = 1.0 / self.target_fps
        if frame_time < target_time:
            time.sleep(target_time - frame_time)

    _render_frame_count = 0

    def _render(self):
        """Render the scene."""
        if self.scene is None or self.camera is None:
            if PlayerRuntime._render_frame_count == 0:
                from termin._native import log
                log.warn(f"[PlayerRuntime] Cannot render: scene={self.scene is not None}, camera={self.camera is not None}")
            return

        from termin.visualization.render.view import RenderView
        from termin.visualization.render.state import ViewportRenderState

        view = RenderView(
            scene=self.scene,
            camera=self.camera,
            pipeline=self._pipeline,
        )

        if self._viewport_state is None:
            self._viewport_state = ViewportRenderState()

        if PlayerRuntime._render_frame_count == 0:
            from termin._native import log
            log.info(f"[PlayerRuntime] First render frame, camera entity: {self.camera.entity.name if self.camera.entity else 'None'}")
            log.info(f"[PlayerRuntime] Surface size: {self.surface.get_size()}")
            log.info(f"[PlayerRuntime] View pipeline: {view.pipeline}")

        try:
            self.render_engine.render_views(
                self.surface,
                [(view, self._viewport_state)],
                present=True,
            )
        except Exception as e:
            if PlayerRuntime._render_frame_count < 3:
                from termin._native import log
                log.error(f"[PlayerRuntime] Render error: {e}")
                import traceback
                traceback.print_exc()

        PlayerRuntime._render_frame_count += 1

    def shutdown(self):
        """Clean up resources."""
        import glfw
        from termin._native import log

        log.info("[PlayerRuntime] Shutting down")

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
