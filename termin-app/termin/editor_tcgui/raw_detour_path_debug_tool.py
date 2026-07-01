"""Generic editor tool for visualizing raw Detour paths."""

from __future__ import annotations

from dataclasses import dataclass

from tcbase import log
from tcbase._geom_native import Vec3
from tgfx._tgfx_native import Color4


_COLOR_START = Color4(0.20, 1.00, 0.35, 1.00)
_COLOR_END = Color4(1.00, 0.25, 0.20, 1.00)
_COLOR_STANDARD = Color4(0.05, 0.90, 1.00, 1.00)
_COLOR_OFFMESH = Color4(1.00, 0.78, 0.10, 1.00)
_COLOR_POINT = Color4(1.00, 1.00, 1.00, 1.00)
_COLOR_FAILED = Color4(1.00, 0.10, 0.60, 1.00)


@dataclass
class _DetourPathPoint:
    point: tuple[float, float, float]
    flags: int
    poly_ref: int
    area: int
    off_mesh_connection: bool
    off_mesh_user_id: int


@dataclass
class _DetourPathCandidate:
    entity_name: str
    navmesh_uuid: str
    start_distance_sq: float
    end_distance_sq: float
    start_over_poly: bool
    end_over_poly: bool
    path_points: list[_DetourPathPoint]

    def score(self) -> tuple[int, float, float]:
        off_poly_count = int(not self.start_over_poly) + int(not self.end_over_poly)
        total_distance_sq = self.start_distance_sq + self.end_distance_sq
        max_distance_sq = max(self.start_distance_sq, self.end_distance_sq)
        return (off_poly_count, total_distance_sq, max_distance_sq)


