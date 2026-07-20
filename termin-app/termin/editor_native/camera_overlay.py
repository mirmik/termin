"""Native viewport projection of editor-camera mode state and actions."""

from __future__ import annotations

from collections.abc import Callable
import logging

from termin.gui_native import IconButton, UiScriptLoader
from termin.stdlib import stdlib_root


_logger = logging.getLogger(__name__)
_OVERLAY_NAME = "editor-camera"
_SCRIPT_PATH = stdlib_root() / "uiscript/editor_camera_ui.uiscript"


class NativeEditorCameraOverlayProjection:
    """Own the native widgets and bind them to a toolkit-neutral controller."""

    def __init__(self, viewport, loaded, controller) -> None:
        self._viewport = viewport
        self._loaded = loaded
        self._controller = controller
        self._buttons: dict[str, IconButton] = {}
        self._runtime_bound = False
        self._closed = False

    @classmethod
    def create(cls, viewport) -> "NativeEditorCameraOverlayProjection":
        camera = viewport.camera
        if camera is None or camera.entity is None:
            raise RuntimeError("native editor camera is unavailable for its overlay")

        from termin.editor_core.editor_camera_ui_controller import (
            EditorCameraUIController,
        )

        controller = camera.entity.get_component(EditorCameraUIController)
        if controller is None:
            raise RuntimeError("editor camera has no EditorCameraUIController")

        loaded = UiScriptLoader().load(_SCRIPT_PATH, document=viewport.document)
        try:
            viewport.install_overlay(_OVERLAY_NAME, loaded)
            projection = cls(viewport, loaded, controller)
            projection._bind_buttons()
            projection.rebind_camera()
            return projection
        except Exception:
            _logger.exception("Failed to create native editor-camera overlay")
            if not viewport.remove_overlay(_OVERLAY_NAME):
                loaded.close()
            raise

    def _bind_buttons(self) -> None:
        actions = {
            "colliders_btn": lambda: self._controller.toggle_colliders(),
            "navmesh_btn": lambda: self._controller.toggle_navmesh(),
            "wireframe_btn": lambda: self._controller.toggle_wireframe(),
            "ortho_btn": lambda: self._controller.toggle_projection(),
            "gizmo_orientation_btn": lambda: (
                self._controller.toggle_gizmo_orientation()
            ),
        }
        for name, action in actions.items():
            button = self._loaded.named(name)
            if not isinstance(button, IconButton):
                raise TypeError(f"editor-camera widget {name!r} is not an IconButton")
            button.connect_clicked(lambda next_action=action: self._invoke(next_action))
            self._buttons[name] = button

    def _invoke(self, action: Callable[[], None]) -> None:
        action()
        self.sync_buttons()

    def rebind_camera(self) -> None:
        """Rebind capabilities after the editor attachment changes scenes."""

        camera = self._viewport.camera
        if camera is None:
            raise RuntimeError("editor scene switch left the native viewport without a camera")
        if self._runtime_bound:
            self._controller.unbind_runtime()

        next_controller = camera.entity.get_component(type(self._controller))
        if next_controller is None:
            raise RuntimeError("new editor camera has no camera-mode controller")
        self._controller = next_controller
        self._controller.bind_runtime(
            camera=camera,
            gizmo=self._viewport.interaction.transform_gizmo,
            request_render=self._viewport._request_render,
        )
        self._runtime_bound = True
        self.sync_buttons()

    def sync_buttons(self) -> None:
        state = self._controller
        values = {
            "colliders_btn": state.colliders_enabled,
            "navmesh_btn": state.navmesh_enabled,
            "wireframe_btn": state.wireframe_enabled,
            "ortho_btn": state.ortho_enabled,
            "gizmo_orientation_btn": state.gizmo_world_orientation_enabled,
        }
        for name, active in values.items():
            self._buttons[name].active = active

        gizmo = self._buttons["gizmo_orientation_btn"]
        gizmo.set_icon("G" if state.gizmo_world_orientation_enabled else "L")
        gizmo.tooltip = (
            "Transform Gizmo: Global"
            if state.gizmo_world_orientation_enabled
            else "Transform Gizmo: Local"
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._runtime_bound:
            self._controller.unbind_runtime()
            self._runtime_bound = False
        self._buttons.clear()
        if not self._viewport.remove_overlay(_OVERLAY_NAME):
            _logger.error("Native editor-camera overlay was already detached")


__all__ = ["NativeEditorCameraOverlayProjection"]
