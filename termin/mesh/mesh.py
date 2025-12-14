"""Base mesh classes and vertex layout definitions."""

import numpy as np
from enum import Enum

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


class Mesh3(Mesh):
    """Simple triangle mesh storing vertex positions and triangle indices."""

    def __init__(self, vertices: np.ndarray, triangles: np.ndarray, uvs: np.ndarray | None = None):
        super().__init__(vertices, triangles)

        self.uvs = np.asarray(uvs, dtype=float) if uvs is not None else None
        self._validate_mesh()
        self.vertex_normals = None
        self.face_normals = None

    def copy(self) -> "Mesh3":
        uvs_copy = self.uvs.copy() if self.uvs is not None else None
        mesh_copy = Mesh3(self.vertices.copy(), self.triangles.copy(), uvs_copy)
        if self.vertex_normals is not None:
            mesh_copy.vertex_normals = self.vertex_normals.copy()
        if self.face_normals is not None:
            mesh_copy.face_normals = self.face_normals.copy()
        return mesh_copy

    def build_interleaved_buffer(self):
        # позиции — всегда есть
        pos = self.vertices.astype(np.float32)

        # нормали — если нет, генерим нули
        if self.vertex_normals is None:
            normals = np.zeros_like(self.vertices, dtype=np.float32)
        else:
            normals = self.vertex_normals.astype(np.float32)

        # uv — если нет, ставим (0,0)
        if self.uvs is None:
            uvs = np.zeros((self.vertices.shape[0], 2), dtype=np.float32)
        else:
            uvs = self.uvs.astype(np.float32)

        return np.hstack([pos, normals, uvs])

    def interleaved_buffer(self):
        if self._inter is None:
            self._inter = self.build_interleaved_buffer()
        return self._inter

    @property
    def triangles(self):
        return self.indices
    
    @triangles.setter
    def triangles(self, value):
        self.indices = value

    def get_vertex_layout(self) -> VertexLayout:
        return VertexLayout(
            stride=8 * 4,  # всегда: pos(3) + normal(3) + uv(2)
            attributes=[
                VertexAttribute("position", 3, VertexAttribType.FLOAT32, 0),
                VertexAttribute("normal",   3, VertexAttribType.FLOAT32, 12),
                VertexAttribute("uv",       2, VertexAttribType.FLOAT32, 24),
            ]
        )

    def _validate_mesh(self):
        """Ensure that the vertex/index arrays have correct shapes and bounds."""
        if self.vertices.ndim != 2 or self.vertices.shape[1] != 3:
            raise ValueError("Vertices must be a Nx3 array.")
        if self.triangles.ndim != 2 or self.triangles.shape[1] != 3:
            raise ValueError("Triangles must be a Mx3 array.")
        if np.any(self.triangles < 0) or np.any(self.triangles >= self.vertices.shape[0]):
            raise ValueError("Triangle indices must be valid vertex indices.")

    def translate(self, offset: np.ndarray):
        """Apply translation by vector ``offset`` to all vertices."""
        offset = np.asarray(offset, dtype=float)
        if offset.shape != (3,):
            raise ValueError("Offset must be a 3-dimensional vector.")
        self.vertices += offset

    def show(self):
        """Show the mesh in a simple viewer application."""
        from .mesh_viewer_miniapp import show_mesh_app
        show_mesh_app(self)

    @staticmethod
    def from_assimp_mesh(assimp_mesh) -> "Mesh":
            verts = np.asarray(assimp_mesh.vertices, dtype=float)
            idx = np.asarray(assimp_mesh.indices, dtype=int).reshape(-1, 3)

            if assimp_mesh.uvs is not None:
                uvs = np.asarray(assimp_mesh.uvs, dtype=float)
            else:
                uvs = None

            mesh = Mesh3(vertices=verts, triangles=idx, uvs=uvs)

            # если нормали есть – присвоим
            if assimp_mesh.normals is not None:
                mesh.vertex_normals = np.asarray(assimp_mesh.normals, dtype=float)
            else:
                mesh.compute_vertex_normals()

            return mesh


    def scale(self, factor: float):
        """Uniformly scale vertex positions by ``factor``."""
        self.vertices *= factor

    def get_vertex_count(self) -> int:
        return self.vertices.shape[0]

    def get_face_count(self) -> int:
        return self.triangles.shape[0]

    def compute_faces_normals(self):
        """Compute per-face normals ``n = (v1-v0) × (v2-v0) / ||...||``."""
        v0 = self.vertices[self.triangles[:, 0], :]
        v1 = self.vertices[self.triangles[:, 1], :]
        v2 = self.vertices[self.triangles[:, 2], :]
        normals = np.cross(v1 - v0, v2 - v0)
        norms = np.linalg.norm(normals, axis=1, keepdims=True)
        norms[norms == 0] = 1  # Prevent division by zero
        self.face_normals = normals / norms
        return self.face_normals

    def compute_vertex_normals(self):
        """Compute area-weighted vertex normals: ``n_v = sum_{t∈F(v)} ( (v1-v0) × (v2-v0) ).``"""
        normals = np.zeros_like(self.vertices, dtype=np.float64)
        v0 = self.vertices[self.triangles[:, 0], :]
        v1 = self.vertices[self.triangles[:, 1], :]
        v2 = self.vertices[self.triangles[:, 2], :]
        face_normals = np.cross(v1 - v0, v2 - v0)
        for face, normal in zip(self.triangles, face_normals):
            normals[face] += normal
        norms = np.linalg.norm(normals, axis=1)
        norms[norms == 0] = 1.0
        self.vertex_normals = (normals.T / norms).T.astype(np.float32)
        return self.vertex_normals

    @staticmethod
    def from_convex_hull(hull) -> "Mesh3":
        """Create a Mesh from a scipy.spatial.ConvexHull object."""
        vertices = hull.points
        triangles = hull.simplices

        center = np.mean(vertices, axis=0)

        for i in range(triangles.shape[0]):
            v0 = vertices[triangles[i, 0]]
            v1 = vertices[triangles[i, 1]]
            v2 = vertices[triangles[i, 2]]
            normal = np.cross(v1 - v0, v2 - v0)
            to_center = center - v0
            if np.dot(normal, to_center) > 0:
                triangles[i, [1, 2]] = triangles[i, [2, 1]]

        return Mesh3(vertices=vertices, triangles=triangles)

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
