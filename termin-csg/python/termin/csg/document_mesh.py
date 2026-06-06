"""Mesh conversion helpers for evaluated procedural CSG documents."""

from __future__ import annotations

import numpy as np

from tcbase import log
from tmesh import Mesh3, TcMesh

from termin.csg._csg_native import to_mesh3
from termin.csg.document_eval import evaluate_document
from termin.csg.procedural_document import ProceduralMeshDocument


def _compute_vertex_normals(vertices: np.ndarray, triangles: np.ndarray) -> np.ndarray:
    normals = np.zeros_like(vertices, dtype=np.float32)
    for i0, i1, i2 in triangles:
        v0 = vertices[int(i0)]
        v1 = vertices[int(i1)]
        v2 = vertices[int(i2)]
        face_normal = np.cross(v1 - v0, v2 - v0)
        length = float(np.linalg.norm(face_normal))
        if length <= 1.0e-8:
            continue
        face_normal = face_normal / length
        normals[int(i0)] += face_normal
        normals[int(i1)] += face_normal
        normals[int(i2)] += face_normal

    lengths = np.linalg.norm(normals, axis=1)
    mask = lengths > 1.0e-8
    normals[mask] = normals[mask] / lengths[mask, None]
    normals[~mask] = (0.0, 0.0, 1.0)
    return np.ascontiguousarray(normals, dtype=np.float32)


def document_to_mesh3(
    document: ProceduralMeshDocument,
    name: str = "procedural_mesh",
) -> Mesh3 | None:
    """Build one document-local Mesh3 from all evaluated root solids."""

    vertices_chunks: list[np.ndarray] = []
    triangle_chunks: list[np.ndarray] = []
    vertex_offset = 0

    for index, evaluated in enumerate(evaluate_document(document)):
        if evaluated.solid.is_empty:
            continue
        mesh_name = f"{name}-{index}"
        try:
            mesh = to_mesh3(evaluated.solid, mesh_name, "", True)
            vertices = np.asarray(mesh.vertices, dtype=np.float32).reshape(-1, 3)
            if vertices.size == 0:
                continue
            transformed_vertices = np.asarray(
                [evaluated.point_transform((float(v[0]), float(v[1]), float(v[2]))) for v in vertices],
                dtype=np.float32,
            )
            triangles = np.asarray(mesh.triangles, dtype=np.uint32).reshape(-1, 3)
            triangles = np.ascontiguousarray(triangles + vertex_offset, dtype=np.uint32)
            vertices_chunks.append(np.ascontiguousarray(transformed_vertices, dtype=np.float32))
            triangle_chunks.append(triangles)
            vertex_offset += transformed_vertices.shape[0]
        except Exception as e:
            log.error(
                "[ProceduralMeshDocument] failed to convert evaluated solid to Mesh3 "
                f"operation='{evaluated.operation_id}' contour='{evaluated.contour_id}': {e}"
            )
            return None

    if not vertices_chunks or not triangle_chunks:
        log.error("[ProceduralMeshDocument] cannot build Mesh3: document produced no non-empty solids")
        return None

    vertices = np.ascontiguousarray(np.vstack(vertices_chunks), dtype=np.float32)
    triangles = np.ascontiguousarray(np.vstack(triangle_chunks), dtype=np.uint32)
    normals = _compute_vertex_normals(vertices, triangles)
    return Mesh3(vertices=vertices, triangles=triangles, vertex_normals=normals, name=name)


def document_to_tc_mesh(
    document: ProceduralMeshDocument,
    name: str = "procedural_mesh",
    uuid: str = "",
) -> TcMesh | None:
    mesh = document_to_mesh3(document, name)
    if mesh is None:
        return None
    tc_mesh = TcMesh.from_mesh3(mesh, name, uuid)
    if not tc_mesh.is_valid:
        log.error(f"[ProceduralMeshDocument] failed to create TcMesh name='{name}'")
        return None
    return tc_mesh


__all__ = ["document_to_mesh3", "document_to_tc_mesh"]
