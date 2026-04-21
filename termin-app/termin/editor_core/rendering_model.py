"""RenderingModel — UI-agnostic display/viewport state and config sync.

Owns:
- a reference to the RenderingManager singleton
- the "editor display" pointer (a non-serialized display the editor uses
  for its main viewport)
- the offscreen GL context (needed before destroying GPU resources)

Provides UI-agnostic operations that were previously duplicated between
Qt and tcgui rendering controllers:
- ``remove_viewports_for_scene`` — scoped cleanup on scene unload
- ``sync_viewport_configs_to_scene`` / ``sync_render_target_configs_to_scene``
  — snapshot current state into Scene before save
- ``is_scene_attached`` — whether the scene already has non-editor viewports

Later phases will fold selection state, attach/detach, and input-mode
routing into the same model.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Iterator

from termin.editor_core.signal import Signal

if TYPE_CHECKING:
    from termin.visualization.core.display import Display
    from termin.visualization.core.scene import Scene
    from termin.visualization.core.viewport import Viewport
    from termin.visualization.core.render_pipeline import RenderPipeline
    from termin._native.render import RenderingManager


class RenderingModel:
    def __init__(self, manager: "RenderingManager", offscreen_context=None):
        self._manager = manager
        self._offscreen_context = offscreen_context
        self._editor_display_ptr: int | None = None

        self._selected_display: "Display | None" = None
        self._selected_viewport: "Viewport | None" = None

        self.changed = Signal()
        self.selection_changed = Signal()

    @property
    def manager(self) -> "RenderingManager":
        return self._manager

    @property
    def editor_display_ptr(self) -> int | None:
        return self._editor_display_ptr

    def set_editor_display_ptr(self, ptr: int | None) -> None:
        self._editor_display_ptr = ptr

    @property
    def offscreen_context(self):
        return self._offscreen_context

    def set_offscreen_context(self, ctx) -> None:
        self._offscreen_context = ctx

    # ------------------------------------------------------------------
    # Selection state (display / viewport)
    # ------------------------------------------------------------------

    @property
    def selected_display(self) -> "Display | None":
        return self._selected_display

    @property
    def selected_viewport(self) -> "Viewport | None":
        return self._selected_viewport

    def set_selected_display(self, display: "Display | None") -> None:
        if self._selected_display is display:
            return
        self._selected_display = display
        self.selection_changed.emit(self)

    def set_selected_viewport(self, viewport: "Viewport | None") -> None:
        if self._selected_viewport is viewport:
            return
        self._selected_viewport = viewport
        self.selection_changed.emit(self)

    def set_selection(
        self,
        display: "Display | None",
        viewport: "Viewport | None",
    ) -> None:
        """Set both in one shot; emits ``selection_changed`` once if anything differs."""
        if self._selected_display is display and self._selected_viewport is viewport:
            return
        self._selected_display = display
        self._selected_viewport = viewport
        self.selection_changed.emit(self)

    def clear_selection(self) -> None:
        self.set_selection(None, None)

    # ------------------------------------------------------------------
    # Iteration helpers
    # ------------------------------------------------------------------

    def _non_editor_displays(self) -> Iterator["Display"]:
        for display in self._manager.displays:
            if display.tc_display_ptr != self._editor_display_ptr:
                yield display

    def is_scene_attached(self, scene: "Scene") -> bool:
        """True if this scene already has at least one non-editor viewport."""
        for display in self._non_editor_displays():
            for vp in display.viewports:
                if vp.scene is scene:
                    return True
        return False

    # ------------------------------------------------------------------
    # Viewport cleanup
    # ------------------------------------------------------------------

    def remove_viewports_for_scene(self, scene: "Scene") -> None:
        """Remove all viewports that belong to ``scene``.

        Editor display is skipped — its viewport is managed by
        EditorSceneAttachment. GL resources are cleared on the offscreen
        context first so deletes don't crash on a foreign context.
        """
        if self._offscreen_context is not None:
            self._offscreen_context.make_current()

        for display in self._non_editor_displays():
            viewports_to_remove = [vp for vp in display.viewports if vp.scene is scene]
            for vp in viewports_to_remove:
                if vp.pipeline is not None:
                    vp.pipeline.destroy()
                state = self._manager.get_viewport_state(vp)
                if state is not None:
                    state.clear_all()
                self._manager.remove_viewport_state(vp)
                display.remove_viewport(vp)

    # ------------------------------------------------------------------
    # Config sync — save state into Scene for serialization
    # ------------------------------------------------------------------

    def sync_viewport_configs_to_scene(self, scene: "Scene") -> None:
        """Snapshot this scene's viewports into ``scene.viewport_configs``."""
        from termin.visualization.core.viewport_config import ViewportConfig
        from termin.visualization.core.scene import scene_render_mount

        rm = scene_render_mount(scene)
        rm.clear_viewport_configs()

        for display in self._non_editor_displays():
            for viewport in display.viewports:
                if viewport.scene is not scene:
                    continue

                rt = viewport.render_target
                rt_name = rt.name if rt is not None else ""

                camera_uuid = ""
                if viewport.camera is not None and viewport.camera.entity is not None:
                    camera_uuid = viewport.camera.entity.uuid

                rect = viewport.rect
                config = ViewportConfig()
                config.name = viewport.name or ""
                config.display_name = display.name
                config.render_target_name = rt_name
                config.camera_uuid = camera_uuid
                config.region_x = rect[0]
                config.region_y = rect[1]
                config.region_w = rect[2]
                config.region_h = rect[3]
                config.depth = viewport.depth
                config.input_mode = viewport.input_mode
                config.block_input_in_editor = viewport.block_input_in_editor
                config.enabled = viewport.enabled
                rm.add_viewport_config(config)

    def sync_render_target_configs_to_scene(self, scene: "Scene") -> None:
        """Snapshot the render target pool into ``scene.render_target_configs``."""
        from termin.render_framework._render_framework_native import render_target_pool_list
        from termin.visualization.core.render_target_config import RenderTargetConfig
        from termin.visualization.core.scene import scene_render_mount

        rm = scene_render_mount(scene)
        rm.clear_render_target_configs()

        for rt in render_target_pool_list():
            if rt.locked:
                continue

            camera_uuid = ""
            if rt.camera is not None and rt.camera.entity is not None:
                camera_uuid = rt.camera.entity.uuid

            pipeline_uuid = ""
            pipeline_name = ""
            if rt.pipeline is not None:
                uuid = self._resolve_pipeline_uuid(rt.pipeline)
                pipeline_uuid = uuid or ""
                if rt.pipeline.name:
                    pipeline_name = rt.pipeline.name

            config = RenderTargetConfig()
            config.name = rt.name or ""
            config.camera_uuid = camera_uuid
            config.width = rt.width
            config.height = rt.height
            config.pipeline_uuid = pipeline_uuid
            config.pipeline_name = pipeline_name
            config.layer_mask = rt.layer_mask
            config.enabled = rt.enabled
            rm.add_render_target_config(config)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_pipeline_uuid(self, pipeline: "RenderPipeline") -> str | None:
        """Get the asset UUID of a live pipeline object, or None."""
        from termin.assets.resources import ResourceManager

        if not pipeline.name:
            return None
        rm = ResourceManager.instance()
        asset = rm.get_pipeline_asset(pipeline.name)
        if asset is not None:
            return asset.uuid
        return None
