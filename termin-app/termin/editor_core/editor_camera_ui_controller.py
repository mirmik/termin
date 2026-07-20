"""Serializable, toolkit-neutral editor-camera mode state and actions."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from tcbase import log
from termin.inspect import InspectField
from termin.render import RENDER_CATEGORY_COLLIDERS, RENDER_CATEGORY_NAVMESH
from termin.scene import PythonComponent

if TYPE_CHECKING:
    from termin.render_components.camera import CameraComponent


class EditorCameraUIController(PythonComponent):
    """Own camera-mode state while frontends own widgets and bindings."""

    component_category = "Editor/Internal"
    inspect_fields = {
        "colliders_enabled": InspectField(
            path="colliders_enabled", kind="bool", is_serializable=True, is_inspectable=True
        ),
        "wireframe_enabled": InspectField(
            path="wireframe_enabled", kind="bool", is_serializable=True, is_inspectable=True
        ),
        "navmesh_enabled": InspectField(
            path="navmesh_enabled", kind="bool", is_serializable=True, is_inspectable=True
        ),
        "ortho_enabled": InspectField(
            path="ortho_enabled", kind="bool", is_serializable=True, is_inspectable=True
        ),
        "gizmo_world_orientation_enabled": InspectField(
            path="gizmo_world_orientation_enabled",
            kind="bool",
            is_serializable=True,
            is_inspectable=True,
        ),
    }

    def __init__(self) -> None:
        super().__init__(enabled=True)
        self.active_in_editor = True
        self.colliders_enabled = False
        self.navmesh_enabled = True
        self.wireframe_enabled = False
        self.ortho_enabled = False
        self.gizmo_world_orientation_enabled = False
        self._camera: CameraComponent | None = None
        self._gizmo = None
        self._request_render: Callable[[], None] | None = None

    @property
    def camera(self) -> CameraComponent | None:
        return self._camera

    @property
    def gizmo_orientation_mode(self) -> str:
        return "world" if self.gizmo_world_orientation_enabled else "local"

    def bind_runtime(
        self,
        *,
        camera: CameraComponent | None,
        gizmo,
        request_render: Callable[[], None] | None,
    ) -> bool:
        """Inject frontend/runtime capabilities and apply serialized state."""

        if camera is None:
            log.error("[EditorCameraUIController] camera capability is unavailable")
        if gizmo is None:
            log.error("[EditorCameraUIController] transform gizmo capability is unavailable")
        if request_render is None:
            log.error("[EditorCameraUIController] render-update callback is unavailable")
        self._camera = camera
        self._gizmo = gizmo
        self._request_render = request_render
        self.resync()
        return camera is not None and gizmo is not None and request_render is not None

    def unbind_runtime(self) -> None:
        self._camera = None
        self._gizmo = None
        self._request_render = None

    def resync(self) -> None:
        """Apply all five persisted modes to currently injected capabilities."""

        self._set_render_category(RENDER_CATEGORY_COLLIDERS, self.colliders_enabled)
        self._set_render_category(RENDER_CATEGORY_NAVMESH, self.navmesh_enabled)
        self._apply_wireframe()
        if self._camera is None:
            log.error("[EditorCameraUIController] cannot apply projection without camera")
        else:
            self._camera.projection_type = (
                "orthographic" if self.ortho_enabled else "perspective"
            )
        if self._gizmo is None:
            log.error("[EditorCameraUIController] cannot apply orientation without transform gizmo")
        else:
            self._gizmo.set_orientation_mode(self.gizmo_orientation_mode)

    def toggle_colliders(self) -> None:
        self.colliders_enabled = not self.colliders_enabled
        self._set_render_category(RENDER_CATEGORY_COLLIDERS, self.colliders_enabled)
        self._request_update()

    def toggle_navmesh(self) -> None:
        self.navmesh_enabled = not self.navmesh_enabled
        self._set_render_category(RENDER_CATEGORY_NAVMESH, self.navmesh_enabled)
        self._request_update()

    def toggle_wireframe(self) -> None:
        self.wireframe_enabled = not self.wireframe_enabled
        self._apply_wireframe()
        self._request_update()

    def toggle_projection(self) -> None:
        self.ortho_enabled = not self.ortho_enabled
        if self._camera is None:
            log.error("[EditorCameraUIController] cannot toggle projection without camera")
        else:
            self._camera.projection_type = (
                "orthographic" if self.ortho_enabled else "perspective"
            )
        self._request_update()

    def toggle_gizmo_orientation(self) -> None:
        self.gizmo_world_orientation_enabled = not self.gizmo_world_orientation_enabled
        if self._gizmo is None:
            log.error("[EditorCameraUIController] cannot toggle orientation without transform gizmo")
        else:
            self._gizmo.set_orientation_mode(self.gizmo_orientation_mode)
        self._request_update()

    def _set_render_category(self, category: int, enabled: bool) -> None:
        if self._camera is None:
            log.error("[EditorCameraUIController] cannot change render category without camera")
            return
        mask = int(self._camera.render_category_mask)
        self._camera.render_category_mask = mask | int(category) if enabled else mask & ~int(category)

    def _apply_wireframe(self) -> None:
        color_pass = self._find_pass("Color")
        transparent_pass = self._find_pass("Transparent")
        if color_pass is None:
            log.error("[EditorCameraUIController] Color render pass is unavailable")
        else:
            color_pass.wireframe = self.wireframe_enabled
        if transparent_pass is None:
            log.error("[EditorCameraUIController] Transparent render pass is unavailable")
        else:
            transparent_pass.wireframe = self.wireframe_enabled

    def _find_pass(self, pass_name: str):
        if self._camera is None or self._camera.viewport is None:
            return None
        render_target = self._camera.viewport.render_target
        if render_target is None or render_target.pipeline is None:
            return None
        for pass_ref in render_target.pipeline.passes:
            if pass_ref.pass_name == pass_name:
                return pass_ref.to_python()
        return None

    def _request_update(self) -> None:
        if self._request_render is None:
            log.error("[EditorCameraUIController] render-update callback is unavailable")
            return
        self._request_render()
