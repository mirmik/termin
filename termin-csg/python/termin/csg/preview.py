"""Standalone CSG mesh preview.

The viewer is local to termin-csg. It does not create scene entities or
renderer components, and it does not depend on tcplot. CSG results are
converted to TcMesh and rendered through termin-graphics draw_tc_mesh().
"""

from __future__ import annotations

import uuid

import numpy as np

from tcbase import Key, MouseButton
from termin.csg import Solid, to_mesh3, to_tc_mesh
from termin.csg.viewer_camera import OrbitCamera
from termin.display import SDLBackendWindow, quit_sdl, wait_sdl_events_timeout
from tgfx import (
    CULL_NONE,
    PIXEL_D32F,
    PIXEL_RGBA8,
    Tgfx2Context,
    Tgfx2ShaderStage,
    draw_tc_mesh,
)
from tmesh import TcAttribType, TcDrawMode, TcMesh, TcVertexLayout


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

_COLORS = (
    (0.12, 0.72, 0.95, 1.0),
    (1.00, 0.62, 0.16, 1.0),
    (0.46, 0.93, 0.35, 1.0),
    (0.90, 0.36, 0.95, 1.0),
)


def _mesh_bounds(meshes):
    lo = np.array((0.0, 0.0, 0.0), dtype=np.float32)
    hi = np.array((0.0, 0.0, 0.0), dtype=np.float32)
    have_any = False
    for mesh in meshes:
        vertices = np.asarray(mesh.vertices, dtype=np.float32)
        if vertices.size == 0:
            continue
        if have_any:
            lo = np.minimum(lo, vertices.min(axis=0))
            hi = np.maximum(hi, vertices.max(axis=0))
        else:
            lo = vertices.min(axis=0)
            hi = vertices.max(axis=0)
            have_any = True
    return lo, hi


def _build_line_mesh(mesh, name):
    vertices = np.asarray(mesh.vertices, dtype=np.float32)
    triangles = np.asarray(mesh.triangles, dtype=np.uint32)
    edges = set()
    for a, b, c in triangles:
        for i, j in ((a, b), (b, c), (c, a)):
            lo = int(min(i, j))
            hi = int(max(i, j))
            edges.add((lo, hi))

    if vertices.size == 0 or len(edges) == 0:
        return TcMesh()

    indices = []
    for a, b in sorted(edges):
        indices.append(a)
        indices.append(b)

    layout = TcVertexLayout()
    layout.add("position", 3, TcAttribType.FLOAT32, 0)
    return TcMesh.from_interleaved(
        vertices=np.ascontiguousarray(vertices.reshape(-1), dtype=np.float32),
        vertex_count=vertices.shape[0],
        indices=np.ascontiguousarray(np.array(indices, dtype=np.uint32), dtype=np.uint32),
        layout=layout,
        name=name,
        uuid=str(uuid.uuid4()),
        draw_mode=TcDrawMode.LINES,
    )


def _build_contour_mesh(contour, name):
    vertices = []
    indices = []

    def append_loop(points):
        start = len(vertices)
        for x, y in points:
            vertices.append((float(x), float(y), 0.0))
        count = len(points)
        for index in range(count):
            indices.append(start + index)
            indices.append(start + ((index + 1) % count))

    append_loop(contour.points)
    for hole in contour.holes:
        append_loop(hole)

    layout = TcVertexLayout()
    layout.add("position", 3, TcAttribType.FLOAT32, 0)
    return TcMesh.from_interleaved(
        vertices=np.ascontiguousarray(np.array(vertices, dtype=np.float32).reshape(-1), dtype=np.float32),
        vertex_count=len(vertices),
        indices=np.ascontiguousarray(np.array(indices, dtype=np.uint32), dtype=np.uint32),
        layout=layout,
        name=name,
        uuid=str(uuid.uuid4()),
        draw_mode=TcDrawMode.LINES,
    )


class _PreviewMesh:
    def __init__(self, solid, index):
        self.cpu_mesh = to_mesh3(solid, f"csg-preview-{index}")
        self.solid_mesh = to_tc_mesh(solid, f"csg-preview-solid-{index}", str(uuid.uuid4()))
        self.line_mesh = _build_line_mesh(self.cpu_mesh, f"csg-preview-wire-{index}")
        self.color = _COLORS[index % len(_COLORS)]
        self.line_color = (0.015, 0.020, 0.025, -1.0)
        self.draw_solid = True


class _PreviewContour:
    def __init__(self, contour, index):
        self.cpu_mesh = _contour_bounds_mesh(contour)
        self.solid_mesh = TcMesh()
        self.line_mesh = _build_contour_mesh(contour, f"csg-preview-contour-{index}")
        self.color = _COLORS[index % len(_COLORS)]
        self.line_color = (0.95, 0.95, 0.98, -1.0)
        self.draw_solid = False


def _contour_bounds_mesh(contour):
    vertices = [(float(x), float(y), 0.0) for x, y in contour.points]
    for hole in contour.holes:
        vertices.extend((float(x), float(y), 0.0) for x, y in hole)
    mesh = type("_ContourBoundsMesh", (), {})()
    mesh.vertices = vertices
    return mesh


