"""
SolidPrimitiveRenderer - efficient solid primitive rendering using pre-built unit meshes.

Renders solid primitives (torus, cylinder, cone, arrow) using pre-built GPU meshes
with model matrix transforms. All geometry is created once at initialization.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Tuple
import numpy as np

from termin.visualization.render.shader import ShaderProgram

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import GraphicsBackend


# Simple unlit shader with color
SOLID_VERT = """
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

SOLID_FRAG = """
#version 330 core
in vec4 v_color;
out vec4 fragColor;

void main() {
    fragColor = v_color;
}
"""


def _build_unit_torus(major_segments: int, minor_segments: int, minor_ratio: float) -> Tuple[np.ndarray, np.ndarray]:
    """
    Build unit torus vertices and indices.

    Major radius = 1.0, minor radius = minor_ratio.
    Torus is centered at origin, lying in XY plane (axis = Z).
    """
    vertices = []

    for i in range(major_segments):
        theta = 2.0 * np.pi * i / major_segments
        cos_theta = np.cos(theta)
        sin_theta = np.sin(theta)

        # Center of tube ring
        cx = cos_theta
        cy = sin_theta

        for j in range(minor_segments):
            phi = 2.0 * np.pi * j / minor_segments
            cos_phi = np.cos(phi)
            sin_phi = np.sin(phi)

            # Point on torus surface
            x = cx + minor_ratio * cos_phi * cos_theta
            y = cy + minor_ratio * cos_phi * sin_theta
            z = minor_ratio * sin_phi

            vertices.append([x, y, z])

    vertices = np.array(vertices, dtype=np.float32)

    # Build indices
    indices = []
    for i in range(major_segments):
        i_next = (i + 1) % major_segments
        for j in range(minor_segments):
            j_next = (j + 1) % minor_segments

            v00 = i * minor_segments + j
            v10 = i_next * minor_segments + j
            v01 = i * minor_segments + j_next
            v11 = i_next * minor_segments + j_next

            indices.extend([v00, v10, v11])
            indices.extend([v00, v11, v01])

    indices = np.array(indices, dtype=np.uint32)

    return vertices, indices


def _build_unit_cylinder(segments: int) -> Tuple[np.ndarray, np.ndarray]:
    """
    Build unit cylinder vertices and indices.

    Radius = 1, height = 1 (from Z=0 to Z=1).
    Includes top and bottom caps.
    """
    vertices = []
    indices = []

    # Side vertices: two rings
    for z in [0.0, 1.0]:
        for i in range(segments):
            angle = 2.0 * np.pi * i / segments
            x = np.cos(angle)
            y = np.sin(angle)
            vertices.append([x, y, z])

    # Side indices
    for i in range(segments):
        j = (i + 1) % segments
        # Bottom ring: 0..segments-1
        # Top ring: segments..2*segments-1
        b0, b1 = i, j
        t0, t1 = i + segments, j + segments
        indices.extend([b0, t0, t1])
        indices.extend([b0, t1, b1])

    # Cap centers
    bottom_center = len(vertices)
    vertices.append([0.0, 0.0, 0.0])
    top_center = len(vertices)
    vertices.append([0.0, 0.0, 1.0])

    # Bottom cap indices (facing -Z)
    for i in range(segments):
        j = (i + 1) % segments
        indices.extend([bottom_center, j, i])  # reversed winding

    # Top cap indices (facing +Z)
    for i in range(segments):
        j = (i + 1) % segments
        indices.extend([top_center, i + segments, j + segments])

    return np.array(vertices, dtype=np.float32), np.array(indices, dtype=np.uint32)


def _build_unit_cone(segments: int) -> Tuple[np.ndarray, np.ndarray]:
    """
    Build unit cone vertices and indices.

    Base radius = 1, height = 1 (base at Z=0, tip at Z=1).
    Includes base cap.
    """
    vertices = []
    indices = []

    # Base ring vertices
    for i in range(segments):
        angle = 2.0 * np.pi * i / segments
        x = np.cos(angle)
        y = np.sin(angle)
        vertices.append([x, y, 0.0])

    # Tip vertex
    tip_idx = len(vertices)
    vertices.append([0.0, 0.0, 1.0])

    # Base center
    base_center = len(vertices)
    vertices.append([0.0, 0.0, 0.0])

    # Side triangles
    for i in range(segments):
        j = (i + 1) % segments
        indices.extend([i, tip_idx, j])

    # Base cap (facing -Z)
    for i in range(segments):
        j = (i + 1) % segments
        indices.extend([base_center, j, i])  # reversed winding

    return np.array(vertices, dtype=np.float32), np.array(indices, dtype=np.uint32)


def _build_unit_quad() -> Tuple[np.ndarray, np.ndarray]:
    """
    Build unit quad vertices and indices.

    Quad from (0,0,0) to (1,1,0) in XY plane.
    """
    vertices = np.array([
        [0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0],
        [1.0, 1.0, 0.0],
        [0.0, 1.0, 0.0],
    ], dtype=np.float32)

    indices = np.array([0, 1, 2, 0, 2, 3], dtype=np.uint32)

    return vertices, indices


