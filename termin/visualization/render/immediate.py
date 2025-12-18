"""
ImmediateRenderer - immediate mode rendering for debug visualization, gizmos, etc.

Accumulates primitives (lines, triangles) during the frame and batches them
into a single draw call at flush time.

Usage:
    renderer = ImmediateRenderer()

    # During frame:
    renderer.begin()
    renderer.line(start, end, color)
    renderer.arrow(origin, direction, length, color)
    renderer.circle(center, normal, radius, color)

    # At end of frame:
    renderer.flush(graphics, view_matrix, proj_matrix)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
import numpy as np

from termin.visualization.render.shader import ShaderProgram

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import GraphicsBackend


# Simple shader for colored lines/triangles
IMMEDIATE_VERT = """
#version 330 core
layout(location = 0) in vec3 a_position;
layout(location = 1) in vec4 a_color;

uniform mat4 u_view;
uniform mat4 u_projection;

out vec4 v_color;

void main() {
    v_color = a_color;
    gl_Position = u_projection * u_view * vec4(a_position, 1.0);
}
"""

IMMEDIATE_FRAG = """
#version 330 core
in vec4 v_color;
out vec4 fragColor;

void main() {
    fragColor = v_color;
}
"""


class ImmediateRenderer:
    """
    Immediate mode renderer for lines and triangles.

    All primitives are accumulated in CPU buffers and rendered
    in a single batch when flush() is called.
    """

    def __init__(self):
        # Line vertices: [(x, y, z, r, g, b, a), ...]
        self._line_vertices: list[tuple[float, ...]] = []

        # Triangle vertices: [(x, y, z, r, g, b, a), ...]
        self._tri_vertices: list[tuple[float, ...]] = []

        # OpenGL resources (lazy init)
        self._shader: ShaderProgram | None = None
        self._line_vao: int | None = None
        self._line_vbo: int | None = None
        self._tri_vao: int | None = None
        self._tri_vbo: int | None = None
        self._initialized = False

    def begin(self) -> None:
        """Clear all accumulated primitives. Call at start of frame."""
        self._line_vertices.clear()
        self._tri_vertices.clear()

    # ============================================================
    # Primitive accumulation
    # ============================================================

    def line(
        self,
        start: np.ndarray | tuple,
        end: np.ndarray | tuple,
        color: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
    ) -> None:
        """Add a line segment."""
        s = tuple(start)
        e = tuple(end)
        self._line_vertices.append((*s, *color))
        self._line_vertices.append((*e, *color))

    def triangle(
        self,
        p0: np.ndarray | tuple,
        p1: np.ndarray | tuple,
        p2: np.ndarray | tuple,
        color: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
    ) -> None:
        """Add a filled triangle."""
        self._tri_vertices.append((*tuple(p0), *color))
        self._tri_vertices.append((*tuple(p1), *color))
        self._tri_vertices.append((*tuple(p2), *color))

    def quad(
        self,
        p0: np.ndarray | tuple,
        p1: np.ndarray | tuple,
        p2: np.ndarray | tuple,
        p3: np.ndarray | tuple,
        color: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
    ) -> None:
        """Add a filled quad (two triangles)."""
        self.triangle(p0, p1, p2, color)
        self.triangle(p0, p2, p3, color)

    def polyline(
        self,
        points: list[np.ndarray | tuple],
        color: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
        closed: bool = False,
    ) -> None:
        """Add connected line segments."""
        if len(points) < 2:
            return
        for i in range(len(points) - 1):
            self.line(points[i], points[i + 1], color)
        if closed and len(points) > 2:
            self.line(points[-1], points[0], color)

    def circle(
        self,
        center: np.ndarray | tuple,
        normal: np.ndarray | tuple,
        radius: float,
        color: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
        segments: int = 32,
    ) -> None:
        """Add a circle (as line loop)."""
        center = np.asarray(center, dtype=np.float32)
        normal = np.asarray(normal, dtype=np.float32)
        normal = normal / np.linalg.norm(normal)

        # Build orthonormal basis
        up = np.array([0.0, 0.0, 1.0], dtype=np.float32)
        if abs(np.dot(normal, up)) > 0.99:
            up = np.array([0.0, 1.0, 0.0], dtype=np.float32)

        tangent = np.cross(normal, up)
        tangent = tangent / np.linalg.norm(tangent)
        bitangent = np.cross(normal, tangent)

        points = []
        for i in range(segments):
            angle = 2.0 * np.pi * i / segments
            point = center + radius * (np.cos(angle) * tangent + np.sin(angle) * bitangent)
            points.append(point)

        self.polyline(points, color, closed=True)

    def arrow(
        self,
        origin: np.ndarray | tuple,
        direction: np.ndarray | tuple,
        length: float,
        color: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
        head_length: float = 0.2,
        head_width: float = 0.1,
    ) -> None:
        """Add an arrow (line + cone head as lines)."""
        origin = np.asarray(origin, dtype=np.float32)
        direction = np.asarray(direction, dtype=np.float32)
        direction = direction / np.linalg.norm(direction)

        tip = origin + direction * length
        head_base = tip - direction * (length * head_length)

        # Shaft
        self.line(origin, head_base, color)

        # Head (simple 4 lines)
        up = np.array([0.0, 0.0, 1.0], dtype=np.float32)
        if abs(np.dot(direction, up)) > 0.99:
            up = np.array([0.0, 1.0, 0.0], dtype=np.float32)

        right = np.cross(direction, up)
        right = right / np.linalg.norm(right)
        up = np.cross(right, direction)

        hw = length * head_width
        p1 = head_base + right * hw
        p2 = head_base - right * hw
        p3 = head_base + up * hw
        p4 = head_base - up * hw

        self.line(tip, p1, color)
        self.line(tip, p2, color)
        self.line(tip, p3, color)
        self.line(tip, p4, color)

    def box(
        self,
        min_pt: np.ndarray | tuple,
        max_pt: np.ndarray | tuple,
        color: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
    ) -> None:
        """Add a wireframe box."""
        mn = np.asarray(min_pt)
        mx = np.asarray(max_pt)

        # 8 corners
        corners = [
            (mn[0], mn[1], mn[2]),
            (mx[0], mn[1], mn[2]),
            (mx[0], mx[1], mn[2]),
            (mn[0], mx[1], mn[2]),
            (mn[0], mn[1], mx[2]),
            (mx[0], mn[1], mx[2]),
            (mx[0], mx[1], mx[2]),
            (mn[0], mx[1], mx[2]),
        ]

        # 12 edges
        edges = [
            (0, 1), (1, 2), (2, 3), (3, 0),  # bottom
            (4, 5), (5, 6), (6, 7), (7, 4),  # top
            (0, 4), (1, 5), (2, 6), (3, 7),  # vertical
        ]

        for i, j in edges:
            self.line(corners[i], corners[j], color)

    def cylinder_wireframe(
        self,
        start: np.ndarray | tuple,
        end: np.ndarray | tuple,
        radius: float,
        color: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
        segments: int = 16,
    ) -> None:
        """Add a wireframe cylinder."""
        start = np.asarray(start, dtype=np.float32)
        end = np.asarray(end, dtype=np.float32)

        axis = end - start
        length = np.linalg.norm(axis)
        if length < 1e-6:
            return
        axis = axis / length

        # Circles at ends
        self.circle(start, axis, radius, color, segments)
        self.circle(end, axis, radius, color, segments)

        # Connecting lines
        up = np.array([0.0, 0.0, 1.0], dtype=np.float32)
        if abs(np.dot(axis, up)) > 0.99:
            up = np.array([0.0, 1.0, 0.0], dtype=np.float32)

        tangent = np.cross(axis, up)
        tangent = tangent / np.linalg.norm(tangent)
        bitangent = np.cross(axis, tangent)

        for i in range(4):
            angle = 2.0 * np.pi * i / 4
            offset = radius * (np.cos(angle) * tangent + np.sin(angle) * bitangent)
            self.line(start + offset, end + offset, color)

    # ============================================================
    # Solid primitives (for gizmos, etc.)
    # ============================================================

    def _build_basis(self, axis: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Build orthonormal basis from axis direction."""
        up = np.array([0.0, 0.0, 1.0], dtype=np.float32)
        if abs(np.dot(axis, up)) > 0.99:
            up = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        tangent = np.cross(axis, up)
        tangent = tangent / np.linalg.norm(tangent)
        bitangent = np.cross(axis, tangent)
        return tangent, bitangent

    def cylinder_solid(
        self,
        start: np.ndarray | tuple,
        end: np.ndarray | tuple,
        radius: float,
        color: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
        segments: int = 16,
        caps: bool = True,
    ) -> None:
        """Add a solid cylinder."""
        start = np.asarray(start, dtype=np.float32)
        end = np.asarray(end, dtype=np.float32)

        axis = end - start
        length = np.linalg.norm(axis)
        if length < 1e-6:
            return
        axis = axis / length

        tangent, bitangent = self._build_basis(axis)

        # Generate ring points
        ring_start = []
        ring_end = []
        for i in range(segments):
            angle = 2.0 * np.pi * i / segments
            offset = radius * (np.cos(angle) * tangent + np.sin(angle) * bitangent)
            ring_start.append(start + offset)
            ring_end.append(end + offset)

        # Side triangles
        for i in range(segments):
            j = (i + 1) % segments
            self.triangle(ring_start[i], ring_end[i], ring_end[j], color)
            self.triangle(ring_start[i], ring_end[j], ring_start[j], color)

        # Caps
        if caps:
            for i in range(segments):
                j = (i + 1) % segments
                self.triangle(start, ring_start[j], ring_start[i], color)
                self.triangle(end, ring_end[i], ring_end[j], color)

    def cone_solid(
        self,
        base: np.ndarray | tuple,
        tip: np.ndarray | tuple,
        radius: float,
        color: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
        segments: int = 16,
        cap: bool = True,
    ) -> None:
        """Add a solid cone."""
        base = np.asarray(base, dtype=np.float32)
        tip = np.asarray(tip, dtype=np.float32)

        axis = tip - base
        length = np.linalg.norm(axis)
        if length < 1e-6:
            return
        axis = axis / length

        tangent, bitangent = self._build_basis(axis)

        # Generate base ring points
        ring = []
        for i in range(segments):
            angle = 2.0 * np.pi * i / segments
            offset = radius * (np.cos(angle) * tangent + np.sin(angle) * bitangent)
            ring.append(base + offset)

        # Side triangles
        for i in range(segments):
            j = (i + 1) % segments
            self.triangle(ring[i], tip, ring[j], color)

        # Base cap
        if cap:
            for i in range(segments):
                j = (i + 1) % segments
                self.triangle(base, ring[j], ring[i], color)

    def torus_solid(
        self,
        center: np.ndarray | tuple,
        axis: np.ndarray | tuple,
        major_radius: float,
        minor_radius: float,
        color: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
        major_segments: int = 32,
        minor_segments: int = 12,
    ) -> None:
        """Add a solid torus."""
        center = np.asarray(center, dtype=np.float32)
        axis = np.asarray(axis, dtype=np.float32)
        axis = axis / np.linalg.norm(axis)

        tangent, bitangent = self._build_basis(axis)

        # Generate torus vertices
        vertices = []
        for i in range(major_segments):
            theta = 2.0 * np.pi * i / major_segments
            # Center of tube ring
            ring_center = center + major_radius * (np.cos(theta) * tangent + np.sin(theta) * bitangent)
            # Radial direction for this ring
            radial = np.cos(theta) * tangent + np.sin(theta) * bitangent

            ring = []
            for j in range(minor_segments):
                phi = 2.0 * np.pi * j / minor_segments
                point = ring_center + minor_radius * (np.cos(phi) * radial + np.sin(phi) * axis)
                ring.append(point)
            vertices.append(ring)

        # Generate triangles
        for i in range(major_segments):
            i_next = (i + 1) % major_segments
            for j in range(minor_segments):
                j_next = (j + 1) % minor_segments
                p00 = vertices[i][j]
                p10 = vertices[i_next][j]
                p01 = vertices[i][j_next]
                p11 = vertices[i_next][j_next]
                self.triangle(p00, p10, p11, color)
                self.triangle(p00, p11, p01, color)

    def arrow_solid(
        self,
        origin: np.ndarray | tuple,
        direction: np.ndarray | tuple,
        length: float,
        color: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
        shaft_radius: float = 0.03,
        head_radius: float = 0.06,
        head_length_ratio: float = 0.25,
        segments: int = 16,
    ) -> None:
        """Add a solid arrow (cylinder shaft + cone head)."""
        origin = np.asarray(origin, dtype=np.float32)
        direction = np.asarray(direction, dtype=np.float32)
        norm = np.linalg.norm(direction)
        if norm < 1e-6:
            return
        direction = direction / norm

        head_length = length * head_length_ratio
        shaft_length = length - head_length

        shaft_end = origin + direction * shaft_length
        tip = origin + direction * length

        # Shaft cylinder
        self.cylinder_solid(origin, shaft_end, shaft_radius, color, segments, caps=True)
        # Head cone
        self.cone_solid(shaft_end, tip, head_radius, color, segments, cap=True)

    # ============================================================
    # Rendering
    # ============================================================

    def _ensure_initialized(self, graphics: "GraphicsBackend") -> None:
        """Initialize OpenGL resources."""
        if self._initialized:
            return

        from OpenGL import GL as gl

        # Shader
        self._shader = ShaderProgram(IMMEDIATE_VERT, IMMEDIATE_FRAG)
        self._shader.ensure_ready(graphics)

        # Line VAO/VBO
        self._line_vao = gl.glGenVertexArrays(1)
        self._line_vbo = gl.glGenBuffers(1)

        gl.glBindVertexArray(self._line_vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self._line_vbo)

        stride = 7 * 4  # 3 pos + 4 color, float32
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, stride, gl.ctypes.c_void_p(0))
        gl.glEnableVertexAttribArray(1)
        gl.glVertexAttribPointer(1, 4, gl.GL_FLOAT, gl.GL_FALSE, stride, gl.ctypes.c_void_p(12))

        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
        gl.glBindVertexArray(0)

        # Triangle VAO/VBO
        self._tri_vao = gl.glGenVertexArrays(1)
        self._tri_vbo = gl.glGenBuffers(1)

        gl.glBindVertexArray(self._tri_vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self._tri_vbo)

        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, stride, gl.ctypes.c_void_p(0))
        gl.glEnableVertexAttribArray(1)
        gl.glVertexAttribPointer(1, 4, gl.GL_FLOAT, gl.GL_FALSE, stride, gl.ctypes.c_void_p(12))

        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
        gl.glBindVertexArray(0)

        self._initialized = True

    def flush(
        self,
        graphics: "GraphicsBackend",
        view_matrix: np.ndarray,
        proj_matrix: np.ndarray,
        depth_test: bool = True,
        blend: bool = True,
    ) -> None:
        """
        Render all accumulated primitives.

        Args:
            graphics: Graphics backend
            view_matrix: Camera view matrix
            proj_matrix: Camera projection matrix
            depth_test: Enable depth testing
            blend: Enable alpha blending
        """
        if not self._line_vertices and not self._tri_vertices:
            return

        from OpenGL import GL as gl

        self._ensure_initialized(graphics)

        # Setup state
        if depth_test:
            gl.glEnable(gl.GL_DEPTH_TEST)
        else:
            gl.glDisable(gl.GL_DEPTH_TEST)

        if blend:
            gl.glEnable(gl.GL_BLEND)
            gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)

        gl.glDisable(gl.GL_CULL_FACE)

        # Use shader
        self._shader.use()
        self._shader.set_uniform_matrix4("u_view", view_matrix)
        self._shader.set_uniform_matrix4("u_projection", proj_matrix)

        # Draw lines
        if self._line_vertices:
            data = np.array(self._line_vertices, dtype=np.float32).flatten()

            gl.glBindVertexArray(self._line_vao)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self._line_vbo)
            gl.glBufferData(gl.GL_ARRAY_BUFFER, data.nbytes, data, gl.GL_DYNAMIC_DRAW)

            gl.glDrawArrays(gl.GL_LINES, 0, len(self._line_vertices))

            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
            gl.glBindVertexArray(0)

        # Draw triangles
        if self._tri_vertices:
            data = np.array(self._tri_vertices, dtype=np.float32).flatten()

            gl.glBindVertexArray(self._tri_vao)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self._tri_vbo)
            gl.glBufferData(gl.GL_ARRAY_BUFFER, data.nbytes, data, gl.GL_DYNAMIC_DRAW)

            gl.glDrawArrays(gl.GL_TRIANGLES, 0, len(self._tri_vertices))

            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
            gl.glBindVertexArray(0)

        # Restore state
        gl.glEnable(gl.GL_CULL_FACE)
        if not blend:
            gl.glDisable(gl.GL_BLEND)

    @property
    def line_count(self) -> int:
        """Number of lines accumulated."""
        return len(self._line_vertices) // 2

    @property
    def triangle_count(self) -> int:
        """Number of triangles accumulated."""
        return len(self._tri_vertices) // 3
