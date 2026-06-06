"""Standalone CSG CAD viewport widgets and renderer."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from math import cos, sin, tau

import numpy as np

from tcbase import MouseButton, log
from tcbase._geom_native import Vec3
from tcgui.widgets.events import MouseEvent, MouseWheelEvent
from tcgui.widgets.widget import Widget
from tgfx import (
    Color4,
    CULL_NONE,
    ImmediateRenderer,
    PIXEL_D32F,
    PIXEL_RGBA8,
    Tgfx2Context,
    Tgfx2ShaderStage,
    draw_tc_mesh,
)
from tmesh import TcAttribType, TcDrawMode, TcMesh, TcVertexLayout

from termin.csg import to_mesh3
from termin.csg.document_eval import evaluate_document
from termin.csg.document_visual_model import build_document_visual_model
from termin.csg.procedural_document import ProceduralMeshDocument
from termin.csg.viewer_camera import OrbitCamera


_VERT_SRC = """#version 450 core
#ifdef VULKAN
layout(push_constant) uniform PCBlock {
    mat4 u_mvp;
    vec4 u_color;
} pc;
#define U_MVP pc.u_mvp
#else
uniform mat4 u_mvp;
#define U_MVP u_mvp
#endif
layout(location=0) in vec3 a_position;
layout(location=0) out vec3 v_world_pos;
void main() {
    v_world_pos = a_position;
    gl_Position = U_MVP * vec4(a_position, 1.0);
}
"""

_FRAG_SRC = """#version 450 core
#ifdef VULKAN
layout(push_constant) uniform PCBlock {
    mat4 u_mvp;
    vec4 u_color;
} pc;
#define U_COLOR pc.u_color
#else
uniform vec4 u_color;
#define U_COLOR u_color
#endif
layout(location=0) in vec3 v_world_pos;
layout(location=0) out vec4 frag_color;
void main() {
    vec3 color = U_COLOR.rgb;
    if (U_COLOR.a >= 0.0) {
        vec3 n = normalize(cross(dFdy(v_world_pos), dFdx(v_world_pos)));
        vec3 light_ray_dir = normalize(vec3(0.35, 0.45, -0.82));
        float lambert = max(dot(n, -light_ray_dir), 0.0);
        float intensity = 0.32 + 0.68 * lambert;
        color *= intensity;
    }
    frag_color = vec4(color, abs(U_COLOR.a));
}
"""


class CadViewportWidget(Widget):
    """tcgui widget that displays a pre-rendered CSG scene texture."""

    def __init__(self, camera: OrbitCamera) -> None:
        super().__init__()
        self.focusable = True
        self.camera = camera
        self.texture = None
        self.texture_size = (0, 0)
        self.on_changed = None
        self.on_scene_click = None
        self._drag_mode = ""
        self._drag_x = 0.0
        self._drag_y = 0.0

    def render(self, renderer) -> None:
        current_size = (max(int(self.width), 1), max(int(self.height), 1))
        if self.texture_size != current_size:
            self._notify_changed()
        renderer.draw_rect(self.x, self.y, self.width, self.height, (0.08, 0.085, 0.095, 1.0))
        if self.texture is not None:
            renderer.draw_texture(
                self.x,
                self.y,
                self.width,
                self.height,
                self.texture,
                int(self.texture_size[0]),
                int(self.texture_size[1]),
            )

    def on_mouse_down(self, event: MouseEvent) -> bool:
        if event.button == MouseButton.LEFT:
            if self.on_scene_click is not None:
                handled = self.on_scene_click(
                    float(event.x - self.x),
                    float(event.y - self.y),
                    max(int(self.width), 1),
                    max(int(self.height), 1),
                )
                if handled:
                    self._notify_changed()
                    return True
            return True
        if event.button == MouseButton.MIDDLE:
            self._begin_drag("orbit", event)
            return True
        if event.button == MouseButton.RIGHT:
            self._begin_drag("pan", event)
            return True
        return False

    def _begin_drag(self, mode: str, event: MouseEvent) -> None:
        self._drag_mode = mode
        self._drag_x = float(event.x)
        self._drag_y = float(event.y)

    def on_mouse_up(self, event: MouseEvent) -> None:
        self._drag_mode = ""

    def on_mouse_move(self, event: MouseEvent) -> None:
        if not self._drag_mode:
            return
        x = float(event.x)
        y = float(event.y)
        dx = x - self._drag_x
        dy = y - self._drag_y
        if self._drag_mode == "orbit":
            self.camera.orbit(dx, dy)
        elif self._drag_mode == "pan":
            self.camera.pan(-dx, dy)
        self._drag_x = x
        self._drag_y = y
        self._notify_changed()

    def on_mouse_wheel(self, event: MouseWheelEvent) -> bool:
        self.camera.zoom(float(event.dy))
        self._notify_changed()
        return True

    def _notify_changed(self) -> None:
        if self.on_changed is not None:
            self.on_changed()


class CsgSceneRenderer:
    """Render a ProceduralMeshDocument into a texture."""

    def __init__(self, graphics: Tgfx2Context) -> None:
        self.graphics = graphics
        self.ctx = graphics.context
        self.vs = graphics.device.create_shader(Tgfx2ShaderStage.Vertex, _VERT_SRC)
        self.fs = graphics.device.create_shader(Tgfx2ShaderStage.Fragment, _FRAG_SRC)
        self.color_tex = None
        self.depth_tex = None
        self.size = (0, 0)
        self.reference_geometry = build_reference_geometry()
        self.immediate_renderer = ImmediateRenderer()
        self._preview_key = None
        self._solid_meshes: list[TcMesh] = []
        self._immediate_geometry = ImmediateGeometry()

    def render_document(
        self,
        document: ProceduralMeshDocument,
        camera: OrbitCamera,
        width: int,
        height: int,
        draft_points: list[tuple[float, float, float]] | None = None,
        selected_node_data: tuple[str, str] | None = None,
        show_wireframe: bool = True,
        preview_key=None,
    ):
        width = max(int(width), 1)
        height = max(int(height), 1)
        self._ensure_textures(width, height)
        mvp = camera.view_projection(width, height)

        ctx = self.ctx
        opened_frame = not ctx.in_frame
        if opened_frame:
            ctx.begin_frame()
        ctx.begin_pass(self.color_tex, self.depth_tex, True, 0.10, 0.10, 0.12, 1.0, 1.0, True)
        ctx.set_viewport(0, 0, width, height)
        ctx.set_depth_test(True)
        ctx.set_depth_write(True)
        ctx.set_blend(False)
        ctx.set_cull(CULL_NONE)
        ctx.bind_shader(self.vs, self.fs)

        self._ensure_preview_meshes(document, draft_points, selected_node_data, show_wireframe, preview_key)

        ctx.set_depth_test(True)
        ctx.set_depth_write(True)
        for mesh in self._solid_meshes:
            _push_draw_state(ctx, mvp, (0.12, 0.72, 0.95, 1.0))
            draw_tc_mesh(ctx, mesh)

        immediate = self.immediate_renderer
        immediate.begin()
        self.reference_geometry.emit(immediate)
        self._immediate_geometry.emit(immediate)
        view = camera.view_matrix()
        projection = camera.projection_matrix(width, height)
        immediate.flush(ctx, view, projection, False, True)
        immediate.flush_depth(ctx, view, projection, True)

        ctx.end_pass()
        if opened_frame:
            ctx.end_frame()
        return self.color_tex

    def _ensure_preview_meshes(
        self,
        document: ProceduralMeshDocument,
        draft_points: list[tuple[float, float, float]] | None,
        selected_node_data: tuple[str, str] | None,
        show_wireframe: bool,
        preview_key,
    ) -> None:
        if preview_key is not None and preview_key == self._preview_key:
            return

        solid_meshes = build_document_solid_meshes(document)
        immediate_geometry = build_document_immediate_geometry(
            document,
            draft_points,
            selected_node_data,
            show_wireframe=show_wireframe,
        )
        self._solid_meshes = solid_meshes
        self._immediate_geometry = immediate_geometry
        self._preview_key = preview_key

    def close(self) -> None:
        if self.color_tex is not None:
            self.graphics.destroy_texture(self.color_tex)
            self.color_tex = None
        if self.depth_tex is not None:
            self.graphics.destroy_texture(self.depth_tex)
            self.depth_tex = None
        self.graphics.device.destroy_shader(self.vs)
        self.graphics.device.destroy_shader(self.fs)

    def _ensure_textures(self, width: int, height: int) -> None:
        if self.size == (width, height):
            return
        if self.color_tex is not None:
            self.graphics.destroy_texture(self.color_tex)
        if self.depth_tex is not None:
            self.graphics.destroy_texture(self.depth_tex)
        self.color_tex = self.graphics.create_color_attachment(width, height, PIXEL_RGBA8)
        self.depth_tex = self.graphics.create_depth_attachment(width, height, PIXEL_D32F)
        self.size = (width, height)


@dataclass
class ImmediateLineSegment:
    start: tuple[float, float, float]
    end: tuple[float, float, float]
    color: tuple[float, float, float, float]
    depth_test: bool = False


@dataclass
class ImmediatePolyline:
    points: list[tuple[float, float, float]]
    color: tuple[float, float, float, float]
    closed: bool = False
    depth_test: bool = False


@dataclass
class ImmediatePointMarker:
    point: tuple[float, float, float]
    color: tuple[float, float, float, float]
    radius: float
    depth_test: bool = False


@dataclass
class ImmediateGeometry:
    lines: list[ImmediateLineSegment] = field(default_factory=list)
    polylines: list[ImmediatePolyline] = field(default_factory=list)
    points: list[ImmediatePointMarker] = field(default_factory=list)

    def emit(self, renderer: ImmediateRenderer) -> None:
        for line in self.lines:
            renderer.line(
                _vec3(line.start),
                _vec3(line.end),
                _color4(line.color),
                line.depth_test,
            )
        for polyline in self.polylines:
            if len(polyline.points) < 2:
                continue
            renderer.polyline(
                [_vec3(point) for point in polyline.points],
                _color4(polyline.color),
                polyline.closed,
                polyline.depth_test,
            )
        for point in self.points:
            center = _vec3(point.point)
            color = _color4(point.color)
            renderer.circle(center, Vec3(0.0, 0.0, 1.0), point.radius, color, 12, point.depth_test)
            renderer.circle(center, Vec3(0.0, 1.0, 0.0), point.radius, color, 12, point.depth_test)
            renderer.circle(center, Vec3(1.0, 0.0, 0.0), point.radius, color, 12, point.depth_test)

    def collect_vertices(self, vertices: list[tuple[float, float, float]]) -> None:
        for line in self.lines:
            vertices.append(line.start)
            vertices.append(line.end)
        for polyline in self.polylines:
            vertices.extend(polyline.points)
        for point in self.points:
            x, y, z = point.point
            r = point.radius
            vertices.append((x - r, y - r, z - r))
            vertices.append((x + r, y + r, z + r))


def build_document_solid_meshes(document: ProceduralMeshDocument) -> list[TcMesh]:
    solid_meshes: list[TcMesh] = []
    for index, evaluated in enumerate(evaluate_document(document)):
        try:
            mesh = to_mesh3(evaluated.solid, f"cad-solid-{index}", "", True)
            vertices = np.asarray(mesh.vertices, dtype=np.float32).reshape(-1, 3)
            transformed = np.array(
                [evaluated.point_transform((float(v[0]), float(v[1]), float(v[2]))) for v in vertices],
                dtype=np.float32,
            )
            triangles = np.asarray(mesh.triangles, dtype=np.uint32).reshape(-1)
            solid_meshes.append(_build_triangle_mesh(transformed, triangles, f"cad-solid-{index}"))
        except Exception as e:
            log.error(f"[CsgCad] failed to build solid preview mesh: {e}")
    return solid_meshes


def build_document_immediate_geometry(
    document: ProceduralMeshDocument,
    draft_points: list[tuple[float, float, float]] | None,
    selected_node_data: tuple[str, str] | None,
    show_wireframe: bool = True,
) -> ImmediateGeometry:
    lines: list[ImmediateLineSegment] = []
    polylines: list[ImmediatePolyline] = []
    points: list[ImmediatePointMarker] = []

    if show_wireframe:
        for evaluated in evaluate_document(document):
            if selected_node_data == ("operation", evaluated.operation_id):
                edge_color = (0.85, 1.0, 1.0, 1.0)
            else:
                edge_color = (0.0, 0.95, 0.95, 0.85)
            try:
                mesh = to_mesh3(evaluated.solid, "cad-solid-wire", "", True)
                vertices = np.asarray(mesh.vertices, dtype=np.float32).reshape(-1, 3)
                transformed = [
                    evaluated.point_transform((float(v[0]), float(v[1]), float(v[2])))
                    for v in vertices
                ]
                triangles = np.asarray(mesh.triangles, dtype=np.uint32).reshape(-1)
                for start, end in _edge_segments_from_triangles(transformed, triangles):
                    lines.append(ImmediateLineSegment(start, end, edge_color, False))
            except Exception as e:
                log.error(f"[CsgCad] failed to build solid edge immediate preview: {e}")

    visual_model = build_document_visual_model(document, draft_points, selected_node_data)
    for polyline in visual_model.polylines:
        polylines.append(
            ImmediatePolyline(
                points=polyline.points[:],
                color=polyline.color,
                closed=polyline.closed,
                depth_test=polyline.depth_test,
            )
        )
    for point in visual_model.points:
        points.append(
            ImmediatePointMarker(
                point=point.point,
                color=point.color,
                radius=point.radius,
                depth_test=point.depth_test,
            )
        )
    return ImmediateGeometry(lines=lines, polylines=polylines, points=points)


def build_document_line_meshes(
    document: ProceduralMeshDocument,
    draft_points: list[tuple[float, float, float]] | None,
    selected_node_data: tuple[str, str] | None,
) -> list[tuple[TcMesh, tuple[float, float, float, float]]]:
    line_meshes: list[tuple[TcMesh, tuple[float, float, float, float]]] = []
    for index, evaluated in enumerate(evaluate_document(document)):
        edge_mesh = _build_evaluated_solid_edge_mesh(evaluated, f"cad-solid-wire-{index}")
        if edge_mesh is None:
            continue
        if selected_node_data == ("operation", evaluated.operation_id):
            line_meshes.append((edge_mesh, (0.85, 1.0, 1.0, 1.0)))
        else:
            line_meshes.append((edge_mesh, (0.0, 0.95, 0.95, 0.85)))

    visual_model = build_document_visual_model(document, draft_points, selected_node_data)
    for index, polyline in enumerate(visual_model.polylines):
        line_mesh = _build_polyline_mesh(polyline.points, polyline.closed, f"cad-polyline-{index}")
        if line_mesh is not None:
            line_meshes.append((line_mesh, polyline.color))
    for index, point in enumerate(visual_model.points):
        point_mesh = _build_point_marker_mesh(point.point, point.radius, f"cad-point-{index}")
        line_meshes.append((point_mesh, point.color))
    return line_meshes


def _build_evaluated_solid_edge_mesh(evaluated, name: str) -> TcMesh | None:
    try:
        mesh = to_mesh3(evaluated.solid, name, "", True)
        vertices = np.asarray(mesh.vertices, dtype=np.float32).reshape(-1, 3)
        transformed = np.array(
            [evaluated.point_transform((float(v[0]), float(v[1]), float(v[2]))) for v in vertices],
            dtype=np.float32,
        )
        triangles = np.asarray(mesh.triangles, dtype=np.uint32).reshape(-1)
        return _build_edge_mesh(transformed, triangles, name)
    except Exception as e:
        log.error(f"[CsgCad] failed to build solid edge preview mesh: {e}")
    return None


def build_reference_geometry() -> ImmediateGeometry:
    """Build persistent viewport reference grid and coordinate axes."""

    lines: list[ImmediateLineSegment] = []
    extent = 10
    grid_color = (0.23, 0.25, 0.29, 1.0)
    x_axis_color = (0.92, 0.18, 0.18, 1.0)
    y_axis_color = (0.18, 0.82, 0.22, 1.0)
    for i in range(-extent, extent + 1):
        value = float(i)
        lines.append(
            ImmediateLineSegment(
                (-extent, value, 0.0),
                (extent, value, 0.0),
                x_axis_color if i == 0 else grid_color,
                True,
            )
        )
        lines.append(
            ImmediateLineSegment(
                (value, -extent, 0.0),
                (value, extent, 0.0),
                y_axis_color if i == 0 else grid_color,
                True,
            )
        )

    axis_len = float(extent)
    lines.extend(
        [
            ImmediateLineSegment((0.0, 0.0, 0.0), (0.0, 0.0, axis_len * 0.5), (0.25, 0.45, 1.0, 1.0), True),
        ]
    )
    return ImmediateGeometry(lines=lines)


def build_document_meshes(document: ProceduralMeshDocument) -> tuple[list[TcMesh], list[TcMesh]]:
    solid_meshes = build_document_solid_meshes(document)
    line_meshes = [mesh for mesh, color in build_document_line_meshes(document, None, None)]
    return solid_meshes, line_meshes


def build_reference_meshes() -> list[tuple[TcMesh, tuple[float, float, float, float]]]:
    """Build persistent viewport reference grid and coordinate axes."""

    grid_segments: list[tuple[tuple[float, float, float], tuple[float, float, float]]] = []
    extent = 10
    for i in range(-extent, extent + 1):
        value = float(i)
        grid_segments.append(((-extent, value, 0.0), (extent, value, 0.0)))
        grid_segments.append(((value, -extent, 0.0), (value, extent, 0.0)))

    axis_len = float(extent)
    return [
        (_build_line_segments_mesh(grid_segments, "cad-reference-grid"), (0.23, 0.25, 0.29, -1.0)),
        (
            _build_line_segments_mesh([((-axis_len, 0.0, 0.0), (axis_len, 0.0, 0.0))], "cad-x-axis"),
            (0.92, 0.18, 0.18, -1.0),
        ),
        (
            _build_line_segments_mesh([((0.0, -axis_len, 0.0), (0.0, axis_len, 0.0))], "cad-y-axis"),
            (0.18, 0.82, 0.22, -1.0),
        ),
        (
            _build_line_segments_mesh([((0.0, 0.0, 0.0), (0.0, 0.0, axis_len * 0.5))], "cad-z-axis"),
            (0.25, 0.45, 1.0, -1.0),
        ),
    ]


def document_bounds(document: ProceduralMeshDocument):
    vertices: list[tuple[float, float, float]] = []
    solid_meshes = build_document_solid_meshes(document)
    immediate_geometry = build_document_immediate_geometry(document, None, None)
    for solid_mesh in solid_meshes:
        _collect_mesh_vertices(solid_mesh, vertices)
    immediate_geometry.collect_vertices(vertices)
    if not vertices:
        vertices.append((-1.0, -1.0, -1.0))
        vertices.append((1.0, 1.0, 1.0))
    arr = np.asarray(vertices, dtype=np.float32)
    return arr.min(axis=0), arr.max(axis=0)


def _collect_mesh_vertices(mesh: TcMesh, vertices: list[tuple[float, float, float]]) -> None:
    arr = np.asarray(mesh.vertices, dtype=np.float32).reshape(-1, 3)
    for v in arr:
        vertices.append((float(v[0]), float(v[1]), float(v[2])))


def _build_triangle_mesh(vertices: np.ndarray, indices: np.ndarray, name: str) -> TcMesh:
    layout = _position_layout()
    return TcMesh.from_interleaved(
        vertices=np.ascontiguousarray(vertices.reshape(-1), dtype=np.float32),
        vertex_count=vertices.shape[0],
        indices=np.ascontiguousarray(indices, dtype=np.uint32),
        layout=layout,
        name=name,
        uuid=str(uuid.uuid4()),
        draw_mode=TcDrawMode.TRIANGLES,
    )


def _build_edge_mesh(vertices: np.ndarray, triangles: np.ndarray, name: str) -> TcMesh:
    edges = set()
    for i in range(0, len(triangles), 3):
        a = int(triangles[i])
        b = int(triangles[i + 1])
        c = int(triangles[i + 2])
        for x, y in ((a, b), (b, c), (c, a)):
            edges.add((min(x, y), max(x, y)))
    indices: list[int] = []
    for a, b in sorted(edges):
        indices.append(a)
        indices.append(b)
    return TcMesh.from_interleaved(
        vertices=np.ascontiguousarray(vertices.reshape(-1), dtype=np.float32),
        vertex_count=vertices.shape[0],
        indices=np.ascontiguousarray(np.array(indices, dtype=np.uint32), dtype=np.uint32),
        layout=_position_layout(),
        name=name,
        uuid=str(uuid.uuid4()),
        draw_mode=TcDrawMode.LINES,
    )


def _edge_segments_from_triangles(
    vertices: list[tuple[float, float, float]],
    triangles: np.ndarray,
) -> list[tuple[tuple[float, float, float], tuple[float, float, float]]]:
    edges = set()
    for i in range(0, len(triangles), 3):
        a = int(triangles[i])
        b = int(triangles[i + 1])
        c = int(triangles[i + 2])
        for x, y in ((a, b), (b, c), (c, a)):
            edges.add((min(x, y), max(x, y)))
    return [(vertices[a], vertices[b]) for a, b in sorted(edges)]


def _build_point_marker_mesh(point: tuple[float, float, float], radius: float, name: str) -> TcMesh:
    segments: list[tuple[tuple[float, float, float], tuple[float, float, float]]] = []
    steps = 8
    cx = float(point[0])
    cy = float(point[1])
    cz = float(point[2])
    for plane in ("xy", "xz", "yz"):
        ring: list[tuple[float, float, float]] = []
        for i in range(steps):
            angle = tau * float(i) / float(steps)
            ca = cos(angle) * radius
            sa = sin(angle) * radius
            if plane == "xy":
                ring.append((cx + ca, cy + sa, cz))
            elif plane == "xz":
                ring.append((cx + ca, cy, cz + sa))
            else:
                ring.append((cx, cy + ca, cz + sa))
        for i in range(steps):
            segments.append((ring[i], ring[(i + 1) % steps]))
    return _build_line_segments_mesh(segments, name)


def _build_polyline_mesh(points, closed: bool, name: str) -> TcMesh | None:
    if len(points) < 2:
        return None
    vertices = np.asarray(points, dtype=np.float32).reshape(-1, 3)
    indices: list[int] = []
    for i in range(len(points) - 1):
        indices.append(i)
        indices.append(i + 1)
    if closed:
        indices.append(len(points) - 1)
        indices.append(0)
    return TcMesh.from_interleaved(
        vertices=np.ascontiguousarray(vertices.reshape(-1), dtype=np.float32),
        vertex_count=vertices.shape[0],
        indices=np.ascontiguousarray(np.array(indices, dtype=np.uint32), dtype=np.uint32),
        layout=_position_layout(),
        name=name,
        uuid=str(uuid.uuid4()),
        draw_mode=TcDrawMode.LINES,
    )


def _build_line_segments_mesh(
    segments: list[tuple[tuple[float, float, float], tuple[float, float, float]]],
    name: str,
) -> TcMesh:
    vertices: list[tuple[float, float, float]] = []
    indices: list[int] = []
    for start, end in segments:
        index = len(vertices)
        vertices.append(start)
        vertices.append(end)
        indices.append(index)
        indices.append(index + 1)
    vertices_arr = np.asarray(vertices, dtype=np.float32).reshape(-1, 3)
    return TcMesh.from_interleaved(
        vertices=np.ascontiguousarray(vertices_arr.reshape(-1), dtype=np.float32),
        vertex_count=vertices_arr.shape[0],
        indices=np.ascontiguousarray(np.array(indices, dtype=np.uint32), dtype=np.uint32),
        layout=_position_layout(),
        name=name,
        uuid=str(uuid.uuid4()),
        draw_mode=TcDrawMode.LINES,
    )


def _position_layout() -> TcVertexLayout:
    layout = TcVertexLayout()
    layout.add("position", 3, TcAttribType.FLOAT32, 0)
    return layout


def _push_draw_state(ctx, mvp, color) -> None:
    gpu_mvp = np.ascontiguousarray(mvp.T, dtype=np.float32)
    color_arr = np.ascontiguousarray(np.array(color, dtype=np.float32), dtype=np.float32)
    pc = np.concatenate((gpu_mvp.reshape(-1), color_arr)).view(np.uint8)
    ctx.set_push_constants(np.ascontiguousarray(pc, dtype=np.uint8))


def _line_color(color: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    return (color[0], color[1], color[2], -abs(color[3]))


def _vec3(point: tuple[float, float, float]) -> Vec3:
    return Vec3(float(point[0]), float(point[1]), float(point[2]))


def _color4(color: tuple[float, float, float, float]) -> Color4:
    return Color4(float(color[0]), float(color[1]), float(color[2]), abs(float(color[3])))


__all__ = [
    "CadViewportWidget",
    "CsgSceneRenderer",
    "ImmediateGeometry",
    "build_document_immediate_geometry",
    "build_reference_geometry",
    "build_reference_meshes",
    "build_document_line_meshes",
    "build_document_meshes",
    "build_document_solid_meshes",
    "document_bounds",
]
