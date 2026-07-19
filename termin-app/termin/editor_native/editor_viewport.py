"""Native editor viewport composition and explicit render/input lifetime."""

from __future__ import annotations

from collections.abc import Callable
import logging

from termin.gui_native import Document, OverlayAnchor, Size, WidgetRef


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
        document: Document,
        widget,
        composition,
        root: WidgetRef,
        surface,
        display,
        attachment,
        interaction,
        input_manager,
        rendering_manager,
        request_render: Callable[[], None],
    ) -> None:
        self.document = document
        self.widget = widget
        self.composition = composition
        self.root = root
        self.surface = surface
        self.display = display
        self.attachment = attachment
        self.interaction = interaction
        self.input_manager = input_manager
        self.rendering_manager = rendering_manager
        self._request_render = request_render
        self._resize_connection = None
        self._ui_overlays: dict[str, object] = {}
        self._overlay_drawer: Callable[[], bool] | None = None
        self._closed = False
        from termin.editor_core.viewport_geometry_controller import (
            ViewportGeometryController,
        )

        geometry_widget = _ViewportGeometryWidget(widget.widget)
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

        from termin.display import Display, DisplayViewportHost, FBOSurface
        from termin.editor._editor_native import (
            EditorInteractionSystem,
            EditorViewportInputManager,
        )
        from termin.editor_core.editor_pipeline import make_editor_pipeline
        from termin.editor_core.editor_scene_attachment import EditorSceneAttachment

        composition = document.create_overlay_layout("native-editor-viewport-composition")
        root = composition.widget
        root.stable_id = "editor.viewport"
        root.preferred_size = Size(800.0, 600.0)
        widget = document.create_viewport3d()
        widget.widget.stable_id = "editor.viewport.surface"
        if not composition.add_child(widget.widget, OverlayAnchor.Fill):
            document.destroy_widget_recursive(root.handle)
            raise RuntimeError("native editor viewport composition rejected Viewport3D")
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
                rendering_manager=rendering_manager,
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
            widget.set_surface_host(DisplayViewportHost(surface, display))
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
            if root.alive:
                document.destroy_widget_recursive(root.handle)
            raise

        runtime = cls(
            document=document,
            widget=widget,
            composition=composition,
            root=root,
            surface=surface,
            display=display,
            attachment=attachment,
            interaction=interaction,
            input_manager=input_manager,
            rendering_manager=rendering_manager,
            request_render=request_render,
        )
        runtime._resize_connection = widget.connect_before_resize(runtime._on_before_resize)
        return runtime

    @property
    def camera(self):
        return self.attachment.camera

    @property
    def overlay_names(self) -> tuple[str, ...]:
        return tuple(self._ui_overlays)

    def install_overlay(self, name: str, loaded_document) -> None:
        """Attach one named loaded gui-native document above the viewport."""

        if self._closed:
            raise RuntimeError("native editor viewport is closed")
        if not name or name in self._ui_overlays:
            raise ValueError(f"viewport overlay name is empty or already installed: {name!r}")
        if loaded_document.document is not self.document:
            raise ValueError("viewport overlay belongs to another native Document")
        overlay_root = loaded_document.root.widget
        if not self.document.remove_root(overlay_root.handle):
            raise ValueError("viewport overlay must be a loaded document root")
        if not self.composition.add_child(overlay_root, OverlayAnchor.Fill):
            if not self.document.add_root(overlay_root.handle):
                _logger.error("Failed to restore rejected viewport overlay root '%s'", name)
            raise RuntimeError(f"native viewport composition rejected overlay {name!r}")
        self._ui_overlays[name] = loaded_document
        self._request_render()

    def remove_overlay(self, name: str) -> bool:
        loaded_document = self._ui_overlays.pop(name, None)
        if loaded_document is None:
            return False
        loaded_document.close()
        self._request_render()
        return True

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
            self._update_gizmo_screen_scale()
        self._request_render()

    def _update_gizmo_screen_scale(self) -> None:
        """Keep the transform gizmo at the legacy camera-relative scale."""
        transform_gizmo = self.interaction.transform_gizmo
        if transform_gizmo is None or not transform_gizmo.target.valid():
            return
        camera = self.camera
        if camera is None or camera.entity is None:
            return

        camera_position = camera.entity.transform.global_pose().lin
        gizmo_position = transform_gizmo.target.transform.global_pose().lin
        distance = (camera_position - gizmo_position).norm()
        transform_gizmo.set_screen_scale(max(0.1, distance * 0.1))

    def after_render(self) -> None:
        self.interaction.after_render()
        if self._overlay_drawer is not None and self._overlay_drawer():
            self._request_render()

    def rebind_input_manager(self) -> None:
        """Attach editor input to the viewport recreated by a scene switch."""
        viewport = self.attachment.viewport
        if viewport is None:
            raise RuntimeError("editor scene attachment has no viewport for input binding")
        index, generation = viewport._viewport_handle()
        if not self.input_manager.rebind(index, generation, self.display.tc_display_ptr):
            raise RuntimeError("failed to rebind editor viewport input manager")

    def _on_before_resize(self, _previous, _next) -> None:
        self._request_render()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True

        from termin.editor._editor_native import EditorInteractionSystem

        self._overlay_drawer = None
        while self._ui_overlays:
            self.remove_overlay(next(iter(self._ui_overlays)))
        if self._resize_connection is not None:
            if not self.widget.disconnect_before_resize(self._resize_connection):
                _logger.error("Native editor viewport resize handler was already detached")
            self._resize_connection = None
        self.interaction.clear_callbacks()
        self.widget.detach_surface()
        self.input_manager.detach()
        self.attachment.close()
        self.rendering_manager.remove_editor_display(self.display)
        self.display.destroy()
        self.surface.close()
        if EditorInteractionSystem.instance() is self.interaction:
            EditorInteractionSystem.set_instance(None)
        if self.root.alive:
            self.document.destroy_widget_recursive(self.root.handle)


__all__ = ["NativeEditorViewport"]
