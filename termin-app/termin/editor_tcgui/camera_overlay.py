"""Temporary tcgui projection of the toolkit-neutral editor-camera controller."""

from __future__ import annotations

from collections.abc import Callable

from tcbase import log
from tcgui.widgets.basic import IconButton
from termin.input import INPUT_SOURCE_EDITOR, INPUT_SOURCE_RUNTIME
from termin.scene import Entity, PythonComponent
from termin.ui_components import UIComponent


class TcguiEditorCameraOverlayProjection(PythonComponent):
    def __init__(self, controller, gizmo, request_render: Callable[[], None] | None) -> None:
        super().__init__(enabled=True)
        self.active_in_editor = True
        self._controller = controller
        self._gizmo = gizmo
        self._request_render = request_render
        self._buttons: dict[str, IconButton] = {}

    def start(self) -> None:
        self._bind()

    def on_scene_active(self) -> None:
        self._bind()

    def on_removed(self) -> None:
        self._controller.unbind_runtime()
        self._buttons.clear()

    def _bind(self) -> None:
        if self.entity is None:
            log.error("[TcguiEditorCameraOverlay] projection entity is unavailable")
            return
        ui = self.entity.get_component(UIComponent)
        if ui is None:
            log.error("[TcguiEditorCameraOverlay] UIComponent is unavailable")
            return
        camera = self.entity.parent.get_component_by_type("CameraComponent")
        self._controller.bind_runtime(
            camera=camera,
            gizmo=self._gizmo,
            request_render=self._request_render,
        )
        actions = {
            "colliders_btn": self._controller.toggle_colliders,
            "navmesh_btn": self._controller.toggle_navmesh,
            "wireframe_btn": self._controller.toggle_wireframe,
            "ortho_btn": self._controller.toggle_projection,
            "gizmo_orientation_btn": self._controller.toggle_gizmo_orientation,
        }
        self._buttons.clear()
        for name, action in actions.items():
            button = ui.find(name)
            if not isinstance(button, IconButton):
                log.error(f"[TcguiEditorCameraOverlay] missing IconButton {name!r}")
                continue
            button.on_click = lambda next_action=action: self._invoke(next_action)
            self._buttons[name] = button
        self._sync_buttons()

    def _invoke(self, action: Callable[[], None]) -> None:
        action()
        self._sync_buttons()

    def _sync_buttons(self) -> None:
        state = self._controller
        values = {
            "colliders_btn": state.colliders_enabled,
            "navmesh_btn": state.navmesh_enabled,
            "wireframe_btn": state.wireframe_enabled,
            "ortho_btn": state.ortho_enabled,
            "gizmo_orientation_btn": state.gizmo_world_orientation_enabled,
        }
        for name, active in values.items():
            button = self._buttons.get(name)
            if button is not None:
                button.active = active
        gizmo = self._buttons.get("gizmo_orientation_btn")
        if gizmo is not None:
            gizmo.icon = "G" if state.gizmo_world_orientation_enabled else "L"
            gizmo.tooltip = (
                "Transform Gizmo: Global"
                if state.gizmo_world_orientation_enabled
                else "Transform Gizmo: Local"
            )


def make_tcgui_camera_overlay_factory(gizmo, request_render: Callable[[], None] | None):
    """Return the comparison-frontend factory injected into editor_core."""

    def create(_camera_entity: Entity, controller) -> Entity:
        overlay = Entity(name="editor_ui")
        overlay.layer = 1
        overlay.add_component_by_name("UIComponent")
        ui = overlay.get_component_by_type("UIComponent")
        ui.active_in_editor = True
        ui.input_source_mask = INPUT_SOURCE_RUNTIME | INPUT_SOURCE_EDITOR
        ui.set_ui_layout_by_name("editor_camera_ui")
        overlay.add_component(
            TcguiEditorCameraOverlayProjection(controller, gizmo, request_render)
        )
        return overlay

    return create


__all__ = ["TcguiEditorCameraOverlayProjection", "make_tcgui_camera_overlay_factory"]