def _items_to_preview_meshes(items):
    from termin.csg.cad import Contour

    meshes = []
    for index, item in enumerate(items):
        if type(item) is Solid:
            meshes.append(_PreviewMesh(item, index))
        elif type(item) is Contour:
            meshes.append(_PreviewContour(item, index))
        else:
            raise TypeError("draw() expects termin.csg.Solid or termin.csg.cad.Contour objects")
    return meshes


def _push_draw_state(ctx, mvp, color):
    gpu_mvp = np.ascontiguousarray(mvp.T, dtype=np.float32)
    color_arr = np.ascontiguousarray(np.array(color, dtype=np.float32), dtype=np.float32)
    pc = np.concatenate((gpu_mvp.reshape(-1), color_arr)).view(np.uint8)
    ctx.set_push_constants(np.ascontiguousarray(pc, dtype=np.uint8))


def _dispatch_event(window, camera, state, ev):
    event_type = ev.get("type")
    if event_type == "quit":
        window.set_should_close(True)
    elif event_type == "key_down":
        if int(ev.get("key", Key.UNKNOWN.value)) == Key.ESCAPE.value:
            window.set_should_close(True)
    elif event_type == "window_close":
        window.set_should_close(True)
    elif event_type == "mouse_down":
        if int(ev.get("button", MouseButton.LEFT.value)) == MouseButton.LEFT.value:
            state["dragging"] = True
            state["x"] = int(ev.get("x", 0))
            state["y"] = int(ev.get("y", 0))
    elif event_type == "mouse_up":
        if int(ev.get("button", MouseButton.LEFT.value)) == MouseButton.LEFT.value:
            state["dragging"] = False
    elif event_type == "mouse_move":
        if state["dragging"]:
            x = int(ev.get("x", 0))
            y = int(ev.get("y", 0))
            camera.orbit(x - state["x"], y - state["y"])
            state["x"] = x
            state["y"] = y
    elif event_type == "mouse_wheel":
        camera.zoom(float(ev.get("dy", 0.0)))


def draw_solids(*solids, title="termin-csg", show_wireframe=True, size=(1000, 760)):
    """Open an interactive preview window and render CSG solids or contours."""
    preview_meshes = _items_to_preview_meshes(solids)
    camera = OrbitCamera()
    lo, hi = _mesh_bounds([m.cpu_mesh for m in preview_meshes])
    camera.fit_bounds(lo, hi)

    window = SDLBackendWindow(title, int(size[0]), int(size[1]))
    graphics = Tgfx2Context.from_window(window.device_ptr(), window.context_ptr())
    ctx = graphics.context
    vs = graphics.device.create_shader(Tgfx2ShaderStage.Vertex, _VERT_SRC)
    fs = graphics.device.create_shader(Tgfx2ShaderStage.Fragment, _FRAG_SRC)

    color_tex = None
    depth_tex = None
    tex_size = (0, 0)
    state = {"dragging": False, "x": 0, "y": 0}

    while not window.should_close():
        for event in wait_sdl_events_timeout(16):
            _dispatch_event(window, camera, state, event)

        w, h = window.framebuffer_size()
        if w <= 0 or h <= 0:
            continue
        if tex_size != (w, h):
            if color_tex is not None:
                graphics.destroy_texture(color_tex)
            if depth_tex is not None:
                graphics.destroy_texture(depth_tex)
            color_tex = graphics.create_color_attachment(w, h, PIXEL_RGBA8)
            depth_tex = graphics.create_depth_attachment(w, h, PIXEL_D32F)
            tex_size = (w, h)

        mvp = camera.view_projection(w, h)
        ctx.begin_frame()
        ctx.begin_pass(color_tex, depth_tex, True, 0.10, 0.10, 0.12, 1.0, 1.0, True)
        ctx.set_viewport(0, 0, w, h)
        ctx.set_depth_test(True)
        ctx.set_depth_write(True)
        ctx.set_blend(False)
        ctx.set_cull(CULL_NONE)
        ctx.bind_shader(vs, fs)
        for mesh in preview_meshes:
            if mesh.draw_solid:
                _push_draw_state(ctx, mvp, mesh.color)
                draw_tc_mesh(ctx, mesh.solid_mesh)
        if show_wireframe:
            ctx.set_depth_test(False)
            ctx.set_depth_write(False)
            for mesh in preview_meshes:
                _push_draw_state(ctx, mvp, mesh.line_color)
                draw_tc_mesh(ctx, mesh.line_mesh)
            ctx.set_depth_test(True)
        ctx.end_pass()
        ctx.end_frame()
        window.present(color_tex)

    if color_tex is not None:
        graphics.destroy_texture(color_tex)
    if depth_tex is not None:
        graphics.destroy_texture(depth_tex)
    graphics.device.destroy_shader(vs)
    graphics.device.destroy_shader(fs)
    window.close()
    quit_sdl()


__all__ = ["draw_solids"]
