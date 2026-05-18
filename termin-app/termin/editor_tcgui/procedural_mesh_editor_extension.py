"""tcgui editor extension for ProceduralMeshComponent."""

from __future__ import annotations

from tcbase import log
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


class ProceduralMeshEditorExtension:
    def __init__(self) -> None:
        self._editor = None
        self._entity = None
        self._component_ref = None
        self._mode = "idle"
        self._mode_label = Label()
        self._draft_points: list[tuple[float, float, float]] = []
        self._closed_contours: list[list[tuple[float, float, float]]] = []

    def attach(self, editor, entity, component_ref) -> None:
        self._editor = editor
        self._entity = entity
        self._component_ref = component_ref
        editor.add_viewport_click_interceptor(self._on_viewport_click)
        editor.add_viewport_overlay_drawer(self._draw_overlay)
        log.info("[ProceduralMeshEditor] extension attached")

    def detach(self) -> None:
        editor = self._editor
        if editor is not None:
            editor.remove_viewport_click_interceptor(self._on_viewport_click)
            editor.remove_viewport_overlay_drawer(self._draw_overlay)
        self._editor = None
        self._entity = None
        self._component_ref = None
        self._mode = "idle"
        self._draft_points = []
        self._closed_contours = []
        log.info("[ProceduralMeshEditor] extension detached")

    def build_panel(self):
        root = VStack()
        root.spacing = 4

        title = Label()
        title.text = "Procedural Geometry"
        root.add_child(title)

        self._mode_label.text = self._mode_text()
        self._mode_label.color = (0.55, 0.60, 0.68, 1.0)
        root.add_child(self._mode_label)

        row = HStack()
        row.spacing = 4
        row.preferred_height = px(28)
        row.add_child(self._make_button("Draw Sketch", "draw_sketch"))
        close_btn = Button()
        close_btn.text = "Close Contour"
        close_btn.on_click = self._close_contour
        row.add_child(close_btn)
        root.add_child(row)

        row2 = HStack()
        row2.spacing = 4
        row2.preferred_height = px(28)
        clear_btn = Button()
        clear_btn.text = "Clear Sketch"
        clear_btn.on_click = self._clear_sketch
        row2.add_child(clear_btn)
        row2.add_child(self._make_button("Clear Tool", "idle"))
        root.add_child(row2)

        return root

    def _make_button(self, text: str, mode: str) -> Button:
        btn = Button()
        btn.text = text
        btn.on_click = lambda m=mode: self._set_mode(m)
        return btn

    def _set_mode(self, mode: str) -> None:
        self._mode = mode
        self._mode_label.text = self._mode_text()
        self._request_viewport_update()
        log.info(f"[ProceduralMeshEditor] mode={mode}")

    def _mode_text(self) -> str:
        return (
            f"Mode: {self._mode}; "
            f"draft points: {len(self._draft_points)}; "
            f"contours: {len(self._closed_contours)}"
        )

    def _refresh_mode_label(self) -> None:
        self._mode_label.text = self._mode_text()

    def _close_contour(self) -> None:
        if len(self._draft_points) < 3:
            log.error(
                "[ProceduralMeshEditor] cannot close contour: "
                f"need at least 3 points, got {len(self._draft_points)}"
            )
            return
        self._closed_contours.append(self._draft_points[:])
        self._draft_points = []
        self._refresh_mode_label()
        self._request_viewport_update()
        log.info(
            "[ProceduralMeshEditor] contour closed "
            f"contours={len(self._closed_contours)}"
        )

    def _clear_sketch(self) -> None:
        self._draft_points = []
        self._closed_contours = []
        self._refresh_mode_label()
        self._request_viewport_update()
        log.info("[ProceduralMeshEditor] sketch cleared")

    def _request_viewport_update(self) -> None:
        editor = self._editor
        if editor is not None:
            editor.request_viewport_update()

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
        if self._mode == "idle":
            return False

        picked_name = "<none>"
        if entity.valid():
            picked_name = entity.name

        point = self._click_point(
            x,
            y,
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
            log.error("[ProceduralMeshEditor] click ignored: no mesh hit and no OXY plane point")
            return True

        if has_mesh_hit:
            point_kind = "mesh"
        elif has_world_point:
            point_kind = "world"
        else:
            point_kind = "oxy"
        if self._mode == "draw_sketch":
            self._draft_points.append(point)
            self._refresh_mode_label()
            self._request_viewport_update()

        log.info(
            "[ProceduralMeshEditor] viewport click "
            f"mode={self._mode} screen=({x:.1f}, {y:.1f}) picked='{picked_name}' "
            f"{point_kind}=({point[0]:.3f}, {point[1]:.3f}, {point[2]:.3f}) "
            f"tri={triangle_index} draft_points={len(self._draft_points)}"
        )
        return True

    def _click_point(
        self,
        x: float,
        y: float,
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
        editor = self._editor
        if editor is None:
            return None
        return editor.world_point_on_oxy_plane(x, y)

    def _draw_overlay(self) -> None:
        entity = self._entity
        if entity is None or not entity.valid():
            return
        try:
            pose = entity.transform.global_pose()
            center = pose.lin
        except Exception as e:
            log.error(f"[ProceduralMeshEditor] overlay failed: {e}")
            return

        from termin.visualization.render.immediate import ImmediateRenderer

        renderer = ImmediateRenderer.instance()
        anchor_color = Color4(0.1, 0.9, 1.0, 1.0)
        radius = 0.35
        renderer.line(
            Vec3(center.x - radius, center.y, center.z),
            Vec3(center.x + radius, center.y, center.z),
            anchor_color,
            True,
        )
        renderer.line(
            Vec3(center.x, center.y - radius, center.z),
            Vec3(center.x, center.y + radius, center.z),
            anchor_color,
            True,
        )
        renderer.line(
            Vec3(center.x, center.y, center.z - radius),
            Vec3(center.x, center.y, center.z + radius),
            anchor_color,
            True,
        )
        self._draw_contours(renderer)

    def _draw_contours(self, renderer) -> None:
        contour_color = Color4(0.0, 0.95, 0.95, 1.0)
        draft_color = Color4(1.0, 0.78, 0.12, 1.0)
        point_color = Color4(1.0, 1.0, 1.0, 1.0)
        for contour in self._closed_contours:
            self._draw_polyline(renderer, contour, contour_color, True)
            self._draw_points(renderer, contour, point_color)
        self._draw_polyline(renderer, self._draft_points, draft_color, False)
        self._draw_points(renderer, self._draft_points, draft_color)

    def _draw_polyline(
        self,
        renderer,
        points: list[tuple[float, float, float]],
        color: Color4,
        closed: bool,
    ) -> None:
        if len(points) < 2:
            return
        for i in range(len(points) - 1):
            renderer.line(self._vec3(points[i]), self._vec3(points[i + 1]), color, False)
        if closed:
            renderer.line(self._vec3(points[-1]), self._vec3(points[0]), color, False)

    def _draw_points(
        self,
        renderer,
        points: list[tuple[float, float, float]],
        color: Color4,
    ) -> None:
        for point in points:
            renderer.sphere_wireframe(self._vec3(point), 0.055, color, 8, False)

    def _vec3(self, point: tuple[float, float, float]) -> Vec3:
        return Vec3(point[0], point[1], point[2])


def register_default_extension() -> None:
    register_component_editor_extension(
        "ProceduralMeshComponent",
        ProceduralMeshEditorExtension,
    )


__all__ = ["ProceduralMeshEditorExtension", "register_default_extension"]
