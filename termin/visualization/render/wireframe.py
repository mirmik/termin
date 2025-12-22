"""
WireframeRenderer - efficient wireframe rendering using instanced unit meshes.

Instead of generating vertices every frame, uses pre-built unit meshes
(circle, box, arc) and transforms them via model matrices.

Supports instanced rendering for batching multiple primitives in one draw call.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Tuple
import numpy as np

from termin.visualization.render.shader import ShaderProgram

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import GraphicsBackend


# Shader with model matrix support
WIREFRAME_VERT = """
#version 330 core
layout(location = 0) in vec3 a_position;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;
uniform vec4 u_color;

out vec4 v_color;

void main() {
    v_color = u_color;
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
}
"""

WIREFRAME_FRAG = """
#version 330 core
in vec4 v_color;
out vec4 fragColor;

void main() {
    fragColor = v_color;
}
"""


def _build_unit_circle(segments: int) -> np.ndarray:
    """Build unit circle vertices in XY plane, radius=1, centered at origin."""
    angles = np.linspace(0, 2 * np.pi, segments, endpoint=False)
    vertices = np.zeros((segments, 3), dtype=np.float32)
    vertices[:, 0] = np.cos(angles)
    vertices[:, 1] = np.sin(angles)
    return vertices


def _build_unit_arc(segments: int) -> np.ndarray:
    """Build unit half-circle (arc) vertices in XY plane, from +X to -X via +Y."""
    angles = np.linspace(0, np.pi, segments + 1, endpoint=True)
    vertices = np.zeros((segments + 1, 3), dtype=np.float32)
    vertices[:, 0] = np.cos(angles)
    vertices[:, 1] = np.sin(angles)
    return vertices


def _build_unit_box() -> np.ndarray:
    """Build unit box edges, from -0.5 to +0.5 on each axis. Returns line pairs."""
    # 8 corners
    corners = np.array([
        [-0.5, -0.5, -0.5],
        [+0.5, -0.5, -0.5],
        [+0.5, +0.5, -0.5],
        [-0.5, +0.5, -0.5],
        [-0.5, -0.5, +0.5],
        [+0.5, -0.5, +0.5],
        [+0.5, +0.5, +0.5],
        [-0.5, +0.5, +0.5],
    ], dtype=np.float32)

    # 12 edges as pairs of vertices
    edges = [
        (0, 1), (1, 2), (2, 3), (3, 0),  # bottom
        (4, 5), (5, 6), (6, 7), (7, 4),  # top
        (0, 4), (1, 5), (2, 6), (3, 7),  # vertical
    ]

    vertices = np.zeros((24, 3), dtype=np.float32)
    for i, (a, b) in enumerate(edges):
        vertices[i * 2] = corners[a]
        vertices[i * 2 + 1] = corners[b]

    return vertices


def _build_unit_line() -> np.ndarray:
    """Build unit line from origin to +Z."""
    return np.array([
        [0.0, 0.0, 0.0],
        [0.0, 0.0, 1.0],
    ], dtype=np.float32)


class WireframeRenderer:
    """
    Efficient wireframe renderer using pre-built unit meshes.

    All geometry is created once at initialization. Drawing is done by
    setting model matrices and colors per-primitive.
    """

    CIRCLE_SEGMENTS = 16
    ARC_SEGMENTS = 8

    def __init__(self):
        self._shader: ShaderProgram | None = None

        # VAOs and VBOs for unit meshes
        self._circle_vao: int = 0
        self._circle_vbo: int = 0
        self._circle_vertex_count: int = 0

        self._arc_vao: int = 0
        self._arc_vbo: int = 0
        self._arc_vertex_count: int = 0

        self._box_vao: int = 0
        self._box_vbo: int = 0
        self._box_vertex_count: int = 0

        self._line_vao: int = 0
        self._line_vbo: int = 0

        self._initialized = False

        # Cached matrices
        self._view: np.ndarray | None = None
        self._proj: np.ndarray | None = None

    def _ensure_initialized(self, graphics: "GraphicsBackend") -> None:
        """Initialize OpenGL resources on first use."""
        if self._initialized:
            return

        from OpenGL import GL as gl

        # Shader
        self._shader = ShaderProgram(WIREFRAME_VERT, WIREFRAME_FRAG)
        self._shader.ensure_ready(graphics)

        # Helper to create VAO/VBO for vertex data
        def create_mesh(vertices: np.ndarray) -> Tuple[int, int, int]:
            vao = gl.glGenVertexArrays(1)
            vbo = gl.glGenBuffers(1)

            gl.glBindVertexArray(vao)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo)
            gl.glBufferData(gl.GL_ARRAY_BUFFER, vertices.nbytes, vertices, gl.GL_STATIC_DRAW)

            gl.glEnableVertexAttribArray(0)
            gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, None)

            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
            gl.glBindVertexArray(0)

            return vao, vbo, len(vertices)

        # Create unit meshes
        circle_verts = _build_unit_circle(self.CIRCLE_SEGMENTS)
        self._circle_vao, self._circle_vbo, self._circle_vertex_count = create_mesh(circle_verts)

        arc_verts = _build_unit_arc(self.ARC_SEGMENTS)
        self._arc_vao, self._arc_vbo, self._arc_vertex_count = create_mesh(arc_verts)

        box_verts = _build_unit_box()
        self._box_vao, self._box_vbo, self._box_vertex_count = create_mesh(box_verts)

        line_verts = _build_unit_line()
        self._line_vao, self._line_vbo, _ = create_mesh(line_verts)

        self._initialized = True

    def begin(
        self,
        graphics: "GraphicsBackend",
        view: np.ndarray,
        proj: np.ndarray,
        depth_test: bool = False,
    ) -> None:
        """Begin wireframe rendering. Sets up shader and state."""
        from OpenGL import GL as gl

        self._ensure_initialized(graphics)

        self._view = view
        self._proj = proj

        # Setup state
        if depth_test:
            gl.glEnable(gl.GL_DEPTH_TEST)
        else:
            gl.glDisable(gl.GL_DEPTH_TEST)

        gl.glDisable(gl.GL_CULL_FACE)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)

        # Bind shader and set view/proj (constant for frame)
        self._shader.use()
        self._shader.set_uniform_matrix4("u_view", view)
        self._shader.set_uniform_matrix4("u_projection", proj)

    def end(self) -> None:
        """End wireframe rendering. Restores state."""
        from OpenGL import GL as gl
        gl.glEnable(gl.GL_CULL_FACE)
        self._view = None
        self._proj = None

    def draw_circle(
        self,
        model: np.ndarray,
        color: Tuple[float, float, float, float],
    ) -> None:
        """
        Draw a circle using model matrix.

        Unit circle is in XY plane with radius=1.
        Model matrix should encode position, rotation, and scale (radius).
        """
        from OpenGL import GL as gl

        self._shader.set_uniform_matrix4("u_model", model)
        self._shader.set_uniform_vec4("u_color", color)

        gl.glBindVertexArray(self._circle_vao)
        gl.glDrawArrays(gl.GL_LINE_LOOP, 0, self._circle_vertex_count)
        gl.glBindVertexArray(0)

    def draw_arc(
        self,
        model: np.ndarray,
        color: Tuple[float, float, float, float],
    ) -> None:
        """
        Draw a half-circle arc using model matrix.

        Unit arc is in XY plane from +X to -X via +Y, radius=1.
        """
        from OpenGL import GL as gl

        self._shader.set_uniform_matrix4("u_model", model)
        self._shader.set_uniform_vec4("u_color", color)

        gl.glBindVertexArray(self._arc_vao)
        gl.glDrawArrays(gl.GL_LINE_STRIP, 0, self._arc_vertex_count)
        gl.glBindVertexArray(0)

    def draw_box(
        self,
        model: np.ndarray,
        color: Tuple[float, float, float, float],
    ) -> None:
        """
        Draw a wireframe box using model matrix.

        Unit box is from -0.5 to +0.5 on each axis.
        Model matrix should encode position, rotation, and scale (size).
        """
        from OpenGL import GL as gl

        self._shader.set_uniform_matrix4("u_model", model)
        self._shader.set_uniform_vec4("u_color", color)

        gl.glBindVertexArray(self._box_vao)
        gl.glDrawArrays(gl.GL_LINES, 0, self._box_vertex_count)
        gl.glBindVertexArray(0)

    def draw_line(
        self,
        model: np.ndarray,
        color: Tuple[float, float, float, float],
    ) -> None:
        """
        Draw a line using model matrix.

        Unit line is from origin to (0, 0, 1).
        Model matrix should encode start position, rotation, and scale (length).
        """
        from OpenGL import GL as gl

        self._shader.set_uniform_matrix4("u_model", model)
        self._shader.set_uniform_vec4("u_color", color)

        gl.glBindVertexArray(self._line_vao)
        gl.glDrawArrays(gl.GL_LINES, 0, 2)
        gl.glBindVertexArray(0)


# ============================================================
# Matrix helpers for building model matrices
# ============================================================

def mat4_identity() -> np.ndarray:
    """Create identity 4x4 matrix."""
    return np.eye(4, dtype=np.float32)


def mat4_translate(x: float, y: float, z: float) -> np.ndarray:
    """Create translation matrix."""
    m = np.eye(4, dtype=np.float32)
    m[0, 3] = x
    m[1, 3] = y
    m[2, 3] = z
    return m


def mat4_scale(sx: float, sy: float, sz: float) -> np.ndarray:
    """Create scale matrix."""
    m = np.eye(4, dtype=np.float32)
    m[0, 0] = sx
    m[1, 1] = sy
    m[2, 2] = sz
    return m


def mat4_scale_uniform(s: float) -> np.ndarray:
    """Create uniform scale matrix."""
    return mat4_scale(s, s, s)


def mat4_from_rotation_matrix(rot3x3: np.ndarray) -> np.ndarray:
    """Create 4x4 matrix from 3x3 rotation matrix."""
    m = np.eye(4, dtype=np.float32)
    m[:3, :3] = rot3x3
    return m


def mat4_compose(translate: np.ndarray, rotate: np.ndarray, scale: np.ndarray) -> np.ndarray:
    """Compose TRS matrix: T * R * S."""
    return translate @ rotate @ scale


def rotation_matrix_from_axis_z_to(target: np.ndarray) -> np.ndarray:
    """
    Build rotation matrix that rotates Z axis to target direction.
    Returns 3x3 rotation matrix.
    """
    target = np.asarray(target, dtype=np.float32)
    length = np.linalg.norm(target)
    if length < 1e-6:
        return np.eye(3, dtype=np.float32)

    z_new = target / length

    # Choose up vector that's not parallel to target
    up = np.array([0.0, 0.0, 1.0], dtype=np.float32)
    if abs(np.dot(z_new, up)) > 0.99:
        up = np.array([0.0, 1.0, 0.0], dtype=np.float32)

    x_new = np.cross(up, z_new)
    x_new = x_new / np.linalg.norm(x_new)
    y_new = np.cross(z_new, x_new)

    # Rotation matrix: columns are new basis vectors
    rot = np.column_stack([x_new, y_new, z_new])
    return rot.astype(np.float32)


def rotation_matrix_align_z_to_axis(axis: np.ndarray) -> np.ndarray:
    """
    Build rotation matrix that aligns Z axis to given axis.
    Similar to rotation_matrix_from_axis_z_to but with consistent naming.
    """
    return rotation_matrix_from_axis_z_to(axis)
