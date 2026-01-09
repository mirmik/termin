"""
RenderingManager - global singleton for managing displays and rendering.

Core responsibilities:
- Display/Viewport lifecycle
- ViewportRenderState management
- Unified render loop
- Scene mounting to displays

No Qt dependencies - can be used in standalone player or editor.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Tuple  # Dict still needed for viewport_states

# Type alias for display factory callback
# Takes display name, returns Display or None
DisplayFactory = Callable[[str], Optional["Display"]]

# Type alias for pipeline factory callback
# Takes pipeline name (e.g., "(Editor)"), returns RenderPipeline or None
PipelineFactory = Callable[[str], Optional["RenderPipeline"]]

if TYPE_CHECKING:
    from termin.visualization.core.display import Display
    from termin.visualization.core.viewport import Viewport
    from termin.visualization.core.scene import Scene
    from termin.visualization.core.camera import CameraComponent
    from termin.visualization.platform.backends.base import GraphicsBackend
    from termin.visualization.render.engine import RenderEngine
    from termin.visualization.render.state import ViewportRenderState
    from termin.visualization.render.framegraph import RenderPipeline


class RenderingManager:
    """
    Global rendering manager singleton.

    Manages displays, viewports, and rendering without Qt dependencies.
    """

    _instance: Optional["RenderingManager"] = None

    @classmethod
    def instance(cls) -> "RenderingManager":
        """Get or create the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def _reset_for_testing(cls) -> None:
        """Reset singleton. For testing only."""
        cls._instance = None

    def __init__(self):
        if RenderingManager._instance is not None:
            raise RuntimeError("Use RenderingManager.instance() instead of constructor")

        self._displays: List["Display"] = []

        # Map display id -> dict of viewport id -> ViewportRenderState
        self._viewport_states: Dict[int, Dict[int, "ViewportRenderState"]] = {}

        # Graphics backend (set externally)
        self._graphics: Optional["GraphicsBackend"] = None

        # RenderEngine (created lazily)
        self._render_engine: Optional["RenderEngine"] = None

        # Default pipeline (optional)
        self._default_pipeline: Optional["RenderPipeline"] = None

        # Display factory callback (creates displays on demand)
        self._display_factory: Optional[DisplayFactory] = None

        # Pipeline factory callback (creates pipelines by special names)
        self._pipeline_factory: Optional[PipelineFactory] = None

    # --- Configuration ---

    def set_graphics(self, graphics: "GraphicsBackend") -> None:
        """Set graphics backend for rendering."""
        self._graphics = graphics

    def set_default_pipeline(self, pipeline: "RenderPipeline") -> None:
        """Set default pipeline for new viewports."""
        self._default_pipeline = pipeline

    def set_display_factory(self, factory: DisplayFactory) -> None:
        """
        Set callback for creating displays on demand.

        The factory is called when attach_scene() needs a display that
        doesn't exist yet. It receives the display name and should return
        a Display or None if creation fails.

        Args:
            factory: Callable[[str], Display | None]
        """
        self._display_factory = factory

    def set_pipeline_factory(self, factory: PipelineFactory) -> None:
        """
        Set callback for creating pipelines by special names.

        The factory is called when attach_scene() needs a pipeline by name
        (e.g., "(Editor)"). It receives the pipeline name and should return
        a RenderPipeline or None if creation fails.

        Args:
            factory: Callable[[str], RenderPipeline | None]
        """
        self._pipeline_factory = factory

    @property
    def graphics(self) -> Optional["GraphicsBackend"]:
        """Current graphics backend."""
        return self._graphics

    @property
    def render_engine(self) -> Optional["RenderEngine"]:
        """Render engine (created lazily on first render)."""
        return self._render_engine

    # --- Display management ---

    @property
    def displays(self) -> List["Display"]:
        """List of managed displays (copy)."""
        return list(self._displays)

    def add_display(self, display: "Display", name: Optional[str] = None) -> None:
        """
        Add display to management.

        Args:
            display: Display to add.
            name: Optional display name (sets display.name if provided).
        """
        if display in self._displays:
            return

        self._displays.append(display)
        display_id = id(display)

        if name is not None:
            display.name = name

        # Initialize viewport states for this display
        self._viewport_states[display_id] = {}

    def remove_display(self, display: "Display") -> None:
        """Remove display from management."""
        if display not in self._displays:
            return

        display_id = id(display)
        self._displays.remove(display)
        self._viewport_states.pop(display_id, None)

    def get_display_name(self, display: "Display") -> str:
        """Get display name."""
        return display.name

    def set_display_name(self, display: "Display", name: str) -> None:
        """Set display name."""
        display.name = name

    def get_display_by_name(self, name: str) -> Optional["Display"]:
        """
        Find display by name.

        Args:
            name: Display name to find.

        Returns:
            Display with matching name or None.
        """
        for display in self._displays:
            if display.name == name:
                return display
        return None

    def get_or_create_display(self, name: str) -> Optional["Display"]:
        """
        Get existing display or create via factory.

        First looks for display by name. If not found and factory is set,
        calls factory to create a new display.

        Args:
            name: Display name.

        Returns:
            Display or None if not found and factory unavailable/failed.
        """
        # Check existing displays by name
        display = self.get_display_by_name(name)
        if display is not None:
            return display

        # Try factory
        if self._display_factory is not None:
            display = self._display_factory(name)
            if display is not None:
                self.add_display(display, name)
                return display

        return None

    # --- Scene mounting ---

    def mount_scene(
        self,
        scene: "Scene",
        display: "Display",
        camera: Optional["CameraComponent"] = None,
        region: Tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0),
        pipeline: Optional["RenderPipeline"] = None,
    ) -> "Viewport":
        """
        Mount a scene to a display region.

        Creates viewport with scene's camera (or specified camera) in the given region.

        Args:
            scene: Scene to mount.
            display: Target display.
            camera: Camera to use (if None, finds first camera in scene).
            region: Normalized rect (x, y, w, h) on display.
            pipeline: Render pipeline (uses default if None).

        Returns:
            Created viewport.
        """
        from termin.visualization.core.viewport import Viewport
        from termin.visualization.core.camera import CameraComponent

        # Find camera if not specified
        if camera is None:
            for entity in scene.entities:
                cam = entity.get_component(CameraComponent)
                if cam is not None:
                    camera = cam
                    break

        if camera is None:
            raise ValueError("No camera found in scene and none specified")

        # Use default pipeline if not specified (copy to avoid shared state)
        if pipeline is None:
            if self._default_pipeline is not None:
                pipeline = self._default_pipeline.copy()

        # Create viewport
        viewport = Viewport(
            scene=scene,
            camera=camera,
            rect=region,
            display=display,
            pipeline=pipeline,
        )

        display.add_viewport(viewport)
        camera.add_viewport(viewport)

        return viewport

    def unmount_scene(self, scene: "Scene", display: "Display") -> None:
        """
        Unmount scene from display.

        Removes all viewports showing this scene from the display.

        Args:
            scene: Scene to unmount.
            display: Display to unmount from.
        """
        viewports_to_remove = [
            vp for vp in display.viewports
            if vp.scene is scene
        ]

        for viewport in viewports_to_remove:
            if viewport.camera is not None:
                viewport.camera.remove_viewport(viewport)
            display.remove_viewport(viewport)

    def attach_scene(self, scene: "Scene") -> List["Viewport"]:
        """
        Attach scene using its viewport configuration.

        Reads scene.viewport_configs and creates viewports on appropriate
        displays. Displays are created via factory if not already present.

        Args:
            scene: Scene with viewport_configs to attach.

        Returns:
            List of created viewports.
        """
        from termin._native import log
        from termin.visualization.core.camera import CameraComponent

        viewports = []

        for config in scene.viewport_configs:
            # Get or create display
            display = self.get_or_create_display(config.display_name)
            if display is None:
                log.warn(
                    f"[RenderingManager] Cannot create display '{config.display_name}' "
                    f"for scene viewport"
                )
                continue

            # Find camera by UUID
            camera: Optional[CameraComponent] = None
            if config.camera_uuid:
                entity = scene.get_entity(config.camera_uuid)
                if entity is not None:
                    camera = entity.get_component(CameraComponent)
                    log.info(f"[attach_scene] Found camera by UUID: {entity.name}")
                else:
                    log.warn(f"[attach_scene] Entity not found for camera_uuid={config.camera_uuid}")

            if camera is None:
                # Fallback: find first camera in scene
                for entity in scene.entities:
                    cam = entity.get_component(CameraComponent)
                    if cam is not None:
                        camera = cam
                        log.info(f"[attach_scene] Using fallback camera: {entity.name}")
                        break

            if camera is None:
                log.warn(
                    f"[RenderingManager] No camera found for viewport on "
                    f"display '{config.display_name}'"
                )
                continue

            # Get pipeline by UUID or special name
            pipeline = None
            if config.pipeline_uuid is not None:
                from termin.assets.resources import ResourceManager
                rm = ResourceManager.instance()
                pipeline = rm.get_pipeline_by_uuid(config.pipeline_uuid)
                if pipeline is None:
                    log.warn(f"[attach_scene] Pipeline not found for uuid={config.pipeline_uuid}")
                else:
                    log.info(f"[attach_scene] Found pipeline by UUID: {pipeline.name}")

            # Try pipeline_name if UUID lookup failed or not set
            if pipeline is None and config.pipeline_name is not None:
                if self._pipeline_factory is not None:
                    pipeline = self._pipeline_factory(config.pipeline_name)
                    if pipeline is not None:
                        log.info(f"[attach_scene] Created pipeline by name: {config.pipeline_name}")
                    else:
                        log.warn(f"[attach_scene] Pipeline factory returned None for name={config.pipeline_name}")
                else:
                    log.warn(f"[attach_scene] No pipeline factory set, cannot create pipeline for name={config.pipeline_name}")

            # Create viewport
            log.info(f"[attach_scene] Creating viewport: display={config.display_name}, camera={camera.entity.name if camera.entity else 'N/A'}, pipeline={pipeline.name if pipeline else 'None'}")
            viewport = self.mount_scene(
                scene=scene,
                display=display,
                camera=camera,
                region=config.region,
                pipeline=pipeline,
            )
            log.info(f"[attach_scene] Created viewport id={id(viewport)}, pipeline passes={len(viewport.pipeline.passes) if viewport.pipeline else 0}")
            viewport.depth = config.depth
            viewport.input_mode = config.input_mode
            viewport.block_input_in_editor = config.block_input_in_editor
            viewports.append(viewport)
            log.info(f"[attach_scene] Created viewport on {config.display_name}, display now has {len(display.viewports)} viewports")

        return viewports

    def detach_scene(self, scene: "Scene") -> None:
        """
        Detach scene from all displays.

        Removes all viewports showing this scene.

        Args:
            scene: Scene to detach.
        """
        for display in list(self._displays):
            self.unmount_scene(scene, display)

    # --- Viewport state management ---

    def get_viewport_state(self, viewport: "Viewport") -> Optional["ViewportRenderState"]:
        """Get render state for a viewport."""
        display = viewport.display
        if display is None:
            return None

        display_id = id(display)
        states = self._viewport_states.get(display_id)
        if states is None:
            return None

        return states.get(id(viewport))

    def remove_viewport_state(self, viewport: "Viewport") -> None:
        """Remove render state for a viewport (call after clearing FBOs)."""
        from termin._native import log

        display = viewport.display
        if display is None:
            return

        display_id = id(display)
        states = self._viewport_states.get(display_id)
        if states is None:
            return

        viewport_id = id(viewport)
        if viewport_id in states:
            log.info(f"[remove_viewport_state] removing state for viewport_id={viewport_id}")
            del states[viewport_id]

    def get_or_create_viewport_state(self, viewport: "Viewport") -> "ViewportRenderState":
        """Get or create render state for a viewport."""
        from termin.visualization.render.state import ViewportRenderState
        from termin._native import log

        display = viewport.display
        if display is None:
            raise ValueError("Viewport has no display")

        display_id = id(display)
        if display_id not in self._viewport_states:
            self._viewport_states[display_id] = {}

        viewport_id = id(viewport)
        states = self._viewport_states[display_id]

        if viewport_id not in states:
            log.info(f"[get_or_create_viewport_state] creating NEW state for viewport_id={viewport_id}")
            states[viewport_id] = ViewportRenderState()

        return states[viewport_id]

    # --- Rendering ---

    def render_display(self, display: "Display", present: bool = True) -> None:
        """
        Render a single display.

        Args:
            display: Display to render.
            present: Whether to present (swap buffers) after rendering.
        """
        from termin._native import log

        if self._graphics is None:
            log.warn("[render_display] _graphics is None")
            return

        # Lazy create render engine
        if self._render_engine is None:
            from termin.visualization.render.engine import RenderEngine
            self._render_engine = RenderEngine(self._graphics)

        from termin.visualization.render.view import RenderView

        surface = display.surface
        if surface is None:
            log.warn(f"[render_display] surface is None for display={display.name}")
            return

        # Collect views and states, sorted by depth
        views_and_states = []
        sorted_viewports = sorted(display.viewports, key=lambda v: v.depth)

        log.info(f"[render_display] display={display.name}, viewports={len(sorted_viewports)}")
        for viewport in sorted_viewports:
            camera_name = viewport.camera.entity.name if viewport.camera and viewport.camera.entity else "None"
            scene_id = id(viewport.scene) if viewport.scene else "None"
            pipeline_name = viewport.pipeline.name if viewport.pipeline else "None"
            log.info(f"  viewport: camera={camera_name}, scene_id={scene_id}, pipeline={pipeline_name}")
            if viewport.pipeline is None or viewport.scene is None:
                log.warn(f"  SKIPPED: pipeline={viewport.pipeline}, scene={viewport.scene}")
                continue

            state = self.get_or_create_viewport_state(viewport)
            view = RenderView(
                scene=viewport.scene,
                camera=viewport.camera,
                rect=viewport.rect,
                canvas=viewport.canvas,
                pipeline=viewport.pipeline,
            )
            views_and_states.append((view, state))

        # Render
        if views_and_states:
            self._render_engine.render_views(
                surface=surface,
                views=views_and_states,
                present=present,
            )
        else:
            # No viewports - clear screen
            from OpenGL import GL as gl
            gl.glClearColor(0.1, 0.1, 0.1, 1.0)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
            if present:
                surface.present()

    def render_all(self, present: bool = True) -> None:
        """
        Render all managed displays.

        Args:
            present: Whether to present after rendering each display.
        """
        for display in self._displays:
            self.render_display(display, present=present)
