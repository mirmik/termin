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

from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

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
        self._display_names: Dict[int, str] = {}

        # Map display id -> dict of viewport id -> ViewportRenderState
        self._viewport_states: Dict[int, Dict[int, "ViewportRenderState"]] = {}

        # Graphics backend (set externally)
        self._graphics: Optional["GraphicsBackend"] = None

        # RenderEngine (created lazily)
        self._render_engine: Optional["RenderEngine"] = None

        # Default pipeline (optional)
        self._default_pipeline: Optional["RenderPipeline"] = None

    # --- Configuration ---

    def set_graphics(self, graphics: "GraphicsBackend") -> None:
        """Set graphics backend for rendering."""
        self._graphics = graphics

    def set_default_pipeline(self, pipeline: "RenderPipeline") -> None:
        """Set default pipeline for new viewports."""
        self._default_pipeline = pipeline

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
            name: Optional display name.
        """
        if display in self._displays:
            return

        self._displays.append(display)
        display_id = id(display)

        if name is not None:
            self._display_names[display_id] = name
        else:
            self._display_names[display_id] = f"Display {len(self._displays) - 1}"

        # Initialize viewport states for this display
        self._viewport_states[display_id] = {}

    def remove_display(self, display: "Display") -> None:
        """Remove display from management."""
        if display not in self._displays:
            return

        display_id = id(display)
        self._displays.remove(display)
        self._display_names.pop(display_id, None)
        self._viewport_states.pop(display_id, None)

    def get_display_name(self, display: "Display") -> str:
        """Get display name."""
        return self._display_names.get(id(display), "Display")

    def set_display_name(self, display: "Display", name: str) -> None:
        """Set display name."""
        self._display_names[id(display)] = name

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

        # Use default pipeline if not specified
        if pipeline is None:
            pipeline = self._default_pipeline

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

    def get_or_create_viewport_state(self, viewport: "Viewport") -> "ViewportRenderState":
        """Get or create render state for a viewport."""
        from termin.visualization.render.state import ViewportRenderState

        display = viewport.display
        if display is None:
            raise ValueError("Viewport has no display")

        display_id = id(display)
        if display_id not in self._viewport_states:
            self._viewport_states[display_id] = {}

        viewport_id = id(viewport)
        states = self._viewport_states[display_id]

        if viewport_id not in states:
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
        if self._graphics is None:
            return

        # Lazy create render engine
        if self._render_engine is None:
            from termin.visualization.render.engine import RenderEngine
            self._render_engine = RenderEngine(self._graphics)

        from termin.visualization.render.view import RenderView

        surface = display.surface
        if surface is None:
            return

        # Collect views and states, sorted by depth
        views_and_states = []
        sorted_viewports = sorted(display.viewports, key=lambda v: v.depth)

        for viewport in sorted_viewports:
            if viewport.pipeline is None or viewport.scene is None:
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
