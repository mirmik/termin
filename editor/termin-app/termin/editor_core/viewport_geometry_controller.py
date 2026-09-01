"""Viewport picking, projection, and project-file drop helpers."""

from __future__ import annotations

from typing import Callable

from termin.base import log
from termin.base._geom_native import Ray3, Rect2, Vec2, Vec3


_GLTF_MODEL_EXTENSIONS = (".glb", ".gltf")


def is_gltf_project_file_drag(event) -> bool:
    if event.payload.kind != "project_file":
        return False
    data = event.payload.data
    if not isinstance(data, dict):
        return False
    return data.get("extension") in _GLTF_MODEL_EXTENSIONS


class ViewportGeometryController:
    def __init__(
        self,
        *,
        get_camera: Callable[[], object | None],
        get_viewport_widget: Callable[[], object | None],
        get_interaction_system: Callable[[], object | None],
        get_editor_display: Callable[[], object | None],
        get_scene_tree_controller: Callable[[], object | None],
    ) -> None:
        self._get_camera = get_camera
        self._get_viewport_widget = get_viewport_widget
        self._get_interaction_system = get_interaction_system
        self._get_editor_display = get_editor_display
        self._get_scene_tree_controller = get_scene_tree_controller

    def on_external_drag(self, event) -> bool:
        return is_gltf_project_file_drag(event)

    def on_external_drop(self, event) -> bool:
        if not self.on_external_drag(event):
            return False
        data = event.payload.data
        if not isinstance(data, dict):
            return False
        path = data.get("path")
        if not isinstance(path, str):
            return False
        return self.drop_project_file(path, str(data.get("extension", "")), event.x, event.y)

    def set_scene_tree_controller_getter(
        self,
        getter: Callable[[], object | None],
    ) -> None:
        self._get_scene_tree_controller = getter

    def drop_project_file(self, path: str, extension: str, x: float, y: float) -> bool:
        if extension.casefold() not in _GLTF_MODEL_EXTENSIONS:
            return False
        scene_tree_controller = self._get_scene_tree_controller()
        if scene_tree_controller is None:
            log.error("[ViewportGeometryController] GLTF viewport drop failed: scene tree controller is not available")
            return False
        world_pos = self.world_position_for_viewport_drop(x, y)
        scene_tree_controller.operations.drop_glb(path, None, world_position=world_pos)
        return True

    def world_position_for_viewport_drop(
        self,
        x: float,
        y: float,
    ) -> Vec3:
        fallback = self.fallback_drop_position()
        interaction_system = self._get_interaction_system()
        editor_display = self._get_editor_display()
        viewport_widget = self._get_viewport_widget()
        if interaction_system is None or editor_display is None:
            return fallback
        if not editor_display.viewports:
            return fallback
        if viewport_widget is None:
            return fallback

        viewport = editor_display.viewports[0]
        vp_idx, vp_gen = viewport._viewport_handle()
        local_x = float(x - viewport_widget.x)
        local_y = float(y - viewport_widget.y)
        try:
            pick = interaction_system.pick_surface_at(
                local_x,
                local_y,
                vp_idx,
                vp_gen,
                editor_display.index,
                editor_display.generation,
            )
        except Exception as e:
            log.error(f"[ViewportGeometryController] GLB viewport drop pick failed: {e}")
            return fallback
        if pick.has_world_point:
            return pick.world_point
        return fallback

    def fallback_drop_position(self) -> Vec3:
        camera = self._get_camera()
        if camera is None or camera.entity is None:
            return Vec3(0.0, 0.0, 0.0)
        transform = camera.entity.transform
        cam_pos = transform.global_position
        forward = transform.transform_direction(Vec3(0.0, 1.0, 0.0))
        return Vec3(
            float(cam_pos.x + forward.x * 5.0),
            float(cam_pos.y + forward.y * 5.0),
            float(cam_pos.z + forward.z * 5.0),
        )

    def world_point_on_oxy_plane(
        self,
        x: float,
        y: float,
    ) -> Vec3 | None:
        return self.world_point_on_plane(
            x,
            y,
            Vec3(0.0, 0.0, 0.0),
            Vec3(0.0, 0.0, 1.0),
            "OXY plane",
        )

    def world_ray_from_viewport_point(
        self,
        x: float,
        y: float,
    ) -> Ray3 | None:
        camera = self._get_camera()
        viewport_widget = self._get_viewport_widget()
        if camera is None or camera.entity is None:
            log.error("[ViewportGeometryController] viewport ray failed: editor camera is not available")
            return None
        if viewport_widget is None:
            log.error("[ViewportGeometryController] viewport ray failed: viewport widget is not available")
            return None

        viewport_rect = self._viewport_rect(viewport_widget)
        ray = camera.try_screen_point_to_ray(Vec2(float(x), float(y)), viewport_rect)
        if ray is None:
            log.error("[ViewportGeometryController] viewport ray failed: camera rejected screen projection")
            return None
        return ray

    def project_world_point_to_viewport(
        self,
        point: Vec3,
    ) -> tuple[float, float] | None:
        camera = self._get_camera()
        viewport_widget = self._get_viewport_widget()
        if camera is None or camera.entity is None:
            log.error("[ViewportGeometryController] viewport projection failed: editor camera is not available")
            return None
        if viewport_widget is None:
            log.error("[ViewportGeometryController] viewport projection failed: viewport widget is not available")
            return None
        projected = camera.try_project_world_point(point, self._viewport_rect(viewport_widget))
        if projected is None:
            log.error("[ViewportGeometryController] viewport projection failed: camera rejected world projection")
            return None
        return float(projected.screen.x), float(projected.screen.y)

    def world_point_on_plane(
        self,
        x: float,
        y: float,
        plane_origin: Vec3,
        plane_normal: Vec3,
        label: str = "plane",
    ) -> Vec3 | None:
        camera = self._get_camera()
        viewport_widget = self._get_viewport_widget()
        if camera is None or camera.entity is None:
            log.error(f"[ViewportGeometryController] {label} pick failed: editor camera is not available")
            return None
        if viewport_widget is None:
            log.error(f"[ViewportGeometryController] {label} pick failed: viewport widget is not available")
            return None

        viewport_rect = self._viewport_rect(viewport_widget)
        ray = camera.try_screen_point_to_ray(Vec2(float(x), float(y)), viewport_rect)
        if ray is None:
            log.error(f"[ViewportGeometryController] {label} pick failed: camera rejected screen projection")
            return None
        point = ray.try_intersect_plane(
            plane_origin,
            plane_normal,
            forward_only=True,
            epsilon=1.0e-9,
        )
        if point is None:
            log.error(f"[ViewportGeometryController] {label} pick failed: checked ray-plane intersection rejected")
            return None
        return point

    def world_point_on_entity_local_oxy_plane(
        self,
        x: float,
        y: float,
        entity,
    ) -> Vec3 | None:
        if entity is None or not entity.valid():
            log.error("[ViewportGeometryController] entity local OXY plane pick failed: entity is not available")
            return None
        transform = entity.transform
        origin = transform.global_position
        axis_x = transform.transform_vector(Vec3(1.0, 0.0, 0.0))
        axis_y = transform.transform_vector(Vec3(0.0, 1.0, 0.0))
        normal = axis_x.cross(axis_y).try_normalized(1.0e-10)
        if normal is None:
            log.error(
                "[ViewportGeometryController] entity local OXY plane pick failed: "
                "transformed axes do not define a finite non-degenerate plane"
            )
            return None
        return self.world_point_on_plane(
            x,
            y,
            origin,
            normal,
            "entity local OXY plane",
        )

    def _viewport_rect(self, viewport_widget) -> Rect2:
        return Rect2(
            0.0,
            0.0,
            float(viewport_widget.width),
            float(viewport_widget.height),
        )
