"""
RenderingManager - global singleton for managing displays and rendering.

Core responsibilities:
- Display/Viewport lifecycle
- ViewportRenderState management
- Unified render loop (offscreen-first model)
- Scene mounting to displays

Offscreen-first rendering model:
1. render_all() - рендерит все viewports в их output_fbos (один GL контекст)
2. present_all() - блитает output_fbos на дисплеи (swap buffers)

Преимущества:
- Scene pipelines могут охватывать viewports на разных дисплеях
- Все GPU ресурсы живут в одном контексте
- Дисплеи независимы и равноправны

No Qt dependencies - can be used in standalone player or editor.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Tuple

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
    from termin.visualization.render.offscreen_context import OffscreenContext


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

        # Dedicated offscreen GL context for rendering
        # All GPU resources live in this context
        self._offscreen_context: Optional["OffscreenContext"] = None

        # Viewport states - flat dict, not tied to displays
        # viewport_id -> ViewportRenderState
        self._viewport_states: Dict[int, "ViewportRenderState"] = {}

        # Legacy: display-based viewport states (for backwards compatibility)
        # Will be removed after migration
        self._legacy_viewport_states: Dict[int, Dict[int, "ViewportRenderState"]] = {}

        # Graphics backend (set via initialize() or set_graphics())
        self._graphics: Optional["GraphicsBackend"] = None

        # RenderEngine (created lazily)
        self._render_engine: Optional["RenderEngine"] = None

        # Default pipeline (optional)
        self._default_pipeline: Optional["RenderPipeline"] = None

        # Display factory callback (creates displays on demand)
        self._display_factory: Optional[DisplayFactory] = None

        # Pipeline factory callback (creates pipelines by special names)
        self._pipeline_factory: Optional[PipelineFactory] = None

        # Attached scenes (for scene pipeline execution)
        self._attached_scenes: List["Scene"] = []

        # Flag to use new offscreen-first rendering
        self._use_offscreen_rendering: bool = False

    # --- Configuration ---

    def initialize(self) -> None:
        """
        Initialize the rendering manager with dedicated offscreen context.

        Creates OffscreenContext which provides:
        - Dedicated GL context for all rendering
        - GraphicsBackend instance
        - Single context_key for all resources

        Call this before creating displays. Displays should share context
        with offscreen_context.gl_context.
        """
        from termin.visualization.render.offscreen_context import OffscreenContext

        if self._offscreen_context is not None:
            return  # Already initialized

        self._offscreen_context = OffscreenContext()
        self._graphics = self._offscreen_context.graphics
        self._use_offscreen_rendering = True

    @property
    def offscreen_context(self) -> Optional["OffscreenContext"]:
        """
        Dedicated offscreen GL context.

        Use offscreen_context.gl_context when creating displays
        to share GL context with the rendering system.
        """
        return self._offscreen_context

    @property
    def is_initialized(self) -> bool:
        """Check if rendering manager is initialized with offscreen context."""
        return self._offscreen_context is not None

    def set_graphics(self, graphics: "GraphicsBackend") -> None:
        """
        Set graphics backend for rendering.

        Note: prefer using initialize() which creates both
        offscreen context and graphics backend.
        """
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

    @property
    def attached_scenes(self) -> List["Scene"]:
        """List of attached scenes (copy)."""
        return list(self._attached_scenes)

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

        if name is not None:
            display.name = name

        # Legacy: Initialize viewport states for this display
        display_id = id(display)
        self._legacy_viewport_states[display_id] = {}

    def remove_display(self, display: "Display") -> None:
        """Remove display from management."""
        if display not in self._displays:
            return

        # Clean up viewport states for viewports on this display
        for viewport in display.viewports:
            viewport_id = id(viewport)
            state = self._viewport_states.pop(viewport_id, None)
            if state is not None:
                state.clear_all()

        display_id = id(display)
        self._displays.remove(display)

        # Legacy cleanup
        self._legacy_viewport_states.pop(display_id, None)

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
        name: str = "main",
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
            name: Viewport name for identification in pipeline.

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
            name=name,
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

        Also processes scene.scene_pipelines - compiles them and assigns
        to matching viewports by name.

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
                else:
                    log.warn(f"[attach_scene] Entity not found for camera_uuid={config.camera_uuid}")

            if camera is None:
                # Fallback: find first camera in scene
                fallback_entity = None
                for entity in scene.entities:
                    cam = entity.get_component(CameraComponent)
                    if cam is not None:
                        camera = cam
                        fallback_entity = entity
                        break
                if camera is not None:
                    log.warn(
                        f"[attach_scene] Camera uuid={config.camera_uuid} not found, "
                        f"using fallback '{fallback_entity.name}'"
                    )

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

            # Try pipeline_name if UUID lookup failed or not set
            if pipeline is None and config.pipeline_name is not None:
                if self._pipeline_factory is not None:
                    pipeline = self._pipeline_factory(config.pipeline_name)
                    if pipeline is None:
                        log.warn(f"[attach_scene] Pipeline factory returned None for name={config.pipeline_name}")
                else:
                    log.warn(f"[attach_scene] No pipeline factory set, cannot create pipeline for name={config.pipeline_name}")

            # Create viewport
            viewport = self.mount_scene(
                scene=scene,
                display=display,
                camera=camera,
                region=config.region,
                pipeline=pipeline,
            )
            viewport.name = config.name
            viewport.depth = config.depth
            viewport.input_mode = config.input_mode
            viewport.block_input_in_editor = config.block_input_in_editor
            viewport.layer_mask = config.layer_mask
            viewport.enabled = config.enabled
            viewports.append(viewport)

        # Process scene pipelines - compile and assign to viewports
        self._apply_scene_pipelines(scene, viewports)

        # Track attached scene
        if scene not in self._attached_scenes:
            self._attached_scenes.append(scene)

        return viewports

    def _apply_scene_pipelines(self, scene: "Scene", viewports: List["Viewport"]) -> None:
        """
        Compile scene pipelines and mark managed viewports.

        1. Compile scene pipeline assets into scene._compiled_pipelines
        2. Mark viewports as managed by scene pipeline (by name)

        Managed viewports are rendered by executing scene pipelines in render loop,
        not by iterating viewports directly.

        Args:
            scene: Scene with scene_pipelines handles
            viewports: List of viewports to potentially manage
        """
        from termin._native import log

        # Compile scene pipelines into scene
        scene.compile_scene_pipelines()

        # Build viewport lookup by name
        viewport_by_name: Dict[str, "Viewport"] = {}
        for vp in viewports:
            if vp.name:
                viewport_by_name[vp.name] = vp

        # Also check all displays for viewports
        for display in self._displays:
            for vp in display.viewports:
                if vp.name and vp.name not in viewport_by_name:
                    viewport_by_name[vp.name] = vp

        log.info(f"[_apply_scene_pipelines] Available viewports: {list(viewport_by_name.keys())}")

        # Mark viewports as managed by their scene pipeline
        for handle in scene.scene_pipelines:
            asset = handle.get_asset()
            if asset is None:
                continue

            for viewport_name in asset.target_viewports:
                viewport = viewport_by_name.get(viewport_name)
                if viewport is None:
                    log.error(
                        f"[attach_scene] Scene pipeline '{asset.name}' targets viewport "
                        f"'{viewport_name}' but no such viewport found"
                    )
                    continue

                viewport.managed_by_scene_pipeline = asset.name
                log.info(f"[attach_scene] Viewport '{viewport_name}' managed by '{asset.name}'")

    def detach_scene(self, scene: "Scene") -> None:
        """
        Detach scene from all displays.

        Removes all viewports showing this scene and cleans up compiled pipelines.

        Args:
            scene: Scene to detach.
        """
        for display in list(self._displays):
            self.unmount_scene(scene, display)

        # Remove from attached scenes
        if scene in self._attached_scenes:
            self._attached_scenes.remove(scene)

        # Destroy compiled pipelines
        scene.destroy_compiled_pipelines()

    def get_scene_pipeline(self, name: str) -> Optional["RenderPipeline"]:
        """
        Get compiled scene pipeline by name.

        Searches through attached scenes for a compiled pipeline with the given name.

        Args:
            name: Scene pipeline asset name.

        Returns:
            Compiled RenderPipeline or None if not found.
        """
        for scene in self._attached_scenes:
            pipeline = scene.get_compiled_pipeline(name)
            if pipeline is not None:
                return pipeline
        return None

    def get_render_stats(self) -> dict:
        """
        Get render statistics for debugging.

        Returns:
            dict with keys:
            - attached_scenes: number of attached scenes
            - scene_pipelines: total number of compiled scene pipelines
            - unmanaged_viewports: number of viewports not managed by scene pipelines
            - scene_names: list of attached scene names
            - pipeline_names: list of scene pipeline names
        """
        stats = {
            "attached_scenes": len(self._attached_scenes),
            "scene_pipelines": 0,
            "unmanaged_viewports": 0,
            "scene_names": [],
            "pipeline_names": [],
        }

        # Count scene pipelines
        for scene in self._attached_scenes:
            stats["scene_names"].append(scene.name or "<unnamed>")
            for pipeline_name in scene.compiled_pipelines.keys():
                stats["scene_pipelines"] += 1
                stats["pipeline_names"].append(pipeline_name)

        # Count unmanaged viewports across all displays
        for display in self._displays:
            for viewport in display.viewports:
                if not viewport.managed_by_scene_pipeline:
                    if viewport.pipeline is not None and viewport.scene is not None:
                        stats["unmanaged_viewports"] += 1

        return stats

    # --- Viewport state management ---

    def get_viewport_state(self, viewport: "Viewport") -> Optional["ViewportRenderState"]:
        """Get render state for a viewport."""
        viewport_id = id(viewport)

        # New flat structure
        state = self._viewport_states.get(viewport_id)
        if state is not None:
            return state

        # Legacy fallback
        display = viewport.display
        if display is None:
            return None

        display_id = id(display)
        states = self._legacy_viewport_states.get(display_id)
        if states is None:
            return None

        return states.get(viewport_id)

    def remove_viewport_state(self, viewport: "Viewport") -> None:
        """Remove render state for a viewport (call after clearing FBOs)."""
        viewport_id = id(viewport)

        # Remove from new structure
        state = self._viewport_states.pop(viewport_id, None)
        if state is not None:
            state.clear_all()

        # Legacy cleanup
        display = viewport.display
        if display is not None:
            display_id = id(display)
            states = self._legacy_viewport_states.get(display_id)
            if states is not None and viewport_id in states:
                del states[viewport_id]

    def get_or_create_viewport_state(self, viewport: "Viewport") -> "ViewportRenderState":
        """Get or create render state for a viewport."""
        from termin.visualization.render.state import ViewportRenderState

        viewport_id = id(viewport)

        # New flat structure (preferred)
        if self._use_offscreen_rendering:
            if viewport_id not in self._viewport_states:
                self._viewport_states[viewport_id] = ViewportRenderState()
            return self._viewport_states[viewport_id]

        # Legacy: display-based structure
        display = viewport.display
        if display is None:
            raise ValueError("Viewport has no display")

        display_id = id(display)
        if display_id not in self._legacy_viewport_states:
            self._legacy_viewport_states[display_id] = {}

        states = self._legacy_viewport_states[display_id]

        if viewport_id not in states:
            states[viewport_id] = ViewportRenderState()

        return states[viewport_id]

    # --- Rendering ---

    def render_display(self, display: "Display", present: bool = True) -> None:
        """
        Render a single display.

        Rendering order:
        1. Execute scene pipelines for attached scenes (renders managed viewports)
        2. Render unmanaged viewports with their own pipelines

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
        from termin.visualization.render.engine import ViewportContext

        surface = display.surface
        if surface is None:
            log.warn(f"[render_display] surface is None for display={display.name}")
            return

        # Build viewport lookup by name (for scene pipeline target resolution)
        viewport_by_name: Dict[str, "Viewport"] = {}
        for vp in display.viewports:
            if vp.name:
                viewport_by_name[vp.name] = vp

        width, height = surface.get_size()
        sorted_viewports = sorted(display.viewports, key=lambda v: v.depth)
        rendered_something = False

        # 1. Execute scene pipelines (renders managed viewports)
        for scene in self._attached_scenes:
            for pipeline_name, pipeline in scene.compiled_pipelines.items():
                target_viewports = scene.get_pipeline_targets(pipeline_name)

                # Collect viewport contexts for this pipeline
                viewport_contexts: Dict[str, ViewportContext] = {}
                first_viewport = None

                for viewport_name in target_viewports:
                    viewport = viewport_by_name.get(viewport_name)
                    if viewport is None:
                        continue
                    if not viewport.enabled:
                        continue
                    if viewport.scene is None or viewport.camera is None:
                        continue

                    if first_viewport is None:
                        first_viewport = viewport

                    # Compute pixel rect for viewport
                    vx, vy, vw, vh = viewport.rect
                    px = int(vx * width)
                    py = int(vy * height)
                    pw = max(1, int(vw * width))
                    ph = max(1, int(vh * height))

                    viewport_contexts[viewport_name] = ViewportContext(
                        name=viewport_name,
                        camera=viewport.camera,
                        rect=(px, py, pw, ph),
                        canvas=viewport.canvas,
                        layer_mask=viewport.effective_layer_mask,
                    )

                if not viewport_contexts or first_viewport is None:
                    continue

                # Use first viewport's state for the scene pipeline
                state = self.get_or_create_viewport_state(first_viewport)

                self._render_engine.render_scene_pipeline(
                    surface=surface,
                    pipeline=pipeline,
                    scene=scene,
                    viewport_contexts=viewport_contexts,
                    state=state,
                    default_viewport=target_viewports[0] if target_viewports else "",
                    present=False,
                )
                rendered_something = True

        # 2. Render unmanaged viewports (those without managed_by_scene_pipeline)
        views_and_states = []
        unmanaged_count = 0
        for viewport in sorted_viewports:
            # Skip disabled viewports
            if not viewport.enabled:
                continue

            # Skip managed viewports - already rendered by scene pipeline
            if viewport.managed_by_scene_pipeline:
                continue

            if viewport.pipeline is None or viewport.scene is None:
                continue

            unmanaged_count += 1
            state = self.get_or_create_viewport_state(viewport)
            view = RenderView(
                scene=viewport.scene,
                camera=viewport.camera,
                rect=viewport.rect,
                canvas=viewport.canvas,
                pipeline=viewport.pipeline,
                layer_mask=viewport.effective_layer_mask,
            )
            views_and_states.append((view, state))

        # Render unmanaged viewports
        if views_and_states:
            self._render_engine.render_views(
                surface=surface,
                views=views_and_states,
                present=False,
            )
            rendered_something = True

        # Present if needed
        if rendered_something:
            if present:
                surface.present()
        else:
            # No viewports - clear screen
            from OpenGL import GL as gl
            gl.glClearColor(0.1, 0.7, 0.7, 1.0)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
            if present:
                surface.present()

    def render_all(self, present: bool = True) -> None:
        """
        Render all viewports.

        If offscreen rendering is enabled (via initialize()):
        - Phase 1: render_all_offscreen() - renders to output_fbos
        - Phase 2: present_all() - blits to displays

        Otherwise falls back to legacy per-display rendering.

        Args:
            present: Whether to present after rendering.
        """
        if self._use_offscreen_rendering:
            self.render_all_offscreen()
            if present:
                self.present_all()
        else:
            # Legacy: render each display separately
            for display in self._displays:
                self.render_display(display, present=present)

    def render_all_offscreen(self) -> None:
        """
        Phase 1: Render all viewports to their output_fbos.

        Executes in dedicated offscreen context. All viewports (from all displays)
        are rendered in a single pass. Scene pipelines can span multiple displays.
        """
        from termin._native import log

        if self._offscreen_context is None:
            log.warn("[render_all_offscreen] OffscreenContext not initialized, call initialize() first")
            return

        if self._graphics is None:
            log.warn("[render_all_offscreen] Graphics backend not set")
            return

        # Activate offscreen context
        self._offscreen_context.make_current()
        context_key = self._offscreen_context.context_key

        # Lazy create render engine
        if self._render_engine is None:
            from termin.visualization.render.engine import RenderEngine
            self._render_engine = RenderEngine(self._graphics)

        # Collect ALL viewports from all displays
        all_viewports_by_name: Dict[str, "Viewport"] = {}
        for display in self._displays:
            for vp in display.viewports:
                if vp.name:
                    all_viewports_by_name[vp.name] = vp

        # 1. Execute scene pipelines (can span multiple displays)
        for scene in self._attached_scenes:
            for pipeline_name, pipeline in scene.compiled_pipelines.items():
                self._render_scene_pipeline_offscreen(
                    scene=scene,
                    pipeline_name=pipeline_name,
                    pipeline=pipeline,
                    all_viewports=all_viewports_by_name,
                    context_key=context_key,
                )

        # 2. Render unmanaged viewports
        for display in self._displays:
            for viewport in display.viewports:
                if not viewport.enabled:
                    continue
                if viewport.managed_by_scene_pipeline:
                    continue
                if viewport.pipeline is None or viewport.scene is None:
                    continue

                self._render_viewport_offscreen(viewport, context_key)

    def _render_scene_pipeline_offscreen(
        self,
        scene: "Scene",
        pipeline_name: str,
        pipeline: "RenderPipeline",
        all_viewports: Dict[str, "Viewport"],
        context_key: int,
    ) -> None:
        """Render a scene pipeline to viewport output_fbos."""
        from termin.visualization.render.engine import ViewportContext

        target_names = scene.get_pipeline_targets(pipeline_name)
        if not target_names:
            return

        # Collect viewport contexts from ALL displays
        viewport_contexts: Dict[str, ViewportContext] = {}
        first_viewport: Optional["Viewport"] = None

        for viewport_name in target_names:
            viewport = all_viewports.get(viewport_name)
            if viewport is None:
                continue
            if not viewport.enabled:
                continue
            if viewport.camera is None:
                continue

            display = viewport.display
            if display is None or display.surface is None:
                continue

            if first_viewport is None:
                first_viewport = viewport

            # Compute output size
            width, height = display.surface.get_size()
            vx, vy, vw, vh = viewport.rect
            pw = max(1, int(vw * width))
            ph = max(1, int(vh * height))

            # Ensure output FBO exists
            state = self.get_or_create_viewport_state(viewport)
            output_fbo = state.ensure_output_fbo(self._graphics, (pw, ph))

            viewport_contexts[viewport_name] = ViewportContext(
                name=viewport_name,
                camera=viewport.camera,
                rect=(0, 0, pw, ph),  # Full FBO, offset at blit time
                canvas=viewport.canvas,
                layer_mask=viewport.effective_layer_mask,
                output_fbo=output_fbo,
            )

        if not viewport_contexts or first_viewport is None:
            return

        # Use first viewport's state for shared resources
        state = self.get_or_create_viewport_state(first_viewport)

        self._render_engine.render_scene_pipeline_offscreen(
            pipeline=pipeline,
            scene=scene,
            viewport_contexts=viewport_contexts,
            shared_state=state,
            context_key=context_key,
            default_viewport=target_names[0] if target_names else "",
        )

    def _render_viewport_offscreen(
        self,
        viewport: "Viewport",
        context_key: int,
    ) -> None:
        """Render a single unmanaged viewport to its output_fbo."""
        from termin.visualization.render.view import RenderView

        display = viewport.display
        if display is None or display.surface is None:
            return

        # Compute output size
        width, height = display.surface.get_size()
        vx, vy, vw, vh = viewport.rect
        pw = max(1, int(vw * width))
        ph = max(1, int(vh * height))

        # Ensure output FBO
        state = self.get_or_create_viewport_state(viewport)
        output_fbo = state.ensure_output_fbo(self._graphics, (pw, ph))

        # Create RenderView
        view = RenderView(
            scene=viewport.scene,
            camera=viewport.camera,
            rect=(0.0, 0.0, 1.0, 1.0),  # Full output FBO
            canvas=viewport.canvas,
            pipeline=viewport.pipeline,
            layer_mask=viewport.effective_layer_mask,
        )

        self._render_engine.render_view_to_fbo(
            view=view,
            state=state,
            target_fbo=output_fbo,
            size=(pw, ph),
            context_key=context_key,
        )

    def present_all(self) -> None:
        """
        Phase 2: Blit viewport output_fbos to displays.

        For each display:
        1. make_current() (shared context)
        2. Clear display
        3. Blit viewports in depth order
        4. swap_buffers()
        """
        for display in self._displays:
            self._present_display(display)

    def _present_display(self, display: "Display") -> None:
        """Blit viewport output_fbos to a single display."""
        surface = display.surface
        if surface is None:
            return

        surface.make_current()

        width, height = surface.get_size()
        if width <= 0 or height <= 0:
            return

        display_fbo = surface.get_framebuffer()

        # Clear display
        self._graphics.bind_framebuffer(display_fbo)
        self._graphics.set_viewport(0, 0, width, height)
        self._graphics.clear_color_depth((0.1, 0.1, 0.1, 1.0))

        # Blit viewports in depth order
        sorted_viewports = sorted(display.viewports, key=lambda v: v.depth)

        for viewport in sorted_viewports:
            if not viewport.enabled:
                continue

            state = self.get_viewport_state(viewport)
            if state is None or state.output_fbo is None:
                continue

            # Compute destination rect on display
            vx, vy, vw, vh = viewport.rect
            dx = int(vx * width)
            dy = int(vy * height)
            dw = max(1, int(vw * width))
            dh = max(1, int(vh * height))

            # Blit output_fbo -> display_fbo
            self._graphics.blit_framebuffer(
                state.output_fbo,
                display_fbo,
                (0, 0, dw, dh),  # src rect (full output_fbo)
                (dx, dy, dx + dw, dy + dh),  # dst rect on display
            )

        surface.present()

    def _collect_all_viewports(self) -> Dict[str, "Viewport"]:
        """Collect all viewports from all displays by name."""
        result: Dict[str, "Viewport"] = {}
        for display in self._displays:
            for vp in display.viewports:
                if vp.name:
                    result[vp.name] = vp
        return result

    def shutdown(self) -> None:
        """
        Shutdown the rendering manager.

        Cleans up all viewport states and destroys offscreen context.
        """
        # Clear all viewport states
        for state in self._viewport_states.values():
            state.clear_all()
        self._viewport_states.clear()

        # Legacy cleanup
        for states_dict in self._legacy_viewport_states.values():
            for state in states_dict.values():
                state.clear_all()
        self._legacy_viewport_states.clear()

        # Destroy offscreen context
        if self._offscreen_context is not None:
            self._offscreen_context.destroy()
            self._offscreen_context = None

        self._graphics = None
        self._render_engine = None