class RawDetourPathDebugTool:
    """Viewport click tool that draws DetourPathfindingWorldComponent results."""

    def __init__(self, editor) -> None:
        self._editor = editor
        self._enabled = False
        self._start: tuple[float, float, float] | None = None
        self._end: tuple[float, float, float] | None = None
        self._path_points: list[_DetourPathPoint] = []

    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if self._enabled == enabled:
            return

        self._enabled = enabled
        if enabled:
            self._editor.add_viewport_click_interceptor(self._on_viewport_click)
            self._editor.add_viewport_overlay_drawer(self._draw_overlay)
            log.info("[RawDetourPathDebugTool] enabled")
            return

        self._editor.remove_viewport_click_interceptor(self._on_viewport_click)
        self._editor.remove_viewport_overlay_drawer(self._draw_overlay)
        self._start = None
        self._end = None
        self._path_points = []
        log.info("[RawDetourPathDebugTool] disabled")

    def toggle(self) -> None:
        self.set_enabled(not self._enabled)

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
        if not self._enabled:
            return False

        point = _click_point(
            has_mesh_hit,
            mesh_x,
            mesh_y,
            mesh_z,
            has_world_point,
            world_x,
            world_y,
            world_z,
        )
        if point is None:
            log.error("[RawDetourPathDebugTool] click ignored: no world point")
            return True

        self._accept_point(point)
        picked_name = "<none>"
        if entity.valid():
            picked_name = entity.name
        log.info(
            "[RawDetourPathDebugTool] click: "
            f"screen=({x:.1f}, {y:.1f}) picked='{picked_name}' "
            f"point=({point[0]:.3f}, {point[1]:.3f}, {point[2]:.3f})"
        )
        return True

    def _accept_point(self, point: tuple[float, float, float]) -> None:
        if self._start is None or self._end is not None:
            self._start = point
            self._end = None
            self._path_points = []
            log.info(
                "[RawDetourPathDebugTool] start set: "
                f"({point[0]:.3f}, {point[1]:.3f}, {point[2]:.3f})"
            )
            return

        self._end = point
        log.info(
            "[RawDetourPathDebugTool] end set: "
            f"({point[0]:.3f}, {point[1]:.3f}, {point[2]:.3f})"
        )
        self._rebuild_path()

    def _rebuild_path(self) -> None:
        if self._start is None or self._end is None:
            return

        candidate = self._find_best_path_candidate(self._start, self._end)
        if candidate is None:
            log.error("[RawDetourPathDebugTool] failed: no DetourPathfindingWorldComponent accepted path query")
            self._path_points = []
            return

        self._path_points = candidate.path_points
        if not self._path_points:
            log.error("[RawDetourPathDebugTool] Detour returned empty path")
            return

        log.info(
            "[RawDetourPathDebugTool] selected pathfinding world: "
            f"entity='{candidate.entity_name}' navmesh_uuid='{candidate.navmesh_uuid}' "
            f"start_distance={candidate.start_distance_sq ** 0.5:.3f} "
            f"end_distance={candidate.end_distance_sq ** 0.5:.3f} "
            f"start_over_poly={1 if candidate.start_over_poly else 0} "
            f"end_over_poly={1 if candidate.end_over_poly else 0}"
        )
        log.info(f"[RawDetourPathDebugTool] Detour returned {len(self._path_points)} points")
        for i, point in enumerate(self._path_points):
            log.info(
                "[RawDetourPathDebugTool] point "
                f"{i}: pos=({point.point[0]:.3f}, {point.point[1]:.3f}, {point.point[2]:.3f}) "
                f"area={point.area} ref={point.poly_ref} flags=0x{point.flags:02x} "
                f"offmesh={1 if point.off_mesh_connection else 0} "
                f"offmesh_user_id={point.off_mesh_user_id}"
            )

    def _find_best_path_candidate(
        self,
        start: tuple[float, float, float],
        end: tuple[float, float, float],
    ) -> _DetourPathCandidate | None:
        scene = self._editor.scene
        if scene is None:
            log.error("[RawDetourPathDebugTool] failed: editor scene is not available")
            return None

        try:
            from termin.navmesh import DetourPathfindingWorldComponent, navmesh_bake_frame_from_pose
        except Exception as e:
            log.error(f"[RawDetourPathDebugTool] failed to import termin.navmesh: {e}")
            return None

        best: _DetourPathCandidate | None = None
        total_worlds = 0
        for entity in scene.entities:
            component = entity.get_component(DetourPathfindingWorldComponent)
            if component is None:
                continue
            total_worlds += 1

            if not component.is_ready() and not component.rebuild():
                log.warning(
                    "[RawDetourPathDebugTool] skipped pathfinding world: "
                    f"entity='{entity.name}' navmesh_uuid='{component.navmesh_uuid}' is not ready"
                )
                continue

            bake_frame = navmesh_bake_frame_from_pose(entity.transform.global_pose())
            start_closest = component.closest_point_world(bake_frame, start)
            end_closest = component.closest_point_world(bake_frame, end)
            if not start_closest.success or not end_closest.success:
                log.warning(
                    "[RawDetourPathDebugTool] skipped pathfinding world: "
                    f"entity='{entity.name}' navmesh_uuid='{component.navmesh_uuid}' "
                    f"start_success={1 if start_closest.success else 0} "
                    f"end_success={1 if end_closest.success else 0}"
                )
                continue

            path_points = _detailed_path_points(
                component.find_detailed_path_world(bake_frame, start, end)
            )
            if not path_points:
                log.warning(
                    "[RawDetourPathDebugTool] skipped pathfinding world: "
                    f"entity='{entity.name}' navmesh_uuid='{component.navmesh_uuid}' returned empty path"
                )
                continue

            candidate = _DetourPathCandidate(
                entity_name=entity.name,
                navmesh_uuid=str(component.navmesh_uuid),
                start_distance_sq=_distance_sq(start, _tuple3(start_closest.point)),
                end_distance_sq=_distance_sq(end, _tuple3(end_closest.point)),
                start_over_poly=bool(start_closest.over_poly),
                end_over_poly=bool(end_closest.over_poly),
                path_points=path_points,
            )
            log.info(
                "[RawDetourPathDebugTool] candidate: "
                f"entity='{candidate.entity_name}' navmesh_uuid='{candidate.navmesh_uuid}' "
                f"points={len(candidate.path_points)} "
                f"start_distance={candidate.start_distance_sq ** 0.5:.3f} "
                f"end_distance={candidate.end_distance_sq ** 0.5:.3f} "
                f"start_over_poly={1 if candidate.start_over_poly else 0} "
                f"end_over_poly={1 if candidate.end_over_poly else 0}"
            )
            if best is None or candidate.score() < best.score():
                best = candidate

        if total_worlds == 0:
            log.error("[RawDetourPathDebugTool] failed: DetourPathfindingWorldComponent not found")
        return best

    def _draw_overlay(self) -> None:
        if not self._enabled:
            return

        from termin.render import ImmediateRenderer

        renderer = ImmediateRenderer.instance()
        if self._start is not None:
            _draw_marker(renderer, self._start, _COLOR_START, 0.18)
        if self._end is not None:
            _draw_marker(renderer, self._end, _COLOR_END, 0.18)

        if len(self._path_points) < 2:
            if self._start is not None and self._end is not None:
                renderer.line(_vec3(self._start), _vec3(self._end), _COLOR_FAILED, False)
            return

        for i in range(len(self._path_points) - 1):
            a = self._path_points[i]
            b = self._path_points[i + 1]
            color = _COLOR_OFFMESH if a.off_mesh_connection else _COLOR_STANDARD
            renderer.line(_vec3(a.point), _vec3(b.point), color, False)

        for point in self._path_points:
            color = _COLOR_OFFMESH if point.off_mesh_connection else _COLOR_POINT
            _draw_marker(renderer, point.point, color, 0.09)


def _click_point(
    has_mesh_hit: bool,
    mesh_x: float,
    mesh_y: float,
    mesh_z: float,
    has_world_point: bool,
    world_x: float,
    world_y: float,
    world_z: float,
) -> tuple[float, float, float] | None:
    if has_mesh_hit:
        return (float(mesh_x), float(mesh_y), float(mesh_z))
    if has_world_point:
        return (float(world_x), float(world_y), float(world_z))
    return None


def _detailed_path_points(detailed_path) -> list[_DetourPathPoint]:
    points: list[_DetourPathPoint] = []
    for item in detailed_path:
        p = item["point"]
        points.append(
            _DetourPathPoint(
                point=(float(p[0]), float(p[1]), float(p[2])),
                flags=int(item["flags"]),
                poly_ref=int(item["poly_ref"]),
                area=int(item["area"]),
                off_mesh_connection=bool(item["off_mesh_connection"]),
                off_mesh_user_id=int(item["off_mesh_user_id"]),
            )
        )
    return points


def _distance_sq(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    dz = a[2] - b[2]
    return dx * dx + dy * dy + dz * dz


def _tuple3(point) -> tuple[float, float, float]:
    return (float(point[0]), float(point[1]), float(point[2]))


def _draw_marker(renderer, point: tuple[float, float, float], color: Color4, radius: float) -> None:
    renderer.sphere_wireframe(_vec3(point), radius, color, 8, False)


def _vec3(point: tuple[float, float, float]) -> Vec3:
    return Vec3(point[0], point[1], point[2])
