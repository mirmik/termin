"""Toolkit-neutral ProceduralMesh viewport editing behavior."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from tcbase import log
from tcbase._geom_native import Vec3
from tgfx._tgfx_native import Color4

from termin.csg.document_eval import evaluate_document
from termin.csg.document_visual_model import build_document_visual_model
from termin.csg.procedural_document import ProceduralPlane
from termin.csg.sketch_point_interaction import (
    SketchPointDrag,
    WallHeightDrag,
    drag_point_to_ray,
    drag_wall_height_offset_to_ray,
    pick_selected_sketch_point,
    pick_selected_wall_height_point,
)
from termin.csg.solid_render import PointTransform, SolidRenderStyle, draw_solid


if TYPE_CHECKING:
    from termin.editor_core.procedural_mesh_editor_extension import (
        ProceduralMeshExtensionModel,
    )


@dataclass
class _ClickFallback:
    point: tuple[float, float, float] | None = None
    plane: ProceduralPlane | None = None
    kind: str = "fallback"


class ProceduralMeshViewportInteraction:
    """Own draw, drag, picking and overlay behavior for one extension model."""

    def __init__(self, model: "ProceduralMeshExtensionModel") -> None:
        self._model = model
        self._editor = None
        self._entity = None
        self._sketch_point_drag: SketchPointDrag | None = None
        self._wall_height_drag: WallHeightDrag | None = None
        self._tool_active = False

    def attach(self, editor, entity) -> None:
        self._editor = editor
        self._entity = entity
        editor.add_viewport_click_interceptor(self.on_click)
        editor.add_viewport_pointer_handler(self.on_pointer)
        editor.add_viewport_overlay_drawer(self.draw_overlay)

    def detach(self) -> None:
        editor = self._editor
        self._end_tool()
        if editor is not None:
            editor.remove_viewport_click_interceptor(self.on_click)
            editor.remove_viewport_pointer_handler(self.on_pointer)
            editor.remove_viewport_overlay_drawer(self.draw_overlay)
        self._editor = None
        self._entity = None
        self._sketch_point_drag = None
        self._wall_height_drag = None

    def on_click(self, event) -> bool:
        controller = self._model.controller
        if controller.mode == "idle":
            return False
        if not self._model.ensure_component_document():
            return True

        entity = event.entity
        x = float(event.screen.x)
        y = float(event.screen.y)
        surface = event.surface
        picked_name = "<none>"
        if entity is not None and entity.valid():
            picked_name = entity.name

        local_ray = self._local_ray_from_viewport(x, y)
        fallback = self._click_fallback(x, y, surface)
        if fallback.point is None:
            log.error("[ProceduralMeshEditor] click ignored: no mesh hit and no OXY plane point")
            return True
        if local_ray is None:
            log.error("[ProceduralMeshEditor] click ignored: viewport ray is not available")
            return True

        ray_origin, ray_direction = local_ray
        result = controller.add_draft_point_from_ray(
            ray_origin,
            ray_direction,
            fallback_point=fallback.point,
            fallback_plane=fallback.plane,
            fallback_kind=fallback.kind,
        )
        if not self._model.apply_result(result):
            return True
        if not controller.draft.points:
            log.error("[ProceduralMeshEditor] click ignored: controller did not add a draft point")
            return True
        local_point = controller.draft.points[-1]
        world_point = self._world_point_from_local(local_point)
        if world_point is None:
            return True

        log.info(
            "[ProceduralMeshEditor] viewport click "
            f"mode={controller.mode} screen=({x:.1f}, {y:.1f}) picked='{picked_name}' "
            f"{fallback.kind}_world=({world_point.x:.3f}, {world_point.y:.3f}, {world_point.z:.3f}) "
            f"local=({local_point[0]:.3f}, {local_point[1]:.3f}, {local_point[2]:.3f}) "
            f"tri={surface.mesh_triangle_index} draft_points={len(controller.draft.points)}"
        )
        return True

    def on_pointer(self, event) -> bool:
        phase = event.phase
        x = float(event.screen.x)
        y = float(event.screen.y)
        button = int(event.button)
        if phase == "move":
            if self._wall_height_drag is not None:
                return self._drag_wall_height_to_viewport(x, y)
            if self._sketch_point_drag is not None:
                return self._drag_sketch_point_to_viewport(x, y)
            return False
        if phase == "down":
            if button != 0:
                return False
            wall_drag = self._pick_selected_wall_height_point(x, y)
            if wall_drag is not None:
                self._wall_height_drag = wall_drag
                self._begin_tool()
                self._model.set_status(f"Dragging wall height P{wall_drag.point_index}")
                log.info(
                    "[ProceduralMeshEditor] wall height drag started "
                    f"operation='{wall_drag.operation_id}' source='{wall_drag.source_id}' "
                    f"index={wall_drag.point_index}"
                )
                return True
            drag = self._pick_selected_sketch_point(x, y)
            if drag is None:
                return False
            self._sketch_point_drag = drag
            self._begin_tool()
            self._model.set_status(f"Dragging {drag.kind} point P{drag.point_index}")
            log.info(
                "[ProceduralMeshEditor] sketch point drag started "
                f"kind='{drag.kind}' item='{drag.item_id}' index={drag.point_index}"
            )
            return True
        if phase == "up":
            wall_drag = self._wall_height_drag
            if wall_drag is not None:
                self._drag_wall_height_to_viewport(x, y)
                self._wall_height_drag = None
                self._end_tool()
                self._model.set_status(f"Wall height P{wall_drag.point_index} moved")
                log.info(
                    "[ProceduralMeshEditor] wall height drag finished "
                    f"operation='{wall_drag.operation_id}' source='{wall_drag.source_id}' "
                    f"index={wall_drag.point_index}"
                )
                return True
            drag = self._sketch_point_drag
            if drag is None:
                return False
            self._drag_sketch_point_to_viewport(x, y)
            self._sketch_point_drag = None
            self._end_tool()
            self._model.set_status(f"{drag.kind.capitalize()} point P{drag.point_index} moved")
            log.info(
                "[ProceduralMeshEditor] sketch point drag finished "
                f"kind='{drag.kind}' item='{drag.item_id}' index={drag.point_index}"
            )
            return True
        return False

    def _begin_tool(self) -> None:
        if self._tool_active:
            return
        if self._editor is not None:
            self._editor.begin_viewport_tool()
        self._tool_active = True

    def _end_tool(self) -> None:
        if not self._tool_active:
            return
        if self._editor is not None:
            self._editor.end_viewport_tool()
        self._tool_active = False

    def _pick_selected_sketch_point(self, x: float, y: float) -> SketchPointDrag | None:
        if not self._model.ensure_component_document():
            return None
        controller = self._model.controller
        return pick_selected_sketch_point(
            controller.document,
            controller.selection,
            self._project_document_point_to_viewport,
            x,
            y,
        )

    def _pick_selected_wall_height_point(self, x: float, y: float) -> WallHeightDrag | None:
        if not self._model.ensure_component_document():
            return None
        controller = self._model.controller
        return pick_selected_wall_height_point(
            controller.document,
            controller.selection,
            self._project_document_point_to_viewport,
            x,
            y,
        )

    def _drag_sketch_point_to_viewport(self, x: float, y: float) -> bool:
        drag = self._sketch_point_drag
        if drag is None:
            return False
        if not self._model.ensure_component_document():
            self._sketch_point_drag = None
            self._end_tool()
            return True
        local_ray = self._local_ray_from_viewport(x, y)
        if local_ray is None:
            log.error("[ProceduralMeshEditor] cannot drag sketch point: viewport ray is not available")
            return True
        controller = self._model.controller
        local_point = drag_point_to_ray(controller.document, drag, *local_ray)
        if local_point is None:
            return True
        if drag.kind == "contour":
            result = controller.set_contour_point(drag.item_id, drag.point_index, local_point)
        elif drag.kind == "path":
            result = controller.set_path_point(drag.item_id, drag.point_index, local_point)
        else:
            log.error(f"[ProceduralMeshEditor] cannot drag sketch point: unsupported kind '{drag.kind}'")
            return True
        self._model.apply_result(result)
        return True

    def _drag_wall_height_to_viewport(self, x: float, y: float) -> bool:
        drag = self._wall_height_drag
        if drag is None:
            return False
        if not self._model.ensure_component_document():
            self._wall_height_drag = None
            self._end_tool()
            return True
        local_ray = self._local_ray_from_viewport(x, y)
        if local_ray is None:
            log.error("[ProceduralMeshEditor] cannot drag wall height: viewport ray is not available")
            return True
        offset = drag_wall_height_offset_to_ray(drag, *local_ray)
        result = self._model.controller.set_wall_corner_offset(
            drag.operation_id,
            drag.source_id,
            drag.point_index,
            offset,
        )
        self._model.apply_result(result)
        return True

    def _project_document_point_to_viewport(
        self,
        point: tuple[float, float, float],
    ) -> tuple[float, float] | None:
        if self._editor is None:
            return None
        world_point = self._world_point_from_local(point)
        if world_point is None:
            return None
        return self._editor.project_world_point_to_viewport(world_point)

    def _local_ray_from_viewport(
        self,
        x: float,
        y: float,
    ) -> tuple[tuple[float, float, float], tuple[float, float, float]] | None:
        if self._editor is None or self._entity is None or not self._entity.valid():
            return None
        world_ray = self._editor.world_ray_from_viewport_point(x, y)
        if world_ray is None:
            return None
        origin, direction = world_ray
        pose = self._entity.transform.global_pose()
        local_origin = pose.point_to_local(origin)
        local_direction = pose.vector_to_local(direction)
        return (
            (float(local_origin.x), float(local_origin.y), float(local_origin.z)),
            (float(local_direction.x), float(local_direction.y), float(local_direction.z)),
        )

    def _world_point_from_local(self, point: tuple[float, float, float]) -> Vec3 | None:
        if self._entity is None or not self._entity.valid():
            log.error("[ProceduralMeshEditor] cannot convert point to world space: entity is not available")
            return None
        return self._entity.transform.global_pose().point_to_global(Vec3(*point))

    def _click_fallback(self, x: float, y: float, surface) -> _ClickFallback:
        if surface.has_mesh_hit:
            return _ClickFallback(self._local_point_from_world(surface.mesh_point), None, "mesh")
        if surface.has_world_point:
            return _ClickFallback(self._local_point_from_world(surface.world_point), None, "world")
        if self._editor is None:
            return _ClickFallback()
        world = self._editor.world_point_on_entity_local_oxy_plane(x, y, self._entity)
        if world is None:
            return _ClickFallback()
        local = self._local_point_from_world(world)
        if local is None:
            return _ClickFallback()
        return _ClickFallback((local[0], local[1], 0.0), ProceduralPlane(), "oxy")

    def _local_point_from_world(self, point: Vec3) -> tuple[float, float, float] | None:
        if self._entity is None or not self._entity.valid():
            log.error("[ProceduralMeshEditor] cannot convert point to local space: entity is not available")
            return None
        local = self._entity.transform.global_pose().point_to_local(point)
        return (float(local.x), float(local.y), float(local.z))

    def draw_overlay(self) -> None:
        if self._entity is None or not self._entity.valid():
            return
        try:
            pose = self._entity.transform.global_pose()
            center = pose.lin
        except Exception as error:
            log.error(f"[ProceduralMeshEditor] overlay failed: {error}")
            return

        from termin.render import ImmediateRenderer

        renderer = ImmediateRenderer.instance()
        anchor_color = Color4(0.1, 0.9, 1.0, 1.0)
        radius = 0.35
        renderer.line(
            Vec3(center.x - radius, center.y, center.z), Vec3(center.x + radius, center.y, center.z), anchor_color, True
        )
        renderer.line(
            Vec3(center.x, center.y - radius, center.z), Vec3(center.x, center.y + radius, center.z), anchor_color, True
        )
        renderer.line(
            Vec3(center.x, center.y, center.z - radius), Vec3(center.x, center.y, center.z + radius), anchor_color, True
        )
        self._draw_document_debug(renderer, pose)

    def _draw_document_debug(self, renderer, entity_pose) -> None:
        if self._model.component is None:
            return
        controller = self._model.controller
        document = controller.document
        evaluated_solids = evaluate_document(document)
        for operation in document.operations:
            style = self._solid_style(controller.selection == ("operation", operation.id))
            for evaluated in evaluated_solids:
                if evaluated.operation_id == operation.id:
                    draw_solid(
                        renderer,
                        evaluated.solid,
                        style,
                        self._compose_point_transform(entity_pose, evaluated.point_transform),
                    )

        visual_model = build_document_visual_model(
            document,
            controller.draft.points,
            controller.selection,
        )
        for polyline in visual_model.polylines:
            self._draw_polyline(
                renderer,
                entity_pose,
                polyline.points,
                self._color4(polyline.color),
                polyline.closed,
                polyline.depth_test,
            )
        for point in visual_model.points:
            renderer.sphere_wireframe(
                self._world_vec3(entity_pose, point.point),
                point.radius,
                self._color4(point.color),
                8,
                point.depth_test,
            )

    def _compose_point_transform(self, entity_pose, document_transform: PointTransform) -> PointTransform:
        def transform(point: tuple[float, float, float]) -> tuple[float, float, float]:
            local_point = document_transform(point)
            world_point = entity_pose.point_to_global(Vec3(*local_point))
            return (float(world_point.x), float(world_point.y), float(world_point.z))

        return transform

    @staticmethod
    def _color4(color: tuple[float, float, float, float]) -> Color4:
        return Color4(*color)

    @staticmethod
    def _solid_style(selected: bool) -> SolidRenderStyle:
        if selected:
            return SolidRenderStyle(
                fill_color=Color4(0.15, 0.85, 1.0, 0.32),
                edge_color=Color4(0.85, 1.0, 1.0, 1.0),
                depth_test=True,
            )
        return SolidRenderStyle(
            fill_color=Color4(0.0, 0.65, 0.95, 0.20),
            edge_color=Color4(0.0, 0.95, 0.95, 0.85),
            depth_test=True,
        )

    def _draw_polyline(
        self,
        renderer,
        entity_pose,
        points: list[tuple[float, float, float]],
        color: Color4,
        closed: bool,
        depth_test: bool = False,
    ) -> None:
        if len(points) < 2:
            return
        for first, second in zip(points, points[1:], strict=False):
            renderer.line(
                self._world_vec3(entity_pose, first),
                self._world_vec3(entity_pose, second),
                color,
                depth_test,
            )
        if closed:
            renderer.line(
                self._world_vec3(entity_pose, points[-1]),
                self._world_vec3(entity_pose, points[0]),
                color,
                depth_test,
            )

    @staticmethod
    def _world_vec3(entity_pose, point: tuple[float, float, float]) -> Vec3:
        world = entity_pose.point_to_global(Vec3(*point))
        return Vec3(float(world.x), float(world.y), float(world.z))


__all__ = ["ProceduralMeshViewportInteraction"]
