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


_COLOR_INSTANCE = (0.35, 1.00, 0.25, 1.00)
_COLOR_BRUSH = (0.05, 0.95, 1.00, 1.00)
_COLOR_ERASE = (1.00, 0.32, 0.20, 1.00)
_COLOR_NORMAL = (1.00, 0.90, 0.25, 1.00)
_MODE_LABELS = {
    "idle": "Off",
    "paint": "Paint",
    "erase": "Erase",
}


@dataclass
class _BrushHit:
    local_point: Vec3
    world_point: Vec3
    world_normal: Vec3


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
        self._tool_active = False

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
        self._set_tool_active(False)
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

    def build_left_panel(self):
        return None

    def _button(self, text: str, callback) -> Button:
        btn = Button()
        btn.text = text
        btn.on_click = callback
        return btn

    def _set_mode(self, mode: str) -> None:
        self._mode = mode
        self._set_tool_active(mode != "idle")
        self._refresh_panel()
        self._request_viewport_update()
        log.info(f"[FoliageLayerEditor] mode={mode}")

    def _set_tool_active(self, active: bool) -> None:
        if self._tool_active == active:
            return
        editor = self._editor
        if editor is None:
            self._tool_active = active
            return
        if active:
            editor.begin_viewport_tool()
        else:
            editor.end_viewport_tool()
        self._tool_active = active

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

    def _on_viewport_click(self, event) -> bool:
        if self._mode == "idle":
            return False
        surface = event.surface
        if not surface.has_mesh_hit:
            log.error("[FoliageLayerEditor] brush click ignored: no mesh surface hit")
            return True

        handle = self._foliage_handle()
        if handle is None:
            log.error("[FoliageLayerEditor] brush click ignored: foliage asset is not selected")
            return True

        world_point = surface.mesh_point
        world_normal = _normalized(surface.mesh_normal)
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
        world_point: Vec3,
        world_normal: Vec3,
        local_point: Vec3,
        local_normal: Vec3,
    ) -> bool:
        world_tangent_a, world_tangent_b = _basis_from_normal(world_normal)
        rng = random.Random((handle.version + 1) * 1000003 + handle.instance_count)
        changed = False
        for index in range(self._stamp_count):
            if index == 0 and self._stamp_count == 1:
                paint_local_point = local_point
            else:
                ox, oy = _random_disk(rng, self._radius)
                paint_world_point = world_point + world_tangent_a * ox + world_tangent_b * oy
                converted = self._local_point_from_world(paint_world_point)
                if converted is None:
                    return changed
                paint_local_point = converted
            instance = FoliageInstance()
            instance.px = float(paint_local_point.x)
            instance.py = float(paint_local_point.y)
            instance.pz = float(paint_local_point.z)
            instance.nx = float(local_normal.x)
            instance.ny = float(local_normal.y)
            instance.nz = float(local_normal.z)
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
        world_point: Vec3,
        world_normal: Vec3,
        local_point: Vec3,
    ) -> bool:
        local_radius = self._local_radius_from_world_radius(world_point, world_normal, local_point)
        removed = handle.remove_instances_in_radius(
            float(local_point.x),
            float(local_point.y),
            float(local_point.z),
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
        point: Vec3,
    ) -> Vec3 | None:
        entity = self._entity
        if entity is None or not entity.valid():
            log.error("[FoliageLayerEditor] cannot convert point to local space: entity is not available")
            return None
        pose = entity.transform.global_pose()
        return pose.point_to_local(point)

    def _local_direction_from_world(
        self,
        vector: Vec3,
    ) -> Vec3 | None:
        entity = self._entity
        if entity is None or not entity.valid():
            log.error("[FoliageLayerEditor] cannot convert direction to local space: entity is not available")
            return None
        pose = entity.transform.global_pose()
        return pose.ang.inverse_rotate(vector)

    def _local_radius_from_world_radius(
        self,
        world_point: Vec3,
        world_normal: Vec3,
        local_point: Vec3,
    ) -> float:
        tangent_a, tangent_b = _basis_from_normal(world_normal)
        local_a = self._local_point_from_world(world_point + tangent_a * self._radius)
        local_b = self._local_point_from_world(world_point + tangent_b * self._radius)
        if local_a is None or local_b is None:
            return self._radius
        return max(_distance(local_point, local_a), _distance(local_point, local_b))

    def _world_point_from_local(
        self,
        point: Vec3,
    ) -> Vec3 | None:
        entity = self._entity
        if entity is None or not entity.valid():
            return None
        pose = entity.transform.global_pose()
        return pose.point_to_global(point)

    def _request_viewport_update(self) -> None:
        editor = self._editor
        if editor is not None:
            editor.request_viewport_update()

    def _draw_overlay(self) -> None:
        handle = self._foliage_handle()
        if handle is None:
            return

        from termin.render import ImmediateRenderer

        renderer = ImmediateRenderer.instance()
        for instance in handle.instances:
            world = self._world_point_from_local(Vec3(instance.px, instance.py, instance.pz))
            if world is not None:
                renderer.sphere_wireframe(world, 0.07, _color(_COLOR_INSTANCE), 8, False)

        hit = self._last_hit
        if hit is None or self._mode == "idle":
            return
        color = _COLOR_ERASE if self._mode == "erase" else _COLOR_BRUSH
        renderer.sphere_wireframe(hit.world_point, self._radius, _color(color), 24, False)
        normal_end = hit.world_point + hit.world_normal * 0.5
        renderer.line(hit.world_point, normal_end, _color(_COLOR_NORMAL), False)


def _color(value: tuple[float, float, float, float]) -> Color4:
    return Color4(value[0], value[1], value[2], value[3])


def _normalized(vector: Vec3) -> Vec3:
    length = vector.norm()
    if length < 0.000001:
        return Vec3(0.0, 0.0, 1.0)
    return vector / length


def _distance(a: Vec3, b: Vec3) -> float:
    return (a - b).norm()


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return a.cross(b)


def _basis_from_normal(normal: Vec3) -> tuple[Vec3, Vec3]:
    helper = Vec3(0.0, 0.0, 1.0)
    if abs(normal.z) > 0.92:
        helper = Vec3(1.0, 0.0, 0.0)
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