class SolidPrimitiveRenderer:
    """
    Efficient solid primitive renderer using pre-built GPU meshes.

    All geometry is created once at initialization. Drawing is done by
    setting model matrices and colors per-primitive.
    """

    # Mesh parameters
    TORUS_MAJOR_SEGMENTS = 32
    TORUS_MINOR_SEGMENTS = 8
    TORUS_MINOR_RATIO = 0.03  # minor_radius / major_radius for gizmo rings

    CYLINDER_SEGMENTS = 16
    CONE_SEGMENTS = 16

    def __init__(self):
        self._shader: ShaderProgram | None = None

        # VAO, VBO, EBO for each primitive type
        self._torus_vao: int = 0
        self._torus_vbo: int = 0
        self._torus_ebo: int = 0
        self._torus_index_count: int = 0

        self._cylinder_vao: int = 0
        self._cylinder_vbo: int = 0
        self._cylinder_ebo: int = 0
        self._cylinder_index_count: int = 0

        self._cone_vao: int = 0
        self._cone_vbo: int = 0
        self._cone_ebo: int = 0
        self._cone_index_count: int = 0

        self._quad_vao: int = 0
        self._quad_vbo: int = 0
        self._quad_ebo: int = 0
        self._quad_index_count: int = 0

        self._initialized = False

    def _ensure_initialized(self, graphics: "GraphicsBackend") -> None:
        """Initialize OpenGL resources on first use."""
        if self._initialized:
            return

        from OpenGL import GL as gl

        # Shader
        self._shader = ShaderProgram(SOLID_VERT, SOLID_FRAG)
        self._shader.ensure_ready(graphics, 0)  # TODO: pass context_key properly

        def create_indexed_mesh(vertices: np.ndarray, indices: np.ndarray) -> Tuple[int, int, int, int]:
            vao = gl.glGenVertexArrays(1)
            vbo = gl.glGenBuffers(1)
            ebo = gl.glGenBuffers(1)

            gl.glBindVertexArray(vao)

            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo)
            gl.glBufferData(gl.GL_ARRAY_BUFFER, vertices.nbytes, vertices, gl.GL_STATIC_DRAW)

            gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, ebo)
            gl.glBufferData(gl.GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, gl.GL_STATIC_DRAW)

            gl.glEnableVertexAttribArray(0)
            gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, None)

            gl.glBindVertexArray(0)

            return vao, vbo, ebo, len(indices)

        # Create meshes
        torus_verts, torus_idx = _build_unit_torus(
            self.TORUS_MAJOR_SEGMENTS,
            self.TORUS_MINOR_SEGMENTS,
            self.TORUS_MINOR_RATIO
        )
        self._torus_vao, self._torus_vbo, self._torus_ebo, self._torus_index_count = create_indexed_mesh(torus_verts, torus_idx)

        cyl_verts, cyl_idx = _build_unit_cylinder(self.CYLINDER_SEGMENTS)
        self._cylinder_vao, self._cylinder_vbo, self._cylinder_ebo, self._cylinder_index_count = create_indexed_mesh(cyl_verts, cyl_idx)

        cone_verts, cone_idx = _build_unit_cone(self.CONE_SEGMENTS)
        self._cone_vao, self._cone_vbo, self._cone_ebo, self._cone_index_count = create_indexed_mesh(cone_verts, cone_idx)

        quad_verts, quad_idx = _build_unit_quad()
        self._quad_vao, self._quad_vbo, self._quad_ebo, self._quad_index_count = create_indexed_mesh(quad_verts, quad_idx)

        self._initialized = True

    def begin(
        self,
        graphics: "GraphicsBackend",
        view: np.ndarray,
        proj: np.ndarray,
        depth_test: bool = True,
        blend: bool = False,
    ) -> None:
        """Begin solid primitive rendering. Sets up shader and state."""
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
        else:
            gl.glDisable(gl.GL_BLEND)

        gl.glEnable(gl.GL_CULL_FACE)
        gl.glCullFace(gl.GL_BACK)

        # Bind shader and set view/proj
        self._shader.use()
        self._shader.set_uniform_matrix4("u_view", view)
        self._shader.set_uniform_matrix4("u_projection", proj)

    def end(self) -> None:
        """End solid primitive rendering."""
        pass

    def draw_torus(
        self,
        model: np.ndarray,
        color: Tuple[float, float, float, float],
    ) -> None:
        """
        Draw a torus using model matrix.

        Unit torus has major_radius=1, minor_radius=TORUS_MINOR_RATIO.
        Axis is Z. Model matrix should include position and scale (for major_radius).
        """
        from OpenGL import GL as gl

        self._shader.set_uniform_matrix4("u_model", model)
        self._shader.set_uniform_vec4("u_color", color)

        gl.glBindVertexArray(self._torus_vao)
        gl.glDrawElements(gl.GL_TRIANGLES, self._torus_index_count, gl.GL_UNSIGNED_INT, None)
        gl.glBindVertexArray(0)

    def draw_cylinder(
        self,
        model: np.ndarray,
        color: Tuple[float, float, float, float],
    ) -> None:
        """
        Draw a cylinder using model matrix.

        Unit cylinder has radius=1, height=1 (Z from 0 to 1).
        Model matrix should encode position, rotation, and scale.
        """
        from OpenGL import GL as gl

        self._shader.set_uniform_matrix4("u_model", model)
        self._shader.set_uniform_vec4("u_color", color)

        gl.glBindVertexArray(self._cylinder_vao)
        gl.glDrawElements(gl.GL_TRIANGLES, self._cylinder_index_count, gl.GL_UNSIGNED_INT, None)
        gl.glBindVertexArray(0)

    def draw_cone(
        self,
        model: np.ndarray,
        color: Tuple[float, float, float, float],
    ) -> None:
        """
        Draw a cone using model matrix.

        Unit cone has base_radius=1, height=1 (base at Z=0, tip at Z=1).
        Model matrix should encode position, rotation, and scale.
        """
        from OpenGL import GL as gl

        self._shader.set_uniform_matrix4("u_model", model)
        self._shader.set_uniform_vec4("u_color", color)

        gl.glBindVertexArray(self._cone_vao)
        gl.glDrawElements(gl.GL_TRIANGLES, self._cone_index_count, gl.GL_UNSIGNED_INT, None)
        gl.glBindVertexArray(0)

    def draw_quad(
        self,
        model: np.ndarray,
        color: Tuple[float, float, float, float],
    ) -> None:
        """
        Draw a quad using model matrix.

        Unit quad is from (0,0,0) to (1,1,0) in XY plane.
        Model matrix should encode position, rotation, and scale.
        """
        from OpenGL import GL as gl

        self._shader.set_uniform_matrix4("u_model", model)
        self._shader.set_uniform_vec4("u_color", color)

        gl.glBindVertexArray(self._quad_vao)
        gl.glDrawElements(gl.GL_TRIANGLES, self._quad_index_count, gl.GL_UNSIGNED_INT, None)
        gl.glBindVertexArray(0)

    def draw_arrow(
        self,
        origin: np.ndarray,
        direction: np.ndarray,
        length: float,
        color: Tuple[float, float, float, float],
        shaft_radius: float = 0.02,
        head_radius: float = 0.06,
        head_length_ratio: float = 0.2,
    ) -> None:
        """
        Draw a solid arrow (cylinder shaft + cone head).

        Convenience method that computes model matrices for cylinder and cone.
        """
        direction = np.asarray(direction, dtype=np.float32)
        norm = np.linalg.norm(direction)
        if norm < 1e-6:
            return
        direction = direction / norm

        head_length = length * head_length_ratio
        shaft_length = length - head_length

        # Rotation matrix to align Z with direction
        rot = _rotation_matrix_align_z_to(direction)

        # Shaft: cylinder from origin, length=shaft_length, radius=shaft_radius
        shaft_model = _compose_trs(
            origin,
            rot,
            np.array([shaft_radius, shaft_radius, shaft_length], dtype=np.float32)
        )
        self.draw_cylinder(shaft_model, color)

        # Head: cone from shaft_end to tip
        shaft_end = origin + direction * shaft_length
        head_model = _compose_trs(
            shaft_end,
            rot,
            np.array([head_radius, head_radius, head_length], dtype=np.float32)
        )
        self.draw_cone(head_model, color)


