"""
Функции для создания мешей с vertex colors для отображения вокселей.

Использует TcMesh и tc_mesh registry.
"""

from __future__ import annotations

import numpy as np

from termin.mesh._mesh_native import (
    TcMesh,
    TcVertexLayout,
    TcAttribType,
)


# Cached layout for voxel meshes
_voxel_layout: TcVertexLayout | None = None


def _get_voxel_layout() -> TcVertexLayout:
    """Get or create the tc_vertex_layout for voxel meshes.

    Layout: position(3) + normal(3) + uv(2) + color(3) = 11 floats = 44 bytes.
    """
    global _voxel_layout
    if _voxel_layout is None:
        layout = TcVertexLayout()
        layout.add("position", 3, TcAttribType.FLOAT32)
        layout.add("normal", 3, TcAttribType.FLOAT32)
        layout.add("uv", 2, TcAttribType.FLOAT32)
        layout.add("color", 3, TcAttribType.FLOAT32)
        _voxel_layout = layout
    return _voxel_layout


def create_voxel_mesh(
    vertices: np.ndarray,
    triangles: np.ndarray,
    uvs: np.ndarray | None = None,
    vertex_colors: np.ndarray | None = None,
    vertex_normals: np.ndarray | None = None,
    name: str = "voxel_mesh",
    uuid: str = "",
) -> TcMesh:
    """
    Create a TcMesh with vertex colors for voxel display.

    Layout: position(3) + normal(3) + uv(2) + color(3) = 11 floats per vertex.

    Args:
        vertices: Nx3 array of vertex positions
        triangles: Mx3 array of triangle indices
        uvs: Nx2 array of UV coordinates (optional, defaults to zeros)
        vertex_colors: Nx3 array of RGB colors (optional, defaults to white)
        vertex_normals: Nx3 array of normals (optional, defaults to zeros)
        name: Mesh name for debugging

    Returns:
        TcMesh registered in tc_mesh registry
    """
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

    layout = _get_voxel_layout()

    return TcMesh.from_interleaved(
        interleaved.flatten(),
        num_verts,
        tris,
        layout,
        name,
        uuid,
    )
