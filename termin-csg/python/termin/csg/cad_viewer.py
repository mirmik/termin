"""Standalone CSG CAD viewport widgets and renderer."""

from __future__ import annotations

import uuid

import numpy as np

from tcbase import MouseButton, log
from tcgui.widgets.events import MouseEvent, MouseWheelEvent
from tcgui.widgets.widget import Widget
from tgfx import (
    CULL_NONE,
    PIXEL_D32F,
    PIXEL_RGBA8,
    Tgfx2Context,
    Tgfx2ShaderStage,
    draw_tc_mesh,
)
from tmesh import TcAttribType, TcDrawMode, TcMesh, TcVertexLayout

from termin.csg import to_mesh3
from termin.csg.document_eval import evaluate_document
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
        self._dragging = False
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
            self._dragging = True
            self._drag_x = float(event.x)
            self._drag_y = float(event.y)
            return True
        return False

    def on_mouse_up(self, event: MouseEvent) -> None:
        self._dragging = False

    def on_mouse_move(self, event: MouseEvent) -> None:
        if not self._dragging:
            return
        x = float(event.x)
        y = float(event.y)
        self.camera.orbit(x - self._drag_x, y - self._drag_y)
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

    def render_document(
        self,
        document: ProceduralMeshDocument,
        camera: OrbitCamera,
        width: int,
        height: int,
        draft_points: list[tuple[float, float, float]] | None = None,
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

        reference_meshes = build_reference_meshes()
        solid_meshes, line_meshes = build_document_meshes(document)
        if draft_points is not None:
            draft_mesh = _build_polyline_mesh(draft_points, False, "cad-draft-polyline")
            if draft_mesh is not None:
                line_meshes.append(draft_mesh)

        ctx.set_depth_test(False)
        ctx.set_depth_write(False)
        for mesh, color in reference_meshes:
            _push_draw_state(ctx, mvp, color)
            draw_tc_mesh(ctx, mesh)

        ctx.set_depth_test(True)
        ctx.set_depth_write(True)
        for mesh in solid_meshes:
            _push_draw_state(ctx, mvp, (0.12, 0.72, 0.95, 1.0))
            draw_tc_mesh(ctx, mesh)

        ctx.set_depth_test(False)
        ctx.set_depth_write(False)
        for mesh in line_meshes:
            _push_draw_state(ctx, mvp, (0.92, 0.96, 1.0, -1.0))
            draw_tc_mesh(ctx, mesh)

        ctx.end_pass()
        if opened_frame:
            ctx.end_frame()
        return self.color_tex

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


def build_document_meshes(document: ProceduralMeshDocument) -> tuple[list[TcMesh], list[TcMesh]]:
    solid_meshes: list[TcMesh] = []
    line_meshes: list[TcMesh] = []
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
            line_meshes.append(_build_edge_mesh(transformed, triangles, f"cad-solid-wire-{index}"))
        except Exception as e:
            log.error(f"[CsgCad] failed to build solid preview mesh: {e}")

    for sketch in document.items:
        for contour in sketch.contours:
            points = sketch.contour_points(contour)
            line_mesh = _build_polyline_mesh(points, True, f"cad-contour-{contour.id}")
            if line_mesh is not None:
                line_meshes.append(line_mesh)
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
    solid_meshes, line_meshes = build_document_meshes(document)
    for solid_mesh in solid_meshes:
        _collect_mesh_vertices(solid_mesh, vertices)
    for line_mesh in line_meshes:
        _collect_mesh_vertices(line_mesh, vertices)
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
    ctx.set_uniform_mat4("u_mvp", gpu_mvp.reshape(-1).tolist(), False)
    ctx.set_uniform_vec4("u_color", color[0], color[1], color[2], color[3])


__all__ = [
    "CadViewportWidget",
    "CsgSceneRenderer",
    "build_reference_meshes",
    "build_document_meshes",
    "document_bounds",
]
