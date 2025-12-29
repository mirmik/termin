"""
VoxelMesh — меш с поддержкой vertex colors для отображения вокселей.

Использует tc_mesh registry для хранения данных и дедупликации по UUID.
"""

from __future__ import annotations

import numpy as np

from termin.mesh._mesh_native import (
    TcMeshHandle,
    TcVertexLayout,
    TcAttribType,
    tc_mesh_compute_uuid,
    tc_mesh_get_or_create,
    tc_mesh_set_data,
)
from termin.mesh.mesh import VertexLayout, VertexAttribute, VertexAttribType


class VoxelMesh:
    """
    Меш с дополнительным атрибутом vertex_colors для цветового кодирования.

    Layout: position(3) + normal(3) + uv(2) + color(3) = 11 floats per vertex.

    Использует tc_mesh registry — данные хранятся в C, дедуплицируются по UUID.
    """

    # Class-level layout (shared between all instances)
    _tc_layout: TcVertexLayout | None = None

    @classmethod
    def _get_tc_layout(cls) -> TcVertexLayout:
        """Get or create the tc_vertex_layout for VoxelMesh."""
        if cls._tc_layout is None:
            layout = TcVertexLayout()
            layout.add("position", 3, TcAttribType.FLOAT32)
            layout.add("normal", 3, TcAttribType.FLOAT32)
            layout.add("uv", 2, TcAttribType.FLOAT32)
            layout.add("color", 3, TcAttribType.FLOAT32)
            cls._tc_layout = layout
        return cls._tc_layout

    def __init__(
        self,
        name: str,
        vertices: np.ndarray,
        triangles: np.ndarray,
        uvs: np.ndarray | None = None,
        vertex_colors: np.ndarray | None = None,
        vertex_normals: np.ndarray | None = None,
    ):
        self._name = name
        self._handle: TcMeshHandle | None = None

        # Convert inputs to proper arrays
        verts = np.asarray(vertices, dtype=np.float32)
        tris = np.asarray(triangles, dtype=np.uint32).flatten()

        num_verts = verts.shape[0]

        # Prepare optional arrays
        if uvs is not None:
            uvs_arr = np.asarray(uvs, dtype=np.float32)
        else:
            uvs_arr = np.zeros((num_verts, 2), dtype=np.float32)

        if vertex_colors is not None:
            colors_arr = np.asarray(vertex_colors, dtype=np.float32)
        else:
            colors_arr = np.ones((num_verts, 3), dtype=np.float32)

        if vertex_normals is not None:
            normals_arr = np.asarray(vertex_normals, dtype=np.float32)
        else:
            normals_arr = np.zeros((num_verts, 3), dtype=np.float32)

        # Build interleaved buffer: pos(3) + normal(3) + uv(2) + color(3) = 11 floats
        interleaved = np.hstack([verts, normals_arr, uvs_arr, colors_arr]).astype(np.float32)

        # Compute UUID from data
        uuid = tc_mesh_compute_uuid(interleaved.flatten(), tris)

        # Debug: print mesh name and uuid
        print(f"[VoxelMesh] name='{name}' uuid={uuid[:16]}...")

        # Get or create mesh in registry
        self._handle = tc_mesh_get_or_create(uuid)

        # Set data if newly created (version == 1 and no vertices)
        if self._handle.is_valid and self._handle.vertex_count == 0:
            layout = self._get_tc_layout()
            tc_mesh_set_data(self._handle, name, interleaved.flatten(), num_verts, layout, tris)

    @property
    def name(self) -> str:
        """Mesh name."""
        if self._handle and self._handle.is_valid:
            return self._handle.name or self._name
        return self._name

    @property
    def uuid(self) -> str:
        """Unique identifier (hash of data)."""
        if self._handle and self._handle.is_valid:
            return self._handle.uuid
        return ""

    @property
    def version(self) -> int:
        """Version number (incremented on data change)."""
        if self._handle and self._handle.is_valid:
            return self._handle.version
        return 0

    @property
    def is_valid(self) -> bool:
        """Check if mesh is valid."""
        return self._handle is not None and self._handle.is_valid

    @property
    def tc_mesh(self):
        """Get underlying tc_mesh pointer (for MeshGPU.draw)."""
        if self._handle and self._handle.is_valid:
            return self._handle.mesh
        return None

    def get_vertex_count(self) -> int:
        """Get number of vertices."""
        if self._handle and self._handle.is_valid:
            return self._handle.vertex_count
        return 0

    def get_face_count(self) -> int:
        """Get number of triangles."""
        if self._handle and self._handle.is_valid:
            return self._handle.index_count // 3
        return 0

    @property
    def vertices(self) -> np.ndarray:
        """Get vertices as Nx3 array (extracts from interleaved buffer)."""
        if not self._handle or not self._handle.is_valid:
            return np.zeros((0, 3), dtype=np.float32)
        buf = self._handle.get_vertices_buffer()
        if buf is None:
            return np.zeros((0, 3), dtype=np.float32)
        # Layout: 11 floats per vertex, position at offset 0
        num_verts = self._handle.vertex_count
        buf = buf.reshape(num_verts, 11)
        return buf[:, 0:3].copy()

    @property
    def triangles(self) -> np.ndarray:
        """Get triangles as Mx3 array."""
        if not self._handle or not self._handle.is_valid:
            return np.zeros((0, 3), dtype=np.uint32)
        buf = self._handle.get_indices_buffer()
        if buf is None:
            return np.zeros((0, 3), dtype=np.uint32)
        return buf.reshape(-1, 3).copy()

    @property
    def vertex_normals(self) -> np.ndarray | None:
        """Get vertex normals as Nx3 array."""
        if not self._handle or not self._handle.is_valid:
            return None
        buf = self._handle.get_vertices_buffer()
        if buf is None:
            return None
        num_verts = self._handle.vertex_count
        buf = buf.reshape(num_verts, 11)
        return buf[:, 3:6].copy()

    @property
    def uvs(self) -> np.ndarray | None:
        """Get UVs as Nx2 array."""
        if not self._handle or not self._handle.is_valid:
            return None
        buf = self._handle.get_vertices_buffer()
        if buf is None:
            return None
        num_verts = self._handle.vertex_count
        buf = buf.reshape(num_verts, 11)
        return buf[:, 6:8].copy()

    @property
    def vertex_colors(self) -> np.ndarray | None:
        """Get vertex colors as Nx3 array."""
        if not self._handle or not self._handle.is_valid:
            return None
        buf = self._handle.get_vertices_buffer()
        if buf is None:
            return None
        num_verts = self._handle.vertex_count
        buf = buf.reshape(num_verts, 11)
        return buf[:, 8:11].copy()

    def interleaved_buffer(self) -> np.ndarray:
        """Get interleaved vertex buffer for GPU upload."""
        if not self._handle or not self._handle.is_valid:
            return np.zeros((0, 11), dtype=np.float32)
        buf = self._handle.get_vertices_buffer()
        if buf is None:
            return np.zeros((0, 11), dtype=np.float32)
        num_verts = self._handle.vertex_count
        return buf.reshape(num_verts, 11)

    def get_vertex_layout(self) -> VertexLayout:
        """Get vertex layout: position(3) + normal(3) + uv(2) + color(3) = 11 floats = 44 bytes."""
        return VertexLayout(
            stride=11 * 4,
            attributes=[
                VertexAttribute("position", 3, VertexAttribType.FLOAT32, 0),
                VertexAttribute("normal", 3, VertexAttribType.FLOAT32, 12),
                VertexAttribute("uv", 2, VertexAttribType.FLOAT32, 24),
                VertexAttribute("color", 3, VertexAttribType.FLOAT32, 32),
            ],
        )

    def compute_vertex_normals(self) -> None:
        """Compute vertex normals from triangle faces.

        Note: This creates a new mesh with computed normals (tc_mesh is immutable).
        """
        verts = self.vertices
        tris = self.triangles
        uvs = self.uvs
        colors = self.vertex_colors

        # Compute normals
        normals = np.zeros_like(verts, dtype=np.float32)
        for tri in tris:
            v0, v1, v2 = verts[tri[0]], verts[tri[1]], verts[tri[2]]
            n = np.cross(v1 - v0, v2 - v0)
            normals[tri[0]] += n
            normals[tri[1]] += n
            normals[tri[2]] += n
        norms = np.linalg.norm(normals, axis=1, keepdims=True)
        norms[norms == 0] = 1
        normals = normals / norms

        # Rebuild mesh with new normals
        self.__init__(self._name, verts, tris, uvs, colors, normals)

    def __repr__(self) -> str:
        if self._handle and self._handle.is_valid:
            return f"<VoxelMesh vertices={self.get_vertex_count()} triangles={self.get_face_count()} uuid={self.uuid[:16]}...>"
        return "<VoxelMesh invalid>"
