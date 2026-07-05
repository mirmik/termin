"""Generic editor tool for visualizing raw Detour paths."""

from __future__ import annotations

from dataclasses import dataclass

from tcbase import log
from tcbase._geom_native import Vec3
from tcgui.widgets.label import Label
from tcgui.widgets.separator import Separator
from tcgui.widgets.text_area import TextArea
from tcgui.widgets.units import px
from tcgui.widgets.vstack import VStack
from tgfx._tgfx_native import Color4


_PANEL_KEY = "termin.raw_detour_path_debug"
_COLOR_START = Color4(0.20, 1.00, 0.35, 1.00)
_COLOR_END = Color4(1.00, 0.25, 0.20, 1.00)
_COLOR_STANDARD = Color4(0.05, 0.90, 1.00, 1.00)
_COLOR_OFFMESH = Color4(1.00, 0.78, 0.10, 1.00)
_COLOR_LINEAR = Color4(0.80, 0.45, 1.00, 1.00)
_COLOR_POINT = Color4(1.00, 1.00, 1.00, 1.00)
_COLOR_FAILED = Color4(1.00, 0.10, 0.60, 1.00)


@dataclass
class _DetourPathPoint:
    point: tuple[float, float, float]
    flags: int
    poly_ref: int
    poly_type: int
    area: int
    off_mesh_connection: bool
    off_mesh_user_id: int
    linear_segment: bool
    linear_user_id: int


@dataclass
class _CandidateInfo:
    entity_name: str
    navmesh_uuid: str
    start_distance_sq: float
    end_distance_sq: float
    start_over_poly: bool
    end_over_poly: bool


class _RawDetourPathInspectorPanel(VStack):
    def __init__(self) -> None:
        super().__init__()
        self.spacing = 4

        title = Label()
        title.text = "Raw Detour Path Debug"
        title.font_size = 15
        self.add_child(title)

        self._status = Label()
        self._status.color = (0.62, 0.66, 0.74, 1.0)
        self.add_child(self._status)
        self.add_child(Separator())

        self._details = TextArea()
        self._details.read_only = True
        self._details.word_wrap = False
        self._details.preferred_height = px(680)
        self.add_child(self._details)
        self.update(
            enabled=False,
            start=None,
            end=None,
            path_points=[],
            candidates=[],
            selected_candidate=None,
            error="Tool is disabled.",
        )

    def update(
        self,
        *,
        enabled: bool,
        start: tuple[float, float, float] | None,
        end: tuple[float, float, float] | None,
        path_points: list[_DetourPathPoint],
        candidates: list[_CandidateInfo],
        selected_candidate: _CandidateInfo | None,
        error: str = "",
    ) -> None:
        self._status.text = "Enabled" if enabled else "Disabled"
        lines: list[str] = []
        if error:
            lines.append(f"Error: {error}")
            lines.append("")
        lines.append(f"Start: {_format_optional_point(start)}")
        lines.append(f"End:   {_format_optional_point(end)}")
        lines.append("")

        lines.append(f"Candidates: {len(candidates)}")
        for index, candidate in enumerate(candidates):
            marker = "*" if selected_candidate == candidate else " "
            lines.append(
                f"{marker} [{index}] entity='{candidate.entity_name}' "
                f"navmesh='{candidate.navmesh_uuid}' "
                f"start_dist={candidate.start_distance_sq ** 0.5:.3f} "
                f"end_dist={candidate.end_distance_sq ** 0.5:.3f} "
                f"start_over_poly={int(candidate.start_over_poly)} "
                f"end_over_poly={int(candidate.end_over_poly)}"
            )
        if selected_candidate is not None and selected_candidate not in candidates:
            lines.append(
                f"* selected entity='{selected_candidate.entity_name}' "
                f"navmesh='{selected_candidate.navmesh_uuid}' "
                f"start_dist={selected_candidate.start_distance_sq ** 0.5:.3f} "
                f"end_dist={selected_candidate.end_distance_sq ** 0.5:.3f} "
                f"start_over_poly={int(selected_candidate.start_over_poly)} "
                f"end_over_poly={int(selected_candidate.end_over_poly)}"
            )
        lines.append("")

        lines.append(f"Detour points: {len(path_points)}")
        for index, point in enumerate(path_points):
            lines.append(
                f"[{index:02d}] pos={_format_point(point.point)} "
                f"area={point.area} poly_type={point.poly_type} "
                f"ref={point.poly_ref} flags=0x{point.flags:02x} "
                f"offmesh={int(point.off_mesh_connection)} "
                f"offmesh_user_id={point.off_mesh_user_id} "
                f"linear={int(point.linear_segment)} "
                f"linear_user_id={point.linear_user_id}"
            )
        self._details.text = "\n".join(lines)


