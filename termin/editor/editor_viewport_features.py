"""
EditorViewportFeatures — editor UX layer for main viewport.

Handles:
- Input management (EditorDisplayInputManager)
- Gizmo integration (picking, press handling)
- Selection/hover state
- Editor pipeline factory
- Framegraph debugger integration

Does NOT own:
- Display (reference from RenderingController)
- RenderEngine (owned by RenderingController)
- SDL window (owned by RenderingController)
"""

from __future__ import annotations

from typing import Callable, Optional, Tuple, TYPE_CHECKING

from termin.visualization.core.entity import Entity
from termin.visualization.core.viewport import Viewport
from termin.visualization.platform.backends.base import Action, MouseButton
from termin.visualization.render.framegraph import RenderPipeline

from termin.editor.gizmo_immediate import ImmediateGizmoController
from termin.editor.editor_display_input_manager import EditorDisplayInputManager

if TYPE_CHECKING:
    from termin.visualization.core.display import Display
    from termin.visualization.platform.backends.base import BackendWindow, GraphicsBackend


class EditorViewportFeatures:
    """
    Editor UX layer for the main viewport.

    Manages editor-specific features like picking, gizmo interaction,
    selection highlighting, and debug tools.

    Does not own Display or RenderEngine — those are managed by RenderingController.
    """

    def __init__(
        self,
        display: "Display",
        backend_window: "BackendWindow",
        graphics: "GraphicsBackend",
        gizmo_controller: ImmediateGizmoController,
        on_entity_picked: Callable[[Entity | None], None],
        on_hover_entity: Callable[[Entity | None], None],
        get_fbo_pool: Callable[[], dict],
        request_update: Callable[[], None],
    ) -> None:
        """
        Initialize EditorViewportFeatures.

        Args:
            display: Display reference (owned by RenderingController).
            backend_window: Backend window reference (owned by RenderingController).
            graphics: Graphics backend reference.
            gizmo_controller: Gizmo controller for transform manipulation.
            on_entity_picked: Callback when entity is selected.
            on_hover_entity: Callback when entity is hovered.
            get_fbo_pool: Callback to get FBO pool for picking.
            request_update: Callback to request viewport update.
        """
        self._display = display
        self._backend_window = backend_window
        self._graphics = graphics
        self._gizmo_controller = gizmo_controller
        self._on_entity_picked = on_entity_picked
        self._on_hover_entity = on_hover_entity
        self._get_fbo_pool = get_fbo_pool
        self._request_update = request_update

        self._framegraph_debugger = None
        self._debug_source_res: str = "color_pp"
        self._debug_paused: bool = False

        self.selected_entity_id: int = 0
        self.hover_entity_id: int = 0

        self._pending_pick_press: Optional[Tuple[float, float, object]] = None
        self._pending_pick_release: Optional[Tuple[float, float, object]] = None
        self._pending_hover: Optional[Tuple[float, float, object]] = None

        # Click vs drag detection
        self._press_position: Optional[Tuple[float, float]] = None
        self._gizmo_handled_press: bool = False
        self._click_threshold: float = 5.0

        # Create EditorDisplayInputManager
        self._input_manager = EditorDisplayInputManager(
            backend_window=self._backend_window,
            display=self._display,
            graphics=self._graphics,
            get_fbo_pool=self._get_fbo_pool,
            on_request_update=self._request_update,
            on_mouse_button_event=self._on_mouse_button_event,
            on_mouse_move_event=self._on_mouse_move,
        )
        self._input_manager.set_world_mode("editor")

    # ---------- Target display switching ----------

    def set_target_display(
        self,
        display: "Display",
        backend_window: "BackendWindow",
        get_fbo_pool: Callable[[], dict],
    ) -> None:
        """
        Switch to a new target display.

        This allows a single EditorViewportFeatures instance to handle
        editor input for any display that switches to "editor" mode.

        Args:
            display: New display to handle.
            backend_window: Backend window for the new display.
            get_fbo_pool: Callback to get FBO pool for the new display.
        """
        # Update references
        self._display = display
        self._backend_window = backend_window
        self._get_fbo_pool = get_fbo_pool

        # Clear pending events from old display
        self._pending_pick_press = None
        self._pending_pick_release = None
        self._pending_hover = None
        self._press_position = None
        self._gizmo_handled_press = False

        # Recreate EditorDisplayInputManager for the new display
        self._input_manager = EditorDisplayInputManager(
            backend_window=self._backend_window,
            display=self._display,
            graphics=self._graphics,
            get_fbo_pool=self._get_fbo_pool,
            on_request_update=self._request_update,
            on_mouse_button_event=self._on_mouse_button_event,
            on_mouse_move_event=self._on_mouse_move,
        )
        self._input_manager.set_world_mode("editor")

    def detach_from_display(self) -> None:
        """
        Detach from current display (clear input callbacks).

        Called when the display switches away from "editor" mode.
        """
        # Clear backend window callbacks
        if self._backend_window is not None:
            self._backend_window.set_cursor_pos_callback(None)
            self._backend_window.set_scroll_callback(None)
            self._backend_window.set_mouse_button_callback(None)
            self._backend_window.set_key_callback(None)

        # Clear pending events
        self._pending_pick_press = None
        self._pending_pick_release = None
        self._pending_hover = None
        self._press_position = None
        self._gizmo_handled_press = False

    # ---------- Properties ----------

    @property
    def display(self) -> "Display":
        """Display reference (not owned)."""
        return self._display

    @property
    def viewport(self) -> Viewport:
        """Primary viewport of the display."""
        if self._display.viewports:
            return self._display.viewports[0]
        raise RuntimeError("No viewports in editor display")

    @property
    def input_manager(self) -> EditorDisplayInputManager:
        """Input manager for editor display."""
        return self._input_manager

    # ---------- Camera/Scene management ----------

    def set_camera(self, camera) -> None:
        """Set camera for the primary viewport."""
        viewport = self.viewport
        viewport.camera = camera
        camera.add_viewport(viewport)

    def set_scene(self, scene) -> None:
        """Set scene for the primary viewport. Clears pending events."""
        self.viewport.scene = scene
        # Clear pending events (they reference old scene's viewport state)
        self._pending_pick_press = None
        self._pending_pick_release = None
        self._pending_hover = None
        self._press_position = None
        self._gizmo_handled_press = False

    def set_world_mode(self, mode: str) -> None:
        """Set input mode (editor/game)."""
        self._input_manager.set_world_mode(mode)

    def request_update(self) -> None:
        """Request viewport redraw."""
        self._request_update()

    # ---------- Picking ----------

    def get_pick_id_for_entity(self, ent: Entity | None) -> int:
        """Get pick ID for entity."""
        if ent is None:
            return 0
        return ent.pick_id

    def pick_entity_at(self, x: float, y: float, viewport: Viewport) -> Entity | None:
        """Pick entity from id buffer."""
        return self._input_manager.pick_entity_at(x, y, viewport)

    def pick_color_at(self, x: float, y: float, viewport: Viewport, buffer_name: str = "id"):
        """Pick color from FBO buffer."""
        return self._input_manager.pick_color_at(x, y, viewport, buffer_name)

    def pick_depth_at(self, x: float, y: float, viewport: Viewport, buffer_name: str = "id") -> float | None:
        """Pick depth from FBO buffer."""
        return self._input_manager.pick_depth_at(x, y, viewport, buffer_name)

    # ---------- Input event handlers ----------

    def _on_mouse_button_event(self, button_type, action, x, y, viewport) -> None:
        if button_type == MouseButton.LEFT and action == Action.RELEASE:
            self._pending_pick_release = (x, y, viewport)
            # End gizmo drag on release
            if self._gizmo_controller.is_dragging():
                self._gizmo_controller.on_mouse_button(viewport, 0, 0, 0)  # button=0, action=0 (release)
        if button_type == MouseButton.LEFT and action == Action.PRESS:
            self._pending_pick_press = (x, y, viewport)

    def _on_mouse_move(self, x: float, y: float, viewport) -> None:
        if viewport is None:
            self._pending_hover = None
            return
        self._pending_hover = (x, y, viewport)

        # Forward to gizmo controller for drag updates
        if self._gizmo_controller.is_dragging() and viewport is not None:
            self._gizmo_controller.on_mouse_move(viewport, x, y, 0, 0)

    def after_render(self) -> None:
        """
        Process pending events after render.

        Should be called by EditorWindow after RenderingController.render_all_displays().
        """
        if self._pending_pick_press is not None:
            self._process_pending_pick_press(self._pending_pick_press)
        if self._pending_pick_release is not None:
            self._process_pending_pick_release(self._pending_pick_release)
        if self._pending_hover is not None:
            self._process_pending_hover(self._pending_hover)

        if self._framegraph_debugger is not None and self._framegraph_debugger.isVisible():
            self._framegraph_debugger.debugger_request_update()

    # ---------- Hover / Selection / Gizmo ----------

    def _process_pending_hover(self, pending_hover) -> None:
        x, y, viewport = pending_hover
        self._pending_hover = None

        # Update gizmo hover state (raycast-based)
        if not self._gizmo_controller.is_dragging() and viewport is not None:
            ray = viewport.screen_point_to_ray(x, y)
            if ray is not None:
                self._gizmo_controller.update_hover(ray.origin, ray.direction)

        ent = self.pick_entity_at(x, y, viewport)
        if ent is not None and not ent.selectable:
            ent = None

        self._on_hover_entity(ent)

    def _process_pending_pick_release(self, pending_release) -> None:
        """
        Handle left mouse button release.

        Selection happens only if:
        1. Gizmo didn't handle the press (no transform started)
        2. Mouse didn't move significantly from press position (click, not drag)
        """
        x, y, viewport = pending_release
        self._pending_pick_release = None

        if self._gizmo_handled_press:
            self._gizmo_handled_press = False
            self._press_position = None
            return

        if self._press_position is not None:
            press_x, press_y = self._press_position
            dx = x - press_x
            dy = y - press_y
            distance_sq = dx * dx + dy * dy
            threshold_sq = self._click_threshold * self._click_threshold
            if distance_sq > threshold_sq:
                self._press_position = None
                return
            self._press_position = None

        ent = self.pick_entity_at(x, y, viewport)
        if ent is not None and not ent.selectable:
            ent = None

        self._on_entity_picked(ent)

    def _process_pending_pick_press(self, pending_press) -> None:
        """
        Handle left mouse button press.

        Remember position for click detection. If gizmo handles it, mark as handled.
        """
        x, y, viewport = pending_press
        self._pending_pick_press = None

        self._press_position = (x, y)
        self._gizmo_handled_press = False

        picked_color = self.pick_color_at(x, y, viewport, buffer_name="id")
        handled = self._gizmo_controller.handle_pick_press_with_color(
            x, y, viewport, picked_color
        )
        if handled:
            self._gizmo_handled_press = True

    # ---------- Debug helpers ----------

    def set_framegraph_debugger(self, debugger) -> None:
        self._framegraph_debugger = debugger

    def set_debug_source_resource(self, name: str) -> None:
        self._debug_source_res = name
        self._request_update()

    def get_debug_source_resource(self) -> str:
        return self._debug_source_res

    def set_debug_paused(self, paused: bool) -> None:
        self._debug_paused = paused
        self._request_update()

    def get_debug_paused(self) -> bool:
        return self._debug_paused

    # ---------- Pipeline ----------

    def make_editor_pipeline(self) -> RenderPipeline:
        """
        Create editor pipeline with gizmo, id pass, highlight effects.

        Returns:
            RenderPipeline configured for editor use.
        """
        from termin.visualization.render.framegraph import (
            ColorPass,
            IdPass,
            CanvasPass,
            PresentToScreenPass,
        )
        from termin.visualization.render.framegraph.passes.gizmo_immediate import ImmediateGizmoPass
        from termin.visualization.render.framegraph.passes.collider_gizmo import ColliderGizmoPass
        from termin.visualization.render.postprocess import PostProcessPass
        from termin.visualization.render.posteffects.highlight import HighlightEffect
        from termin.visualization.render.framegraph.passes.depth import DepthPass
        from termin.visualization.render.framegraph.passes.skybox import SkyBoxPass
        from termin.visualization.render.framegraph.passes.shadow import ShadowPass

        def get_gizmo_renderer():
            return self._gizmo_controller.gizmo_renderer

        postprocess = PostProcessPass(
            effects=[],
            input_res="color",
            output_res="color_pp",
            pass_name="PostFX",
        )

        depth_pass = DepthPass(input_res="empty_depth", output_res="depth", pass_name="Depth")

        color_pass = ColorPass(
            input_res="skybox",
            output_res="color_scene",
            shadow_res="shadow_maps",
            pass_name="Color",
            phase_mark="opaque",
        )

        transparent_pass = ColorPass(
            input_res="color_scene",
            output_res="color_transparent",
            shadow_res=None,
            pass_name="Transparent",
            phase_mark="transparent",
            sort_by_distance=True,
        )

        editor_color_pass = ColorPass(
            input_res="color_transparent",
            output_res="color_editor",
            shadow_res=None,
            pass_name="EditorColor",
            phase_mark="editor",
        )

        # Collider wireframe pass
        collider_gizmo_pass = ColliderGizmoPass(
            input_res="color_editor",
            output_res="color_colliders",
            pass_name="ColliderGizmo",
        )

        # Immediate gizmo pass (renders directly, no entities)
        gizmo_pass = ImmediateGizmoPass(
            gizmo_renderer=get_gizmo_renderer,
            input_res="color_colliders",
            output_res="color",
            pass_name="Gizmo",
        )

        skybox_pass = SkyBoxPass(input_res="empty", output_res="skybox", pass_name="Skybox")

        shadow_pass = ShadowPass(
            output_res="shadow_maps",
            pass_name="Shadow",
            default_resolution=1024,
            ortho_size=20.0,
            near=0.1,
            far=100.0,
        )

        passes: list = [
            shadow_pass,
            skybox_pass,
            color_pass,
            transparent_pass,
            editor_color_pass,
            collider_gizmo_pass,
            gizmo_pass,
            depth_pass,
            IdPass(input_res="empty_id", output_res="id", pass_name="Id"),
            postprocess,
            CanvasPass(
                src="color_pp",
                dst="color+ui",
                pass_name="Canvas",
            ),
            PresentToScreenPass(
                input_res="color+ui",
                pass_name="Present",
            ),
        ]

        postprocess.add_effect(
            HighlightEffect(
                lambda: self.hover_entity_id,
                color=(0.3, 0.8, 1.0, 1.0),
            )
        )
        postprocess.add_effect(
            HighlightEffect(
                lambda: self.selected_entity_id,
                color=(1.0, 0.9, 0.1, 1.0),
            )
        )

        return RenderPipeline(
            passes=passes,
            pipeline_specs=[],
        )