# ============================================================
# Matrix helpers
# ============================================================

def _rotation_matrix_align_z_to(target: np.ndarray) -> np.ndarray:
    """Build 3x3 rotation matrix that rotates Z axis to target direction."""
    target = np.asarray(target, dtype=np.float32)
    length = np.linalg.norm(target)
    if length < 1e-6:
        return np.eye(3, dtype=np.float32)

    z_new = target / length

    up = np.array([0.0, 0.0, 1.0], dtype=np.float32)
    if abs(np.dot(z_new, up)) > 0.99:
        up = np.array([0.0, 1.0, 0.0], dtype=np.float32)

    x_new = np.cross(up, z_new)
    x_new = x_new / np.linalg.norm(x_new)
    y_new = np.cross(z_new, x_new)

    return np.column_stack([x_new, y_new, z_new]).astype(np.float32)


def _compose_trs(translate: np.ndarray, rotate: np.ndarray, scale: np.ndarray) -> np.ndarray:
    """Compose 4x4 TRS matrix from translation, 3x3 rotation, and scale vector."""
    m = np.eye(4, dtype=np.float32)

    # Apply scale to rotation columns
    m[:3, 0] = rotate[:, 0] * scale[0]
    m[:3, 1] = rotate[:, 1] * scale[1]
    m[:3, 2] = rotate[:, 2] * scale[2]

    # Translation
    m[0, 3] = translate[0]
    m[1, 3] = translate[1]
    m[2, 3] = translate[2]

    return m
