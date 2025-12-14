"""
VoxelMesh — меш с поддержкой vertex colors для отображения вокселей.
"""

from __future__ import annotations

import numpy as np

from termin.mesh.mesh import Mesh3, VertexLayout, VertexAttribute, VertexAttribType


class VoxelMesh(Mesh3):
    """
    Меш с дополнительным атрибутом vertex_colors для цветового кодирования.

    Layout: position(3) + normal(3) + uv(2) + color(3) = 11 floats per vertex.
    """

    def __init__(
        self,
        vertices: np.ndarray,
        triangles: np.ndarray,
        uvs: np.ndarray | None = None,
        vertex_colors: np.ndarray | None = None,
    ):
        super().__init__(vertices, triangles, uvs)
        self.vertex_colors = (
            np.asarray(vertex_colors, dtype=np.float32)
            if vertex_colors is not None
            else None
        )

    def build_interleaved_buffer(self):
        # позиции
        pos = self.vertices.astype(np.float32)

        # нормали
        if self.vertex_normals is None:
            normals = np.zeros_like(self.vertices, dtype=np.float32)
        else:
            normals = self.vertex_normals.astype(np.float32)

        # uv
        if self.uvs is None:
            uvs = np.zeros((self.vertices.shape[0], 2), dtype=np.float32)
        else:
            uvs = self.uvs.astype(np.float32)

        # colors
        if self.vertex_colors is None:
            colors = np.ones((self.vertices.shape[0], 3), dtype=np.float32)
        else:
            colors = self.vertex_colors.astype(np.float32)

        return np.hstack([pos, normals, uvs, colors])

    def get_vertex_layout(self) -> VertexLayout:
        # position(3) + normal(3) + uv(2) + color(3) = 11 floats = 44 bytes
        return VertexLayout(
            stride=11 * 4,
            attributes=[
                VertexAttribute("position", 3, VertexAttribType.FLOAT32, 0),
                VertexAttribute("normal", 3, VertexAttribType.FLOAT32, 12),
                VertexAttribute("uv", 2, VertexAttribType.FLOAT32, 24),
                VertexAttribute("color", 3, VertexAttribType.FLOAT32, 32),
            ],
        )