class RawDetourPathDebugTool:
    """Viewport click tool that draws DetourPathfindingWorldComponent results."""

    def __init__(self, editor) -> None:
        self._editor = editor
        self._enabled = False
        self._start: tuple[float, float, float] | None = None
        self._end: tuple[float, float, float] | None = None
        self._path_points: list[_DetourPathPoint] = []
        self._candidates: list[_CandidateInfo] = []
        self._selected_candidate: _CandidateInfo | None = None
        self._last_error = ""
        self._panel = _RawDetourPathInspectorPanel()
        self._editor.register_tool_inspector_panel(_PANEL_KEY, self._panel)

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
            self._editor.show_tool_inspector_panel(_PANEL_KEY, "Raw Detour Path Debug")
            self._update_panel()
            log.info("[RawDetourPathDebugTool] enabled")
            return

        self._editor.remove_viewport_click_interceptor(self._on_viewport_click)
        self._editor.remove_viewport_overlay_drawer(self._draw_overlay)
        self._start = None
        self._end = None
        self._path_points = []
        self._candidates = []
        self._selected_candidate = None
        self._last_error = "Tool is disabled."
        self._update_panel()
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
            self._candidates = []
            self._selected_candidate = None
            self._last_error = ""
            self._update_panel()
            log.info(
                "[RawDetourPathDebugTool] start set: "
                f"({point[0]:.3f}, {point[1]:.3f}, {point[2]:.3f})"
            )
            return

        self._end = point
        self._last_error = ""
        self._update_panel()
        log.info(
            "[RawDetourPathDebugTool] end set: "
            f"({point[0]:.3f}, {point[1]:.3f}, {point[2]:.3f})"
        )
        self._rebuild_path()

    def _rebuild_path(self) -> None:
        if self._start is None or self._end is None:
            return

        result = self._find_path_result(self._start, self._end)
        if result is None or not result.success:
            log.error("[RawDetourPathDebugTool] failed: PathfindingWorld did not return a path")
            self._path_points = []
            self._selected_candidate = None
            self._last_error = "PathfindingWorld did not return a path."
            self._update_panel()
            return

        self._path_points = _detailed_path_points(result.path)
        if not self._path_points:
            log.error("[RawDetourPathDebugTool] Detour returned empty path")
            self._selected_candidate = _candidate_info(result.candidate)
            self._last_error = "Detour returned empty path."
            self._update_panel()
            return

        candidate = result.candidate
        self._selected_candidate = _candidate_info(candidate)
        self._last_error = ""
        self._update_panel()
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

    def _find_path_result(
        self,
        start: tuple[float, float, float],
        end: tuple[float, float, float],
    ):
        scene = self._editor.scene
        if scene is None:
            log.error("[RawDetourPathDebugTool] failed: editor scene is not available")
            return None

        try:
            from termin.navmesh import PathfindingWorld
        except Exception as e:
            log.error(f"[RawDetourPathDebugTool] failed to import termin.navmesh: {e}")
            return None

        world = PathfindingWorld.ensure_scene(scene)
        if world is None:
            log.error("[RawDetourPathDebugTool] failed: PathfindingWorld extension is unavailable")
            self._candidates = []
            self._last_error = "PathfindingWorld extension is unavailable."
            self._update_panel()
            return None

        candidates = world.candidates_for_world_points(start, end)
        self._candidates = [_candidate_info(candidate) for candidate in candidates]
        self._selected_candidate = None
        for candidate in candidates:
            log.info(
                "[RawDetourPathDebugTool] candidate: "
                f"entity='{candidate.entity_name}' navmesh_uuid='{candidate.navmesh_uuid}' "
                f"start_distance={candidate.start_distance_sq ** 0.5:.3f} "
                f"end_distance={candidate.end_distance_sq ** 0.5:.3f} "
                f"start_over_poly={1 if candidate.start_over_poly else 0} "
                f"end_over_poly={1 if candidate.end_over_poly else 0}"
            )

        if not candidates:
            log.error("[RawDetourPathDebugTool] failed: DetourPathfindingWorldComponent not found")
            self._last_error = "DetourPathfindingWorldComponent not found."
            self._update_panel()
            return None

        return world.find_detailed_path_world(start, end)

    def _update_panel(self) -> None:
        self._panel.update(
            enabled=self._enabled,
            start=self._start,
            end=self._end,
            path_points=self._path_points,
            candidates=self._candidates,
            selected_candidate=self._selected_candidate,
            error=self._last_error,
        )

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
            if a.off_mesh_connection:
                color = _COLOR_OFFMESH
            elif a.linear_segment:
                color = _COLOR_LINEAR
            else:
                color = _COLOR_STANDARD
            renderer.line(_vec3(a.point), _vec3(b.point), color, False)

        for point in self._path_points:
            if point.off_mesh_connection:
                color = _COLOR_OFFMESH
            elif point.linear_segment:
                color = _COLOR_LINEAR
            else:
                color = _COLOR_POINT
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
                poly_type=int(item["poly_type"]),
                area=int(item["area"]),
                off_mesh_connection=bool(item["off_mesh_connection"]),
                off_mesh_user_id=int(item["off_mesh_user_id"]),
                linear_segment=bool(item["linear_segment"]),
                linear_user_id=int(item["linear_user_id"]),
            )
        )
    return points


def _candidate_info(candidate) -> _CandidateInfo:
    return _CandidateInfo(
        entity_name=str(candidate.entity_name),
        navmesh_uuid=str(candidate.navmesh_uuid),
        start_distance_sq=float(candidate.start_distance_sq),
        end_distance_sq=float(candidate.end_distance_sq),
        start_over_poly=bool(candidate.start_over_poly),
        end_over_poly=bool(candidate.end_over_poly),
    )


def _format_optional_point(point: tuple[float, float, float] | None) -> str:
    if point is None:
        return "<unset>"
    return _format_point(point)


def _format_point(point: tuple[float, float, float]) -> str:
    return f"({point[0]:.3f}, {point[1]:.3f}, {point[2]:.3f})"


def _draw_marker(renderer, point: tuple[float, float, float], color: Color4, radius: float) -> None:
    renderer.sphere_wireframe(_vec3(point), radius, color, 8, False)


def _vec3(point: tuple[float, float, float]) -> Vec3:
    return Vec3(point[0], point[1], point[2])
