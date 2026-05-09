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

        # Python-side GC anchor for per-display DisplayInputRouter instances —
        # the surface only holds a raw ptr, so if the router is GC'd the
        # ptr becomes dangling. View deferentially relies on this dict
        # staying alive through the display's lifetime.
        self._display_input_managers: dict[int, object] = {}

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
    # Display input managers — GC anchor + mode dispatch
    # ------------------------------------------------------------------

    @property
    def display_input_managers(self) -> dict[int, object]:
        """Live GC-anchor dict: ``display_id → DisplayInputRouter``."""
        return self._display_input_managers

    def drop_display_input_manager(self, display_id: int) -> None:
        self._display_input_managers.pop(display_id, None)

    def apply_display_input(
        self,
        display: "Display",
        input_mode: str,
        surface,
        on_editor_mode=None,
    ) -> None:
        """Install the appropriate input router on ``surface`` for ``input_mode``.

        - ``"none"``: surface is cleared, no router.
        - ``"simple"`` / ``"basic"``: creates ``DisplayInputRouter``, stashes
          it in the GC-anchor dict, and points the surface at its
          ``tc_input_manager_ptr``.
        - ``"editor"``: view handles it. The optional ``on_editor_mode``
          callback (``(display) -> None``) is invoked so hosts like the
          Qt editor can wire up editor-specific input.

        ``surface`` comes from the view — the model doesn't look it up
        itself because the Python `Display` subclass isn't always what
        ``RenderingManager`` returns (raw ``TcDisplay`` wrappers don't
        carry the subclass ``.surface``).
        """
        from termin.visualization.platform.input_manager import DisplayInputRouter

        display_id = display.tc_display_ptr

        self._display_input_managers.pop(display_id, None)

        if surface is not None:
            surface.set_input_manager(0)

        if input_mode == "none":
            return

        if input_mode in ("simple", "basic"):
            router = DisplayInputRouter(display_id)
            self._display_input_managers[display_id] = router
            if surface is not None:
                surface.set_input_manager(router.tc_input_manager_ptr)
            return

        if input_mode == "editor":
            if on_editor_mode is not None:
                on_editor_mode(display)
            return

    # ------------------------------------------------------------------
    # Iteration helpers
    # ------------------------------------------------------------------

    def _non_editor_displays(self) -> Iterator["Display"]:
        # Use scene_displays to skip editor displays
        return iter(self._manager.scene_displays)

    def is_scene_attached(self, scene: "Scene") -> bool:
        """True if this scene already has at least one non-editor viewport."""
        for display in self._non_editor_displays():
            for vp in display.viewports:
                vp_scene = vp.scene
                if vp_scene is not None and vp_scene.equal(scene):
                    return True
        return False

    def get_framegraph_debug_targets_info(self) -> list:
        """Return render targets that can be inspected by Framegraph Debugger.

        The debugger operates on pipelines, not viewport ownership. Viewport-
        owned render targets and standalone offscreen render targets are
        therefore exposed through the same target descriptor.
        """
        from termin.editor_core.framegraph_debugger_model import FramegraphDebugTarget

        result: list[FramegraphDebugTarget] = []
        owned_keys: set[tuple[int, int]] = set()

        for display in self._manager.displays:
            display_name = self._manager.get_display_name(display)
            for i, viewport in enumerate(display.viewports):
                viewport_name = viewport.name or f"Viewport {i}"
                render_target = viewport.render_target
                if render_target is None:
                    label = f"{display_name} / {viewport_name}"
                    result.append(FramegraphDebugTarget(
                        source=viewport,
                        label=label,
                        get_pipeline=lambda viewport=viewport: self._pipeline_for_viewport(viewport),
                    ))
                    continue

                owned_keys.add((render_target.index, render_target.generation))
                rt_name = render_target.name or "RenderTarget"
                if viewport.managed_by_scene_pipeline:
                    label = f"[{viewport.managed_by_scene_pipeline}] {viewport_name} / {rt_name}"
                else:
                    label = f"{display_name} / {viewport_name} / {rt_name}"
                result.append(FramegraphDebugTarget(
                    source=render_target,
                    label=label,
                    get_pipeline=lambda viewport=viewport, render_target=render_target:
                        self._pipeline_for_viewport_render_target(viewport, render_target),
                    get_resource_info=lambda resource_name, render_target=render_target:
                        self._render_target_output_resource_info(render_target, resource_name),
                ))

        for render_target in self._manager.standalone_render_targets:
            rt_name = render_target.name or "RenderTarget"
            result.append(FramegraphDebugTarget(
                source=render_target,
                label=f"RenderTarget / {rt_name}",
                get_pipeline=lambda render_target=render_target: render_target.pipeline,
                get_resource_info=lambda resource_name, render_target=render_target:
                    self._render_target_output_resource_info(render_target, resource_name),
            ))

        return result

    def _pipeline_for_viewport(self, viewport: "Viewport"):
        managed_by = viewport.managed_by_scene_pipeline
        if managed_by and viewport.scene is not None:
            from termin.visualization.core.scene import scene_render_mount
            return scene_render_mount(viewport.scene).get_pipeline(managed_by)
        render_target = viewport.render_target
        if render_target is not None:
            return render_target.pipeline
        return None

    def _pipeline_for_viewport_render_target(self, viewport: "Viewport", render_target):
        managed_by = viewport.managed_by_scene_pipeline
        if managed_by and viewport.scene is not None:
            from termin.visualization.core.scene import scene_render_mount
            return scene_render_mount(viewport.scene).get_pipeline(managed_by)
        return render_target.pipeline

    def _render_target_output_resource_info(self, render_target, resource_name: str) -> dict | None:
        return render_target.output_resource_info(resource_name)

    def remove_render_target(self, render_target, scene: "Scene | None" = None) -> None:
        """Remove a live render target and its scene config entry."""
        for display in self._manager.displays:
            for viewport in display.viewports:
                rt = viewport.render_target
                if rt is not None and rt.index == render_target.index and rt.generation == render_target.generation:
                    viewport.render_target = None
        if scene is not None:
            name = render_target.name or ""
            if name:
                self._remove_render_target_config_by_name(scene, name)
        self._manager.unregister_standalone_render_target(render_target)
        render_target.free()

    def _remove_render_target_config_by_name(self, scene: "Scene", name: str) -> None:
        from termin.visualization.core.scene import scene_render_mount

        rm = scene_render_mount(scene)
        for index in range(rm.render_target_config_count() - 1, -1, -1):
            config = rm.render_target_config_at(index)
            if config is not None and config.name == name:
                rm.remove_render_target_config(index)

    def _live_viewport_render_target_keys(self) -> set[tuple[int, int]]:
        keys: set[tuple[int, int]] = set()
        for display in self._manager.displays:
            for viewport in display.viewports:
                render_target = viewport.render_target
                if render_target is not None:
                    keys.add((render_target.index, render_target.generation))
        return keys

    def standalone_render_targets(self, render_targets) -> list:
        """Return render targets that are not owned by a live viewport."""
        owned_keys = self._live_viewport_render_target_keys()
        result = []
        for render_target in render_targets:
            if (render_target.index, render_target.generation) not in owned_keys:
                result.append(render_target)
        return result

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
            viewports_to_remove = [
                vp for vp in display.viewports
                if vp.scene is not None and vp.scene.equal(scene)
            ]
            for vp in viewports_to_remove:
                if vp.render_target is not None and vp.render_target.pipeline is not None:
                    vp.render_target.pipeline.destroy()
                state = self._manager.get_viewport_state(vp)
                if state is not None:
                    state.clear_all()
                self._manager.remove_viewport_state(vp)
                display.remove_viewport(vp)
                vp.destroy()

    # ------------------------------------------------------------------
    # Scene attach / detach
    # ------------------------------------------------------------------

    def find_viewport_config(
        self,
        scene: "Scene",
        viewport: "Viewport",
        display: "Display | None" = None,
    ):
        """Find the ViewportConfig inside scene that matches this viewport.

        Matches on (display_name, render_target_name) when the viewport
        has a render target. Falls back to (display_name, viewport.name).
        """
        from termin.visualization.core.scene import scene_render_mount

        if display is None:
            display = self._manager.get_display_for_viewport(viewport)
        if display is None:
            return None

        display_name = display.name or ""

        render_target = viewport.render_target
        render_target_name = render_target.name if render_target is not None else ""

        vp_name = viewport.name or ""
        configs = scene_render_mount(scene).viewport_configs

        if render_target_name:
            for config in configs:
                if config.display_name == display_name and config.render_target_name == render_target_name:
                    return config

        for config in configs:
            if config.display_name == display_name and config.name == vp_name:
                return config
        return None

    def attach_scene(
        self,
        scene: "Scene",
        setup_display_input=None,
    ) -> list:
        """Attach scene: delegates to RenderingManager, then asks view to
        configure input for each non-editor display.

        ``setup_display_input(display, input_mode)``: called once per
        non-editor display that received viewports, with the input mode
        from the first matching ViewportConfig. View creates the
        appropriate DisplayInputRouter (or whatever backend wants).
        """
        if self.is_scene_attached(scene):
            return []

        viewports = self._manager.attach_scene(scene)

        by_display: dict[int, list] = {}
        for viewport in viewports:
            display = self._manager.get_display_for_viewport(viewport)
            if display is None:
                continue
            config = self.find_viewport_config(scene, viewport, display)
            render_target = viewport.render_target
            if render_target is not None:
                viewport.scene = scene
                render_target.scene = scene
            if config is None:
                continue
            by_display.setdefault(display.tc_display_ptr, []).append(
                (viewport, config, display)
            )

        if setup_display_input is not None:
            for display_id, entries in by_display.items():
                if not entries:
                    continue
                if display_id == self._editor_display_ptr:
                    continue
                viewport, config, display = entries[0]
                setup_display_input(display, config.input_mode)

        return viewports

    def detach_scene(self, scene: "Scene") -> set[int]:
        """Detach scene: remove viewports, free unlocked render targets
        for the scene, then call manager.detach_scene.

        Returns the set of non-editor display_ptrs that were emptied by
        this detach — view can use that to drop per-display input
        managers or tabs.
        """
        displays_to_check: set[int] = set()
        for display in self._non_editor_displays():
            if display.viewports:
                displays_to_check.add(display.tc_display_ptr)

        self._manager.detach_scene_full(scene)

        emptied: set[int] = set()
        for display_ptr in displays_to_check:
            display = None
            for d in self._manager.displays:
                if d.tc_display_ptr == display_ptr:
                    display = d
                    break
            if display is not None and not display.viewports:
                emptied.add(display_ptr)

        return emptied

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
                vp_scene = viewport.scene
                if vp_scene is None or not vp_scene.equal(scene):
                    continue

                rt = viewport.render_target

                render_target_name = ""
                if rt is not None:
                    render_target_name = rt.name or ""

                rect = viewport.rect
                config = ViewportConfig()
                config.name = viewport.name or ""
                config.display_name = display.name
                config.render_target_name = render_target_name
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
        """Snapshot managed standalone render targets into ``scene.render_target_configs``."""
        from termin.visualization.core.render_target_config import RenderTargetConfig
        from termin.visualization.core.scene import scene_render_mount

        rm = scene_render_mount(scene)
        rm.clear_render_target_configs()

        for rt in self._manager.standalone_render_targets:
            rt_scene = rt.scene
            if rt_scene is None or not rt_scene.equal(scene):
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
            config.dynamic_resolution = bool(rt.dynamic_resolution)
            config.color_format = rt.color_format
            config.depth_format = rt.depth_format
            config.pipeline_uuid = pipeline_uuid
            config.pipeline_name = pipeline_name
            config.layer_mask = rt.layer_mask
            config.enabled = rt.enabled
            config.pipeline_params = dict(rt.pipeline_params)
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
