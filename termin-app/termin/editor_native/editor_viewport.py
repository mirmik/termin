"""Native editor viewport composition and explicit render/input lifetime."""

from __future__ import annotations

from collections.abc import Callable
import logging

from termin.gui_native import Document, Size, WidgetRef


_logger = logging.getLogger(__name__)


class _ViewportGeometryWidget:
    """Expose native widget bounds through the legacy-neutral geometry shape."""

    def __init__(self, widget: WidgetRef) -> None:
        self._widget = widget

    @property
    def x(self) -> float:
        return float(self._widget.bounds.x)

    @property
    def y(self) -> float:
        return float(self._widget.bounds.y)

    @property
    def width(self) -> float:
        return float(self._widget.bounds.width)

    @property
    def height(self) -> float:
        return float(self._widget.bounds.height)


class NativeEditorViewport:
    """Own one native ``Viewport3D`` and its editor rendering bridge."""

    def __init__(
        self,
        *,
        widget,
        root: WidgetRef,
        surface,
        display,
        attachment,
        interaction,
        input_manager,
        input_router,
        rendering_manager,
        request_render: Callable[[], None],
    ) -> None:
        self.widget = widget
        self.root = root
        self.surface = surface
        self.display = display
        self.attachment = attachment
        self.interaction = interaction
        self.input_manager = input_manager
        self.input_router = input_router
        self.rendering_manager = rendering_manager
        self._request_render = request_render
        self._resize_connection = None
        self._overlay_drawer: Callable[[], bool] | None = None
        self._closed = False
        from termin.editor_core.viewport_geometry_controller import (
            ViewportGeometryController,
        )

        geometry_widget = _ViewportGeometryWidget(root)
        self.geometry = ViewportGeometryController(
            get_camera=lambda: self.camera,
            get_viewport_widget=lambda: geometry_widget,
            get_interaction_system=lambda: self.interaction,
            get_editor_display=lambda: self.display,
            get_scene_tree_controller=lambda: None,
        )

    @classmethod
    def create(
        cls,
        document: Document,
        parent: WidgetRef,
        *,
        device,
        rendering_manager,
        scene,
        request_render: Callable[[], None],
    ) -> "NativeEditorViewport":
        """Create and connect the complete editor viewport runtime chain."""

        from termin.display import Display, DisplayInputRouter, FBOSurface
        from termin.editor._editor_native import (
            EditorInteractionSystem,
            EditorViewportInputManager,
        )
        from termin.editor_core.editor_pipeline import make_editor_pipeline
        from termin.editor_core.editor_scene_attachment import EditorSceneAttachment

        widget = document.create_viewport3d()
        root = widget.widget
        root.stable_id = "editor.viewport"
        root.preferred_size = Size(800.0, 600.0)
        parent.add_stretch_child(root)

        surface = None
        display = None
        attachment = None
        interaction = None
        registered_display = False
        try:
            surface = FBOSurface(device, 800, 600)
            if not surface.is_valid():
                raise RuntimeError("native editor FBO surface is invalid")

            display = Display(
                surface=surface,
                name="Editor",
                editor_only=True,
            )
            interaction = EditorInteractionSystem()
            EditorInteractionSystem.set_instance(interaction)

            rendering_manager.add_editor_display(display)
            registered_display = True
            attachment = EditorSceneAttachment(
                display=display,
                rendering_controller=None,
                make_editor_pipeline=make_editor_pipeline,
            )
            attachment.attach(scene, restore_state=False)
            viewport = attachment.viewport
            if viewport is None:
                raise RuntimeError("editor scene attachment did not create a viewport")

            viewport_index, viewport_generation = viewport._viewport_handle()
            input_manager = EditorViewportInputManager(
                viewport_index,
                viewport_generation,
                display.tc_display_ptr,
            )
            input_router = DisplayInputRouter(display.tc_display_ptr)
            surface.set_input_manager(input_router.tc_input_manager_ptr)
            widget.set_surface_host(surface)
        except Exception:
            _logger.exception("Native editor viewport creation failed")
            if attachment is not None:
                try:
                    attachment.close(save_state=False)
                except Exception:
                    _logger.exception("Failed to close partial editor scene attachment")
            if registered_display and display is not None:
                rendering_manager.remove_editor_display(display)
            if display is not None:
                display.destroy()
            if surface is not None:
                surface.close()
            if interaction is not None:
                EditorInteractionSystem.set_instance(None)
            raise

        runtime = cls(
            widget=widget,
            root=root,
            surface=surface,
            display=display,
            attachment=attachment,
            interaction=interaction,
            input_manager=input_manager,
            input_router=input_router,
            rendering_manager=rendering_manager,
            request_render=request_render,
        )
        runtime._resize_connection = widget.connect_before_resize(runtime._on_before_resize)
        return runtime

    @property
    def camera(self):
        return self.attachment.camera

    def configure_interaction(
        self,
        *,
        on_selection_changed: Callable[[object], None],
        on_hover_changed: Callable[[object], None],
        on_entity_click: Callable[[object], bool],
        on_pointer: Callable[[object], bool],
        on_key: Callable[[object], object],
        on_transform_end: Callable[[object, object], None] | None = None,
        draw_overlays: Callable[[], bool] | None = None,
    ) -> None:
        self.interaction.selection.on_selection_changed = on_selection_changed
        self.interaction.selection.on_hover_changed = on_hover_changed
        self.interaction.on_request_update = self._request_render
        self.interaction.on_entity_click = on_entity_click
        self.interaction.on_viewport_pointer_event = on_pointer
        self.interaction.on_key = on_key
        self.interaction.on_transform_end = on_transform_end
        self._overlay_drawer = draw_overlays

    def select_scene_object(self, obj: object | None, *, active_tools: int = 0) -> None:
        from termin.scene import Entity

        if isinstance(obj, Entity) and obj.valid():
            self.interaction.selection.select(obj)
        else:
            self.interaction.selection.clear()
        self.sync_gizmo_target(active_tools)

    def sync_gizmo_target(self, active_tools: int) -> None:
        selected = self.interaction.selection.selected
        if active_tools > 0 or selected is None or not selected.valid():
            self.interaction.set_gizmo_target(None)
        else:
            self.interaction.set_gizmo_target(selected)
        self._request_render()

    def after_render(self) -> None:
        self.interaction.after_render()
        if self._overlay_drawer is not None and self._overlay_drawer():
            self._request_render()

    def _on_before_resize(self, _previous, _next) -> None:
        self._request_render()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True

        from termin.editor._editor_native import EditorInteractionSystem

        self._overlay_drawer = None
        self.interaction.clear_callbacks()
        self.widget.detach_surface()
        self.surface.set_input_manager(0)
        self.attachment.close()
        self.rendering_manager.remove_editor_display(self.display)
        self.display.destroy()
        self.surface.close()
        if EditorInteractionSystem.instance() is self.interaction:
            EditorInteractionSystem.set_instance(None)


__all__ = ["NativeEditorViewport"]
