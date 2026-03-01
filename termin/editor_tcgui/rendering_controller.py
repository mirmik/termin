"""RenderingControllerTcgui — manages displays and viewports in the tcgui editor.

Tcgui port of RenderingController. Uses FBOSurface instead of SDL embedded windows,
OffscreenContext for dedicated GL context, and delegates to RenderingManager for
core rendering logic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional

from tcbase import log

if TYPE_CHECKING:
    from termin.visualization.core.display import Display
    from termin.visualization.core.viewport import Viewport
    from termin.visualization.core.scene import Scene
    from termin.visualization.render.framegraph import RenderPipeline
    from termin.visualization.render.offscreen_context import OffscreenContext


class _NoOpViewportList:
    """Stub for EditorSceneAttachment compatibility (calls _viewport_list.refresh())."""

    def refresh(self) -> None:
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
        get_scene: Callable[[], "Scene | None"] | None = None,
        make_editor_pipeline: Callable[[], "RenderPipeline"] | None = None,
        on_request_update: Callable[[], None] | None = None,
        on_rendering_changed: Callable[[], None] | None = None,
    ) -> None:
        from termin._native.render import RenderingManager

        self._manager = RenderingManager.instance()
        self._offscreen_context = offscreen_context
        self._get_scene = get_scene
        self._make_editor_pipeline = make_editor_pipeline
        self._on_request_update = on_request_update
        self._on_rendering_changed = on_rendering_changed

        self._editor_display_ptr: int | None = None
        self._display_surfaces: dict[int, object] = {}
        self._display_input_managers: dict[int, object] = {}
        self._viewport_list = _NoOpViewportList()

        # Register offscreen context with RenderingManager
        self._manager.set_graphics(offscreen_context.graphics)
        self._manager.set_make_current_callback(offscreen_context.make_current)

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
    # Editor display
    # ------------------------------------------------------------------

    def set_editor_display_ptr(self, ptr: int) -> None:
        self._editor_display_ptr = ptr

    def is_editor_display(self, display: "Display") -> bool:
        return display.tc_display_ptr == self._editor_display_ptr

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

        self._offscreen_context.make_current()

        fbo = FBOSurface(width=800, height=600)
        display = Display(surface=fbo, name=name)
        display.auto_remove_when_empty = True

        display_id = display.tc_display_ptr
        self._display_surfaces[display_id] = fbo

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
        self._offscreen_context.make_current()

        for display in self._manager.displays:
            viewports_to_remove = [vp for vp in display.viewports if vp.scene is scene]
            if not viewports_to_remove:
                continue

            for vp in viewports_to_remove:
                if vp.pipeline is not None:
                    vp.pipeline.destroy()
                state = self._manager.get_viewport_state(vp)
                if state is not None:
                    state.clear_all()
                self._manager.remove_viewport_state(vp)
                display.remove_viewport(vp)

    def sync_viewport_configs_to_scene(self, scene: "Scene") -> None:
        """Sync current viewport state to scene.viewport_configs.

        Call before saving. Excludes editor display viewports.
        """
        from termin.visualization.core.viewport_config import ViewportConfig

        scene.clear_viewport_configs()

        for display in self._manager.displays:
            if display.tc_display_ptr == self._editor_display_ptr:
                continue

            for viewport in display.viewports:
                if viewport.scene is not scene:
                    continue

                camera_uuid = ""
                if viewport.camera is not None and viewport.camera.entity is not None:
                    camera_uuid = viewport.camera.entity.uuid

                pipeline_uuid = None
                pipeline_name = None
                if viewport.pipeline is not None:
                    pipeline_uuid = self._get_pipeline_uuid(viewport.pipeline)
                    if pipeline_uuid is None:
                        if viewport.pipeline.name == "editor":
                            pipeline_name = "(Editor)"

                rect = viewport.rect
                config = ViewportConfig(
                    name=viewport.name or "",
                    display_name=display.name,
                    camera_uuid=camera_uuid,
                    region_x=rect[0],
                    region_y=rect[1],
                    region_w=rect[2],
                    region_h=rect[3],
                    depth=viewport.depth,
                    input_mode=viewport.input_mode,
                    block_input_in_editor=viewport.block_input_in_editor,
                    pipeline_uuid=pipeline_uuid or "",
                    pipeline_name=pipeline_name or "",
                    layer_mask=viewport.layer_mask,
                    enabled=viewport.enabled,
                )
                scene.add_viewport_config(config)

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def _setup_display_input(self, display: "Display", input_mode: str) -> None:
        display_id = display.tc_display_ptr

        if display_id in self._display_input_managers:
            del self._display_input_managers[display_id]

        if input_mode == "none":
            pass
        elif input_mode in ("simple", "basic"):
            from termin.visualization.platform.input_manager import DisplayInputRouter

            input_router = DisplayInputRouter(display.tc_display_ptr)
            self._display_input_managers[display_id] = input_router

    # ------------------------------------------------------------------
    # Viewport state (needed by EditorSceneAttachment.detach)
    # ------------------------------------------------------------------

    def get_viewport_state(self, viewport: "Viewport"):
        return self._manager.get_viewport_state(viewport)

    # ------------------------------------------------------------------
    # EditorStateIO callbacks
    # ------------------------------------------------------------------

    def get_displays_data(self) -> list | None:
        """Sync viewport configs and return None (new format stores in scene)."""
        scene = self._get_scene() if self._get_scene is not None else None
        if scene is not None:
            self.sync_viewport_configs_to_scene(scene)
        return None

    def set_displays_data(self, data: list | None) -> None:
        """Attach scene if it has viewport_configs and not already attached."""
        scene = self._get_scene() if self._get_scene is not None else None
        if scene is None:
            return

        if not scene.viewport_configs:
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

        display_name = display.name
        camera_uuid = ""
        if viewport.camera.entity is not None:
            camera_uuid = viewport.camera.entity.uuid

        for config in scene.viewport_configs:
            if config.display_name == display_name and config.camera_uuid == camera_uuid:
                return config

        return None

    def _get_pipeline_uuid(self, pipeline: "RenderPipeline") -> str | None:
        from termin.assets.resources import ResourceManager
        rm = ResourceManager.instance()
        for name in rm.pipeline_names:
            p = rm.get_pipeline(name)
            if p is pipeline:
                return name
        return None

    def _on_display_removed(self, display: "Display") -> None:
        display_id = display.tc_display_ptr

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
