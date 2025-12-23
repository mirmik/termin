"""Base mesh classes and vertex layout definitions."""

import numpy as np
from enum import Enum

from termin.mesh._mesh_native import Mesh3

# GPU COMPATIBILITY

class VertexAttribType(Enum):
    FLOAT32 = "float32"
    INT32 = "int32"
    UINT32 = "uint32"

class VertexAttribute:
    def __init__(self, name, size, vtype: VertexAttribType, offset):
        self.name = name
        self.size = size
        self.vtype = vtype
        self.offset = offset


class VertexLayout:
    def __init__(self, stride, attributes):
        self.stride = stride    # размер одной вершины в байтах
        self.attributes = attributes  # список VertexAttribute


class Mesh:
    def __init__(self, vertices: np.ndarray, indices: np.ndarray):
        self.vertices = np.asarray(vertices, dtype=np.float32)
        self.indices  = np.asarray(indices,  dtype=np.uint32)
        self.type = "triangles" if indices.shape[1] == 3 else "lines"
        self._inter = None

    def get_vertex_layout(self) -> VertexLayout:
        raise NotImplementedError("get_vertex_layout must be implemented in subclasses.")


class Mesh2(Mesh):
    """Simple triangle mesh storing vertex positions and triangle indices."""

    @staticmethod
    def from_lists(vertices: list[tuple[float, float]], indices: list[tuple[int, int]]) -> "Mesh2":
        verts = np.asarray(vertices, dtype=float)
        idx = np.asarray(indices, dtype=int)
        return Mesh2(verts, idx)

    def __init__(self, vertices: np.ndarray, indices: np.ndarray):
        super().__init__(vertices, indices)
        self._validate_mesh()

    def copy(self) -> "Mesh2":
        return Mesh2(self.vertices.copy(), self.indices.copy())

    def _validate_mesh(self):
        """Ensure that the vertex/index arrays have correct shapes and bounds."""
        if self.vertices.ndim != 2 or self.vertices.shape[1] != 3:
            raise ValueError("Vertices must be a Nx3 array.")
        if self.indices.ndim != 2 or self.indices.shape[1] != 2:
            raise ValueError("Indices must be a Mx2 array.")

    def interleaved_buffer(self):
        return self.vertices.astype(np.float32)

    def get_vertex_layout(self):
        return VertexLayout(
            stride=3*4,
            attributes=[
                VertexAttribute("position", 3, VertexAttribType.FLOAT32, 0)
            ]
        )


# Add Python methods to native Mesh3

def _mesh3_get_vertex_layout(self) -> VertexLayout:
    """Get vertex layout for Mesh3: pos(3) + normal(3) + uv(2)."""
    return VertexLayout(
        stride=8 * 4,
        attributes=[
            VertexAttribute("position", 3, VertexAttribType.FLOAT32, 0),
            VertexAttribute("normal",   3, VertexAttribType.FLOAT32, 12),
            VertexAttribute("uv",       2, VertexAttribType.FLOAT32, 24),
        ]
    )

Mesh3.get_vertex_layout = _mesh3_get_vertex_layout


# Helper functions for Mesh3

def mesh3_vertex_layout() -> VertexLayout:
    """Get vertex layout for Mesh3: pos(3) + normal(3) + uv(2)."""
    return VertexLayout(
        stride=8 * 4,
        attributes=[
            VertexAttribute("position", 3, VertexAttribType.FLOAT32, 0),
            VertexAttribute("normal",   3, VertexAttribType.FLOAT32, 12),
            VertexAttribute("uv",       2, VertexAttribType.FLOAT32, 24),
        ]
    )


def mesh3_from_assimp(assimp_mesh) -> Mesh3:
    """Create Mesh3 from assimp mesh."""
    verts = np.asarray(assimp_mesh.vertices, dtype=np.float32)
    idx = np.asarray(assimp_mesh.indices, dtype=np.uint32).reshape(-1, 3)
    uvs = np.asarray(assimp_mesh.uvs, dtype=np.float32) if assimp_mesh.uvs is not None else None

    mesh = Mesh3(verts, idx, uvs)

    if assimp_mesh.normals is not None:
        mesh.vertex_normals = np.asarray(assimp_mesh.normals, dtype=np.float32)
    else:
        mesh.compute_vertex_normals()

    return mesh


def mesh3_from_convex_hull(hull) -> Mesh3:
    """Create Mesh3 from scipy.spatial.ConvexHull."""
    vertices = hull.points.astype(np.float32)
    triangles = hull.simplices.astype(np.uint32)

    center = np.mean(vertices, axis=0)

    for i in range(triangles.shape[0]):
        v0 = vertices[triangles[i, 0]]
        v1 = vertices[triangles[i, 1]]
        v2 = vertices[triangles[i, 2]]
        normal = np.cross(v1 - v0, v2 - v0)
        to_center = center - v0
        if np.dot(normal, to_center) > 0:
            triangles[i, [1, 2]] = triangles[i, [2, 1]]

    return Mesh3(vertices, triangles)


def show_mesh(mesh: Mesh3):
    """Show the mesh in a simple viewer application."""
    from .mesh_viewer_miniapp import show_mesh_app
    show_mesh_app(mesh)


# Re-export primitives for backward compatibility
from .primitives import (
    CubeMesh,
    TexturedCubeMesh,
    UVSphereMesh,
    IcoSphereMesh,
    PlaneMesh,
    CylinderMesh,
    ConeMesh,
    TorusMesh,
    RingMesh,
)
