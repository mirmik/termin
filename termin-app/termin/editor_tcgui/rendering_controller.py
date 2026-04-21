"""RenderingControllerTcgui — manages displays and viewports in the tcgui editor.

Tcgui port of RenderingController. Uses FBOSurface instead of SDL embedded windows,
OffscreenContext for dedicated GL context, and delegates to RenderingManager for
core rendering logic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional

from tcbase import log
from termin.visualization.core.scene import scene_render_mount

if TYPE_CHECKING:
    from termin.visualization.core.display import Display
    from termin.visualization.core.viewport import Viewport
    from termin.visualization.core.scene import Scene
    from termin.visualization.render.framegraph import RenderPipeline
    from termin.visualization.render.offscreen_context import OffscreenContext
    from tgfx._tgfx_native import Tgfx2Context


class _NoOpViewportList:
    """Stub for EditorSceneAttachment compatibility (calls _viewport_list.refresh())."""

    def refresh(self) -> None:
        pass

    def set_render_targets(self, targets) -> None:
        # Qt editor used this to populate a side panel listing
        # offscreen render targets. The tcgui editor has no such panel
        # yet — the list is silently dropped until M14 restores a
        # parity panel.
        pass



class RenderingControllerTcgui:
    """Controller for managing rendering displays and viewports in tcgui editor.

    Provides:
    - Display/pipeline factory registration with RenderingManager
    - Scene attach/detach with viewport creation from viewport_configs
    - Input routing for game displays
    - Viewport config sync for save/load
    """

    def __init__(
        self,
        offscreen_context: "OffscreenContext",
        ctx: "Tgfx2Context",
        get_scene: Callable[[], "Scene | None"] | None = None,
        make_editor_pipeline: Callable[[], "RenderPipeline"] | None = None,
        on_request_update: Callable[[], None] | None = None,
        on_rendering_changed: Callable[[], None] | None = None,
    ) -> None:
        from termin._native.render import RenderingManager
        from termin.editor_core.rendering_model import RenderingModel

        self._manager = RenderingManager.instance()
        self._model = RenderingModel(self._manager, offscreen_context=offscreen_context)
        self._offscreen_context = offscreen_context
        # Process-global tgfx2 context — every FBOSurface this controller
        # creates allocates its color/depth textures on this device.
        # Passed in from run_editor_tcgui (currently built around
        # OffscreenContext, migrating to BackendWindow in M4).
        self._ctx = ctx
        self._get_scene = get_scene
        self._make_editor_pipeline = make_editor_pipeline
        self._on_request_update = on_request_update
        self._on_rendering_changed = on_rendering_changed

        self._display_surfaces: dict[int, object] = {}
        self._display_viewports: dict[int, object] = {}  # display_id -> Viewport3D
        self._display_input_managers: dict[int, object] = {}
        self._viewport_list = _NoOpViewportList()
        self._center_tabs = None

        # Register offscreen context with RenderingManager. Under
        # BackendWindow the GL context is always current on the one
        # thread that ever renders, and on Vulkan there's nothing to
        # make current at all — so the callback is a no-op in that
        # mode. We still wire it up when a legacy offscreen_context
        # was supplied (standalone tests that pre-date M4).
        if offscreen_context is not None:
            self._manager.set_make_current_callback(offscreen_context.make_current)
        else:
            self._manager.set_make_current_callback(lambda: None)

        # Register factories
        self._manager.set_display_factory(self._create_display_for_name)
        self._manager.set_pipeline_factory(self._create_pipeline_for_name)
        self._manager.set_display_removed_callback(self._on_display_removed)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def offscreen_context(self) -> "OffscreenContext":
        return self._offscreen_context

    @property
    def displays(self) -> list["Display"]:
        return self._manager.displays

    # ------------------------------------------------------------------
    # Editor display — backed by RenderingModel
    # ------------------------------------------------------------------

    @property
    def _editor_display_ptr(self) -> int | None:
        return self._model.editor_display_ptr

    @_editor_display_ptr.setter
    def _editor_display_ptr(self, value: int | None) -> None:
        self._model.set_editor_display_ptr(value)

    def set_editor_display_ptr(self, ptr: int) -> None:
        self._model.set_editor_display_ptr(ptr)

    def is_editor_display(self, display: "Display") -> bool:
        return display.tc_display_ptr == self._editor_display_ptr

    def set_center_tabs(self, tabs) -> None:
        self._center_tabs = tabs

    def _refresh_render_targets(self) -> None:
        """Refresh render target list from pool. Kept as a no-op method
        for EditorSceneAttachment parity with the Qt controller — the
        tcgui editor has not yet restored the render-targets debug
        panel, so there's nothing to refresh."""
        pass

    # ------------------------------------------------------------------
    # Factories
    # ------------------------------------------------------------------

    def _create_pipeline_for_name(self, name: str) -> "RenderPipeline | None":
        if name == "(Editor)":
            if self._make_editor_pipeline is not None:
                return self._make_editor_pipeline()
            return None

        from termin.assets.resources import ResourceManager
        rm = ResourceManager.instance()

        lookup_name = "Default" if (not name or name == "(Default)") else name
        pipeline = rm.get_pipeline(lookup_name)
        if pipeline is not None:
            return pipeline

        if lookup_name != "Default":
            return rm.get_pipeline("Default")
        return None

    def _create_display_for_name(self, name: str) -> "Display | None":
        from termin.visualization.core.display import Display
        from termin.visualization.platform.backends.fbo_backend import FBOSurface

        if self._offscreen_context is not None:
            self._offscreen_context.make_current()

        fbo = FBOSurface(800, 600, ctx=self._ctx)
        display = Display(surface=fbo, name=name)
        display.auto_remove_when_empty = True

        display_id = display.tc_display_ptr
        self._display_surfaces[display_id] = fbo

        # Add tab with Viewport3D for this display
        if self._center_tabs is not None:
            from tcgui.widgets.viewport3d import Viewport3D
            vp3d = Viewport3D()
            vp3d.stretch = True
            vp3d.set_surface(fbo, display)
            self._center_tabs.add_tab(name, vp3d)
            self._display_viewports[display_id] = vp3d

        return display

    # ------------------------------------------------------------------
    # Scene management
    # ------------------------------------------------------------------

    def attach_scene(self, scene: "Scene") -> list["Viewport"]:
        """Attach scene using its viewport configuration.

        Creates displays via factory, mounts viewports, sets up input managers.
        """
        viewports = self._manager.attach_scene(scene)

        # Set up input managers for each display based on viewport configs
        display_viewports: dict[int, list] = {}

        for viewport in viewports:
            display = self._manager.get_display_for_viewport(viewport)
            if display is None:
                continue
            display_id = display.tc_display_ptr

            config = self._find_viewport_config(scene, viewport, display)
            if config is None:
                continue

            if display_id not in display_viewports:
                display_viewports[display_id] = []
            display_viewports[display_id].append((viewport, config, display))

        for display_id, vp_configs in display_viewports.items():
            if not vp_configs:
                continue

            viewport, config, display = vp_configs[0]

            if display_id == self._editor_display_ptr:
                continue

            self._setup_display_input(display, config.input_mode)

        self._request_update()
        self._notify_rendering_changed()

        return viewports

    def detach_scene(self, scene: "Scene") -> None:
        """Detach scene from all displays."""
        displays_to_check: set[int] = set()
        for display in self._manager.displays:
            for viewport in display.viewports:
                if viewport.scene is scene:
                    displays_to_check.add(display.tc_display_ptr)

        self.remove_viewports_for_scene(scene)
        self._manager.detach_scene(scene)

        for display_ptr in displays_to_check:
            display = None
            for d in self._manager.displays:
                if d.tc_display_ptr == display_ptr:
                    display = d
                    break

            if display is not None and not display.viewports:
                if display_ptr in self._display_input_managers:
                    del self._display_input_managers[display_ptr]

        self._request_update()
        self._notify_rendering_changed()

    def remove_viewports_for_scene(self, scene: "Scene") -> None:
        """Remove all viewports referencing the given scene."""
        self._model.remove_viewports_for_scene(scene)

    def sync_viewport_configs_to_scene(self, scene: "Scene") -> None:
        """Snapshot this scene's viewports into its viewport_configs."""
        self._model.sync_viewport_configs_to_scene(scene)

    def sync_render_target_configs_to_scene(self, scene: "Scene") -> None:
        """Snapshot the render target pool into scene.render_target_configs."""
        self._model.sync_render_target_configs_to_scene(scene)

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def _setup_display_input(self, display: "Display", input_mode: str) -> None:
        display_id = display.tc_display_ptr

        if display_id in self._display_input_managers:
            del self._display_input_managers[display_id]

        # Clear input manager on surface first — leaving a dangling ptr from
        # the previous router would dispatch events into freed memory once
        # the router dict entry is removed above.
        surface = display.surface
        if surface is not None:
            surface.set_input_manager(0)

        if input_mode == "none":
            pass
        elif input_mode in ("simple", "basic"):
            from termin.visualization.platform.input_manager import DisplayInputRouter

            input_router = DisplayInputRouter(display.tc_display_ptr)
            self._display_input_managers[display_id] = input_router
            # Surface must know the router's tc_input_manager_ptr so the
            # SDL/FBO dispatch path (and Viewport3D._connect_input, which
            # reads it via _render_surface_get_input_manager) actually
            # routes through the viewport input managers attached to the
            # display. Without this call picking/hover never fire — the
            # default surface input_manager has no viewport-aware logic.
            if surface is not None:
                surface.set_input_manager(input_router.tc_input_manager_ptr)
        elif input_mode == "editor":
            # Editor display is handled by EditorWindowTcgui directly —
            # it creates its own DisplayInputRouter + EditorViewportInput-
            # Managers and calls surface.set_input_manager() there.
            pass

    # ------------------------------------------------------------------
    # Viewport state (needed by EditorSceneAttachment.detach)
    # ------------------------------------------------------------------

    def get_viewport_state(self, viewport: "Viewport"):
        return self._manager.get_viewport_state(viewport)

    def get_all_viewports_info(self) -> list[tuple["Viewport", str]]:
        """Get list of all viewports with display names for UI selection."""
        result: list[tuple["Viewport", str]] = []

        scene_pipeline_viewports: dict[str, list[tuple["Viewport", str, int]]] = {}
        unmanaged_viewports: list[tuple["Viewport", str, int]] = []

        for display in self._manager.displays:
            display_name = self._manager.get_display_name(display)
            for i, viewport in enumerate(display.viewports):
                if viewport.managed_by_scene_pipeline:
                    pipeline_name = viewport.managed_by_scene_pipeline
                    if pipeline_name not in scene_pipeline_viewports:
                        scene_pipeline_viewports[pipeline_name] = []
                    scene_pipeline_viewports[pipeline_name].append((viewport, display_name, i))
                else:
                    unmanaged_viewports.append((viewport, display_name, i))

        for pipeline_name, viewports in sorted(scene_pipeline_viewports.items()):
            for viewport, display_name, i in viewports:
                vp_name = viewport.name or f"Viewport {i}"
                label = f"[{pipeline_name}] {vp_name}"
                result.append((viewport, label))

        for viewport, display_name, i in unmanaged_viewports:
            vp_name = viewport.name or f"Viewport {i}"
            label = f"{display_name} / {vp_name}"
            result.append((viewport, label))

        return result

    # ------------------------------------------------------------------
    # EditorStateIO callbacks
    # ------------------------------------------------------------------

    def get_displays_data(self) -> list | None:
        """Sync viewport and render target configs and return None (new format stores in scene)."""
        scene = self._get_scene() if self._get_scene is not None else None
        if scene is not None:
            self.sync_viewport_configs_to_scene(scene)
            self.sync_render_target_configs_to_scene(scene)
        return None

    def set_displays_data(self, data: list | None) -> None:
        """Attach scene if it has viewport_configs and not already attached."""
        scene = self._get_scene() if self._get_scene is not None else None
        if scene is None:
            return

        if not scene_render_mount(scene).viewport_configs:
            return

        # Check if scene already has non-editor viewports (already attached)
        for display in self._manager.displays:
            if display.tc_display_ptr == self._editor_display_ptr:
                continue
            for vp in display.viewports:
                if vp.scene is scene:
                    return  # Already attached

        self.attach_scene(scene)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_viewport_config(self, scene: "Scene", viewport: "Viewport", display: "Display | None" = None):
        if display is None:
            display = self._manager.get_display_for_viewport(viewport)
        if display is None or viewport.camera is None:
            return None

        # Match by (display_name, camera_uuid). camera.entity.uuid is
        # the stable identifier for a viewport across save/load — unique
        # within a scene and invariant under renames / reordering.
        display_name = display.name
        camera_uuid = ""
        if viewport.camera.entity is not None:
            camera_uuid = viewport.camera.entity.uuid

        for config in scene_render_mount(scene).viewport_configs:
            if config.display_name == display_name and config.camera_uuid == camera_uuid:
                return config

        return None

    def _on_display_removed(self, display: "Display") -> None:
        display_id = display.tc_display_ptr

        # Remove tab
        if display_id in self._display_viewports:
            vp3d = self._display_viewports.pop(display_id)
            if self._center_tabs is not None:
                for i, page in enumerate(self._center_tabs.pages):
                    if page is vp3d:
                        self._center_tabs.remove_tab(i)
                        break

        if display_id in self._display_surfaces:
            del self._display_surfaces[display_id]

        if display_id in self._display_input_managers:
            del self._display_input_managers[display_id]

        self._notify_rendering_changed()

    def _request_update(self) -> None:
        if self._on_request_update is not None:
            self._on_request_update()

    def _notify_rendering_changed(self) -> None:
        if self._on_rendering_changed is not None:
            self._on_rendering_changed()
