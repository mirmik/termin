"""tcgui editor extension for FoliageLayerComponent paint stamps."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from tcbase import Action, Key, log
from tcbase._geom_native import Vec3
from tgfx._tgfx_native import Color4
from tcgui.widgets.button import Button
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.vstack import VStack
from tcgui.widgets.units import px

from termin.editor_tcgui.component_editor_extension import (
    register_component_editor_extension,
)
from termin.foliage import FoliageInstance, TcFoliageData


_COLOR_INSTANCE = Color4(0.35, 1.00, 0.25, 1.00)
_COLOR_BRUSH = Color4(0.05, 0.95, 1.00, 1.00)
_COLOR_ERASE = Color4(1.00, 0.32, 0.20, 1.00)
_COLOR_NORMAL = Color4(1.00, 0.90, 0.25, 1.00)
_MODE_LABELS = {
    "idle": "Off",
    "paint": "Paint",
    "erase": "Erase",
}


@dataclass
class _BrushHit:
    local_point: tuple[float, float, float]
    world_point: tuple[float, float, float]
    world_normal: tuple[float, float, float]


class FoliageLayerEditorExtension:
    def __init__(self) -> None:
        self._editor = None
        self._entity = None
        self._component_ref = None
        self._component = None
        self._mode = "idle"
        self._radius = 0.5
        self._stamp_count = 1
        self._mode_label = Label()
        self._asset_label = Label()
        self._radius_label = Label()
        self._count_label = Label()
        self._last_hit: _BrushHit | None = None

    def attach(self, editor, entity, component_ref) -> None:
        self._editor = editor
        self._entity = entity
        self._component_ref = component_ref
        self._component = component_ref.to_python()
        if self._component is None:
            log.error("[FoliageLayerEditor] failed to resolve FoliageLayerComponent object")
        editor.add_viewport_click_interceptor(self._on_viewport_click)
        editor.add_viewport_key_handler(self._on_key)
        editor.add_viewport_overlay_drawer(self._draw_overlay)
        log.info("[FoliageLayerEditor] extension attached")

    def detach(self) -> None:
        editor = self._editor
        if editor is not None:
            editor.remove_viewport_click_interceptor(self._on_viewport_click)
            editor.remove_viewport_key_handler(self._on_key)
            editor.remove_viewport_overlay_drawer(self._draw_overlay)
        self._editor = None
        self._entity = None
        self._component_ref = None
        self._component = None
        self._mode = "idle"
        self._last_hit = None
        log.info("[FoliageLayerEditor] extension detached")

    def build_panel(self):
        root = VStack()
        root.spacing = 4

        title = Label()
        title.text = "Foliage Brush"
        root.add_child(title)

        self._mode_label.color = (0.55, 0.60, 0.68, 1.0)
        self._asset_label.color = (0.55, 0.60, 0.68, 1.0)
        self._radius_label.color = (0.55, 0.60, 0.68, 1.0)
        self._count_label.color = (0.55, 0.60, 0.68, 1.0)
        root.add_child(self._mode_label)
        root.add_child(self._asset_label)

        mode_row = HStack()
        mode_row.spacing = 4
        mode_row.preferred_height = px(28)
        mode_row.add_child(self._button("Off", lambda: self._set_mode("idle")))
        mode_row.add_child(self._button("Paint", lambda: self._set_mode("paint")))
        mode_row.add_child(self._button("Erase", lambda: self._set_mode("erase")))
        root.add_child(mode_row)

        radius_row = HStack()
        radius_row.spacing = 4
        radius_row.preferred_height = px(28)
        radius_row.add_child(self._radius_label)
        radius_row.add_child(self._button("-", lambda: self._change_radius(-0.1)))
        radius_row.add_child(self._button("+", lambda: self._change_radius(0.1)))
        root.add_child(radius_row)

        count_row = HStack()
        count_row.spacing = 4
        count_row.preferred_height = px(28)
        count_row.add_child(self._count_label)
        count_row.add_child(self._button("-", lambda: self._change_count(-1)))
        count_row.add_child(self._button("+", lambda: self._change_count(1)))
        root.add_child(count_row)

        self._refresh_panel()
        return root

    def _button(self, text: str, callback) -> Button:
        btn = Button()
        btn.text = text
        btn.on_click = callback
        return btn

    def _set_mode(self, mode: str) -> None:
        self._mode = mode
        self._refresh_panel()
        self._request_viewport_update()
        log.info(f"[FoliageLayerEditor] mode={mode}")

    def _change_radius(self, delta: float) -> None:
        self._radius = max(0.05, min(10.0, self._radius + delta))
        self._refresh_panel()
        self._request_viewport_update()

    def _change_count(self, delta: int) -> None:
        self._stamp_count = max(1, min(128, self._stamp_count + delta))
        self._refresh_panel()

    def _refresh_panel(self) -> None:
        self._mode_label.text = f"Mode: {_MODE_LABELS[self._mode]}"
        self._radius_label.text = f"Radius: {self._radius:.2f}"
        self._count_label.text = f"Count: {self._stamp_count}"
        handle = self._foliage_handle()
        if handle is None:
            self._asset_label.text = "Asset: <none>"
            return
        self._asset_label.text = f"Asset: {handle.name}; instances: {handle.instance_count}"

    def _on_key(self, event) -> bool:
        if self._mode == "idle":
            return False
        if event.key != Key.ESCAPE.value or event.action != Action.PRESS.value:
            return False
        self._set_mode("idle")
        return True

    def _on_viewport_click(
        self,
        entity,
        x: float,
        y: float,
        has_world_point: bool,
        world_x: float,
        world_y: float,
        world_z: float,
        depth: float,
        view_depth: float,
        reproject_screen_error: float,
        reproject_depth_error: float,
        has_mesh_hit: bool,
        mesh_x: float,
        mesh_y: float,
        mesh_z: float,
        normal_x: float,
        normal_y: float,
        normal_z: float,
        triangle_index: int,
        index0: int,
        index1: int,
        index2: int,
    ) -> bool:
        del entity, x, y, has_world_point, world_x, world_y, world_z
        del depth, view_depth, reproject_screen_error, reproject_depth_error
        del triangle_index, index0, index1, index2
        if self._mode == "idle":
            return False
        if not has_mesh_hit:
            log.error("[FoliageLayerEditor] brush click ignored: no mesh surface hit")
            return True

        handle = self._foliage_handle()
        if handle is None:
            log.error("[FoliageLayerEditor] brush click ignored: foliage asset is not selected")
            return True

        world_point = (float(mesh_x), float(mesh_y), float(mesh_z))
        world_normal = _normalized((float(normal_x), float(normal_y), float(normal_z)))
        local_point = self._local_point_from_world(world_point)
        local_normal = self._local_direction_from_world(world_normal)
        if local_point is None or local_normal is None:
            return True

        local_normal = _normalized(local_normal)
        self._last_hit = _BrushHit(local_point, world_point, world_normal)
        if self._mode == "paint":
            changed = self._paint(handle, world_point, world_normal, local_point, local_normal)
        elif self._mode == "erase":
            changed = self._erase(handle, world_point, world_normal, local_point)
        else:
            changed = False

        if changed and not handle.save():
            log.error(f"[FoliageLayerEditor] failed to save foliage asset: {handle.source_path}")
        self._refresh_panel()
        self._request_viewport_update()
        return True

    def _paint(
        self,
        handle: TcFoliageData,
        world_point: tuple[float, float, float],
        world_normal: tuple[float, float, float],
        local_point: tuple[float, float, float],
        local_normal: tuple[float, float, float],
    ) -> bool:
        world_tangent_a, world_tangent_b = _basis_from_normal(world_normal)
        rng = random.Random((handle.version + 1) * 1000003 + handle.instance_count)
        changed = False
        for index in range(self._stamp_count):
            if index == 0 and self._stamp_count == 1:
                paint_local_point = local_point
            else:
                ox, oy = _random_disk(rng, self._radius)
                paint_world_point = (
                    world_point[0] + world_tangent_a[0] * ox + world_tangent_b[0] * oy,
                    world_point[1] + world_tangent_a[1] * ox + world_tangent_b[1] * oy,
                    world_point[2] + world_tangent_a[2] * ox + world_tangent_b[2] * oy,
                )
                converted = self._local_point_from_world(paint_world_point)
                if converted is None:
                    return changed
                paint_local_point = converted
            instance = FoliageInstance()
            instance.px = float(paint_local_point[0])
            instance.py = float(paint_local_point[1])
            instance.pz = float(paint_local_point[2])
            instance.nx = float(local_normal[0])
            instance.ny = float(local_normal[1])
            instance.nz = float(local_normal[2])
            instance.yaw = float(rng.uniform(0.0, math.tau))
            instance.scale = float(self._random_scale(rng))
            instance.variant = 0
            instance.seed = rng.randrange(0, 2**32)
            if handle.add_instance(instance):
                changed = True
            else:
                log.error("[FoliageLayerEditor] failed to add foliage instance")
                return changed
        log.info(
            "[FoliageLayerEditor] painted foliage "
            f"count={self._stamp_count} total={handle.instance_count}"
        )
        return changed

    def _erase(
        self,
        handle: TcFoliageData,
        world_point: tuple[float, float, float],
        world_normal: tuple[float, float, float],
        local_point: tuple[float, float, float],
    ) -> bool:
        local_radius = self._local_radius_from_world_radius(world_point, world_normal, local_point)
        removed = handle.remove_instances_in_radius(
            float(local_point[0]),
            float(local_point[1]),
            float(local_point[2]),
            float(local_radius),
        )
        log.info(f"[FoliageLayerEditor] erased foliage count={removed} total={handle.instance_count}")
        return removed > 0

    def _random_scale(self, rng: random.Random) -> float:
        component = self._component
        if component is None:
            return 1.0
        lo = float(component.scale_min)
        hi = float(component.scale_max)
        if hi < lo:
            lo, hi = hi, lo
        if abs(hi - lo) < 0.000001:
            return lo
        return rng.uniform(lo, hi)

    def _foliage_handle(self) -> TcFoliageData | None:
        component = self._component
        if component is None:
            return None
        uuid = component.foliage_uuid
        if not uuid:
            return None

        handle = TcFoliageData.from_uuid(uuid)
        if handle.is_valid:
            handle.ensure_loaded()
            return handle

        editor = self._editor
        if editor is None:
            return None
        record = editor.resource_manager.external_assets.get_by_uuid("foliage_data", uuid)
        if record is None:
            return None
        handle = TcFoliageData.declare(record.uuid, record.name, record.path)
        if not handle.is_valid:
            return None
        handle.ensure_loaded()
        return handle

    def _local_point_from_world(
        self,
        point: tuple[float, float, float],
    ) -> tuple[float, float, float] | None:
        entity = self._entity
        if entity is None or not entity.valid():
            log.error("[FoliageLayerEditor] cannot convert point to local space: entity is not available")
            return None
        pose = entity.transform.global_pose()
        local = pose.point_to_local(Vec3(point[0], point[1], point[2]))
        return (float(local.x), float(local.y), float(local.z))

    def _local_direction_from_world(
        self,
        vector: tuple[float, float, float],
    ) -> tuple[float, float, float] | None:
        entity = self._entity
        if entity is None or not entity.valid():
            log.error("[FoliageLayerEditor] cannot convert direction to local space: entity is not available")
            return None
        pose = entity.transform.global_pose()
        local = pose.ang.inverse_rotate(Vec3(vector[0], vector[1], vector[2]))
        return (float(local.x), float(local.y), float(local.z))

    def _local_radius_from_world_radius(
        self,
        world_point: tuple[float, float, float],
        world_normal: tuple[float, float, float],
        local_point: tuple[float, float, float],
    ) -> float:
        tangent_a, tangent_b = _basis_from_normal(world_normal)
        local_a = self._local_point_from_world(
            (
                world_point[0] + tangent_a[0] * self._radius,
                world_point[1] + tangent_a[1] * self._radius,
                world_point[2] + tangent_a[2] * self._radius,
            )
        )
        local_b = self._local_point_from_world(
            (
                world_point[0] + tangent_b[0] * self._radius,
                world_point[1] + tangent_b[1] * self._radius,
                world_point[2] + tangent_b[2] * self._radius,
            )
        )
        if local_a is None or local_b is None:
            return self._radius
        return max(_distance(local_point, local_a), _distance(local_point, local_b))

    def _world_point_from_local(
        self,
        point: tuple[float, float, float],
    ) -> tuple[float, float, float] | None:
        entity = self._entity
        if entity is None or not entity.valid():
            return None
        pose = entity.transform.global_pose()
        world = pose.point_to_global(Vec3(point[0], point[1], point[2]))
        return (float(world.x), float(world.y), float(world.z))

    def _request_viewport_update(self) -> None:
        editor = self._editor
        if editor is not None:
            editor.request_viewport_update()

    def _draw_overlay(self) -> None:
        handle = self._foliage_handle()
        if handle is None:
            return

        from termin.visualization.render.immediate import ImmediateRenderer

        renderer = ImmediateRenderer.instance()
        for instance in handle.instances:
            world = self._world_point_from_local((instance.px, instance.py, instance.pz))
            if world is not None:
                renderer.sphere_wireframe(_vec3(world), 0.07, _COLOR_INSTANCE, 8, False)

        hit = self._last_hit
        if hit is None or self._mode == "idle":
            return
        color = _COLOR_ERASE if self._mode == "erase" else _COLOR_BRUSH
        renderer.sphere_wireframe(_vec3(hit.world_point), self._radius, color, 24, False)
        normal_end = (
            hit.world_point[0] + hit.world_normal[0] * 0.5,
            hit.world_point[1] + hit.world_normal[1] * 0.5,
            hit.world_point[2] + hit.world_normal[2] * 0.5,
        )
        renderer.line(_vec3(hit.world_point), _vec3(normal_end), _COLOR_NORMAL, False)


def _vec3(point: tuple[float, float, float]) -> Vec3:
    return Vec3(point[0], point[1], point[2])


def _normalized(vector: tuple[float, float, float]) -> tuple[float, float, float]:
    length = math.sqrt(vector[0] * vector[0] + vector[1] * vector[1] + vector[2] * vector[2])
    if length < 0.000001:
        return (0.0, 0.0, 1.0)
    return (vector[0] / length, vector[1] / length, vector[2] / length)


def _distance(
    a: tuple[float, float, float],
    b: tuple[float, float, float],
) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    dz = a[2] - b[2]
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def _cross(
    a: tuple[float, float, float],
    b: tuple[float, float, float],
) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _basis_from_normal(
    normal: tuple[float, float, float],
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    helper = (0.0, 0.0, 1.0)
    if abs(normal[2]) > 0.92:
        helper = (1.0, 0.0, 0.0)
    tangent_a = _normalized(_cross(helper, normal))
    tangent_b = _normalized(_cross(normal, tangent_a))
    return tangent_a, tangent_b


def _random_disk(rng: random.Random, radius: float) -> tuple[float, float]:
    angle = rng.uniform(0.0, math.tau)
    distance = math.sqrt(rng.uniform(0.0, 1.0)) * radius
    return (math.cos(angle) * distance, math.sin(angle) * distance)


def register_default_extension() -> None:
    register_component_editor_extension(
        "FoliageLayerComponent",
        FoliageLayerEditorExtension,
    )


__all__ = ["FoliageLayerEditorExtension", "register_default_extension"]
