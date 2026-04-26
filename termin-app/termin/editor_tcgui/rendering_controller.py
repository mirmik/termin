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
    from tgfx._tgfx_native import Tgfx2Context


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
        viewport_list_widget,
        offscreen_context: "OffscreenContext",
        ctx: "Tgfx2Context",
        get_scene: Callable[[], "Scene | None"] | None = None,
        make_editor_pipeline: Callable[[], "RenderPipeline"] | None = None,
        on_request_update: Callable[[], None] | None = None,
        on_rendering_changed: Callable[[], None] | None = None,
        on_display_selected: Callable[["Display | None"], None] | None = None,
        on_viewport_selected: Callable[["Viewport | None"], None] | None = None,
        on_entity_selected: Callable[[object], None] | None = None,
        on_render_target_selected: Callable[[object], None] | None = None,
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
        self._on_display_selected = on_display_selected
        self._on_viewport_selected = on_viewport_selected
        self._on_entity_selected = on_entity_selected
        self._on_render_target_selected = on_render_target_selected

        self._display_surfaces: dict[int, object] = {}
        self._display_viewports: dict[int, object] = {}  # display_id -> Viewport3D
        self._viewport_list = viewport_list_widget
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

        self._connect_viewport_list_signals()

    def _connect_viewport_list_signals(self) -> None:
        vl = self._viewport_list
        vl.display_selected.connect(self._on_display_selected_from_list)
        vl.viewport_selected.connect(self._on_viewport_selected_from_list)
        vl.entity_selected.connect(self._on_entity_selected_from_list)
        vl.render_target_selected.connect(self._on_render_target_selected_from_list)
        vl.display_add_requested.connect(self._on_add_display_requested)
        vl.viewport_add_requested.connect(self._on_add_viewport_requested)
        vl.display_remove_requested.connect(self._on_remove_display_requested)
        vl.viewport_remove_requested.connect(self._on_remove_viewport_requested)
        vl.render_target_add_requested.connect(self._on_add_render_target_requested)
        vl.render_target_remove_requested.connect(self._on_remove_render_target_requested)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def offscreen_context(self) -> "OffscreenContext":
        return self._offscreen_context

    @property
    def displays(self) -> list["Display"]:
        return self._manager.displays

    @property
    def editor_display(self) -> "Display | None":
        ptr = self._model.editor_display_ptr
        if ptr is None:
            return None
        for display in self._manager.displays:
            if display.tc_display_ptr == ptr:
                return display
        return None

    # ------------------------------------------------------------------
    # Editor display — backed by RenderingModel
    # ------------------------------------------------------------------

    @property
    def _editor_display_ptr(self) -> int | None:
        return self._model.editor_display_ptr

    @_editor_display_ptr.setter
    def _editor_display_ptr(self, value: int | None) -> None:
        self._model.set_editor_display_ptr(value)

    @property
    def _selected_display(self) -> "Display | None":
        return self._model.selected_display

    @_selected_display.setter
    def _selected_display(self, value: "Display | None") -> None:
        self._model.set_selected_display(value)

    @property
    def _selected_viewport(self) -> "Viewport | None":
        return self._model.selected_viewport

    @_selected_viewport.setter
    def _selected_viewport(self, value: "Viewport | None") -> None:
        self._model.set_selected_viewport(value)

    @property
    def _display_input_managers(self) -> dict[int, object]:
        return self._model.display_input_managers

    def set_editor_display_ptr(self, ptr: int) -> None:
        self._model.set_editor_display_ptr(ptr)

    def is_editor_display(self, display: "Display") -> bool:
        return display.tc_display_ptr == self._editor_display_ptr

    def set_center_tabs(self, tabs) -> None:
        self._center_tabs = tabs

    def add_display(self, display: "Display", name: str | None = None) -> None:
        """Register an externally-created display with the manager and viewport list."""
        if display in self._manager.displays:
            return
        display_name = name or display.name or ""
        self._manager.add_display(display, display_name)
        self._viewport_list.add_display(display, self._manager.get_display_name(display))

    def remove_display(self, display: "Display") -> None:
        if display not in self._manager.displays:
            return
        self._manager.remove_display(display)

    def _refresh_render_targets(self) -> None:
        """Refresh render target list in the viewport list widget."""
        from termin.render_framework._render_framework_native import render_target_pool_list
        self._viewport_list.set_render_targets(render_target_pool_list())

    def sync_viewport_list_from_manager(self) -> None:
        """Push current manager state (displays + render targets) into the widget."""
        self._viewport_list.set_displays(self._manager.displays)
        self._refresh_render_targets()

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

        self._viewport_list.add_display(display, name)
        return display

    # ------------------------------------------------------------------
    # Scene management
    # ------------------------------------------------------------------

    def attach_scene(self, scene: "Scene") -> list["Viewport"]:
        """Attach scene using its viewport configuration.

        Creates displays via factory, mounts viewports via the model,
        and asks the view to configure input per non-editor display.
        """
        viewports = self._model.attach_scene(
            scene,
            setup_display_input=self._setup_display_input,
        )

        self._request_update()
        self._notify_rendering_changed()

        return viewports

    def detach_scene(self, scene: "Scene") -> None:
        """Detach scene and clean up per-display input managers."""
        emptied = self._model.detach_scene(scene)

        for display_ptr in emptied:
            self._display_input_managers.pop(display_ptr, None)

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
        """Set up input manager for a display (delegates to RenderingModel).

        The raw ``TcDisplay`` returned by ``RenderingManager`` doesn't carry
        the Python ``.surface`` attribute, so we look the FBOSurface up
        through the dict the factory populates at create time and pass it
        in explicitly.
        """
        display_id = display.tc_display_ptr
        surface = self._display_surfaces.get(display_id)
        # Editor mode here is a no-op — the editor display has its input
        # handling wired up by ``EditorWindowTcgui._attach_editor_input_router``
        # directly; non-editor displays never carry input_mode="editor".
        self._model.apply_display_input(display, input_mode, surface)

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
        """Refresh viewport list after scene load.

        Scene-owned viewport creation happens when the editor explicitly
        attaches the scene to rendering after load/switch.
        """
        self.sync_viewport_list_from_manager()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

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

        self._viewport_list.remove_display(display)

        if self._selected_display is display:
            self._selected_display = None

        self._notify_rendering_changed()

    # ------------------------------------------------------------------
    # Viewport list signal handlers
    # ------------------------------------------------------------------

    def _on_display_selected_from_list(self, display) -> None:
        self._selected_display = display
        if self._on_display_selected is not None:
            self._on_display_selected(display)

    def _on_viewport_selected_from_list(self, viewport) -> None:
        self._selected_viewport = viewport
        if self._on_viewport_selected is not None:
            self._on_viewport_selected(viewport)

    def _on_entity_selected_from_list(self, entity) -> None:
        if self._on_entity_selected is not None:
            self._on_entity_selected(entity)

    def _on_render_target_selected_from_list(self, render_target) -> None:
        if self._on_render_target_selected is not None:
            self._on_render_target_selected(render_target)

    # ------------------------------------------------------------------
    # Add/Remove display / viewport / render target
    # ------------------------------------------------------------------

    def _on_add_display_requested(self) -> None:
        existing_names = {self._manager.get_display_name(d) for d in self._manager.displays}
        idx = 0
        while True:
            name = f"Display {idx}"
            if name not in existing_names:
                break
            idx += 1

        display = self._create_display_for_name(name)
        if display is None:
            return

        self._manager.add_display(display, name)
        self._viewport_list.add_display(display, name)
        self._request_update()
        self._notify_rendering_changed()

    def _on_add_viewport_requested(self, display: "Display") -> None:
        scene = self._get_scene() if self._get_scene is not None else None
        if scene is None:
            return

        from termin.visualization.core.camera import CameraComponent

        camera = None
        for entity in scene.entities:
            cam = entity.get_component(CameraComponent)
            if cam is not None:
                camera = cam
                break
        if camera is None:
            log.warn("No camera in scene — cannot create viewport")
            return

        display.create_viewport(scene=scene, camera=camera, rect=(0.0, 0.0, 1.0, 1.0))
        self._viewport_list.refresh()
        self._request_update()
        self._notify_rendering_changed()

    def _on_remove_display_requested(self, display: "Display") -> None:
        if display not in self._manager.displays:
            return
        self._manager.remove_display(display)
        self._request_update()

    def _on_remove_viewport_requested(self, viewport: "Viewport") -> None:
        display = self._manager.get_display_for_viewport(viewport)
        if display is not None:
            display.remove_viewport(viewport)
        if self._selected_viewport is viewport:
            self._selected_viewport = None
        self._viewport_list.refresh()
        self._request_update()
        self._notify_rendering_changed()

    def _on_add_render_target_requested(self) -> None:
        from termin.render_framework._render_framework_native import render_target_new
        render_target_new("RenderTarget")
        self._refresh_render_targets()

    def _on_remove_render_target_requested(self, render_target) -> None:
        render_target.free()
        self._refresh_render_targets()

    def _request_update(self) -> None:
        if self._on_request_update is not None:
            self._on_request_update()

    def _notify_rendering_changed(self) -> None:
        if self._on_rendering_changed is not None:
            self._on_rendering_changed()
