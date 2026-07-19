"""Backend-neutral geometry helpers shared by navmesh integrations."""

from __future__ import annotations

import numpy as np


def build_line_ribbon(
    points: list[tuple[float, float, float]],
    width: float,
    up_hint: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Build a camera-independent triangle ribbon for a 3D polyline."""
    if len(points) < 2 or width <= 0.0:
        return (
            np.zeros((0, 3), dtype=np.float32),
            np.zeros((0, 3), dtype=np.int32),
        )

    up = np.asarray(up_hint, dtype=np.float32)
    up_norm = float(np.linalg.norm(up))
    if up_norm < 1e-6:
        up = np.array([0.0, 0.0, 1.0], dtype=np.float32)
    else:
        up = up / up_norm

    vertices: list[np.ndarray] = []
    triangles: list[tuple[int, int, int]] = []
    half_width = width * 0.5

    for index in range(len(points) - 1):
        p0 = np.asarray(points[index], dtype=np.float32)
        p1 = np.asarray(points[index + 1], dtype=np.float32)
        direction = p1 - p0
        length = float(np.linalg.norm(direction))
        if length < 1e-6:
            continue
        direction = direction / length

        side = np.cross(up, direction)
        side_norm = float(np.linalg.norm(side))
        if side_norm < 1e-6:
            side = np.cross(np.array([1.0, 0.0, 0.0], dtype=np.float32), direction)
            side_norm = float(np.linalg.norm(side))
        if side_norm < 1e-6:
            side = np.cross(np.array([0.0, 1.0, 0.0], dtype=np.float32), direction)
            side_norm = float(np.linalg.norm(side))
        if side_norm < 1e-6:
            continue
        side = (side / side_norm) * half_width

        base = len(vertices)
        vertices.extend([p0 - side, p0 + side, p1 - side, p1 + side])
        triangles.append((base, base + 1, base + 2))
        triangles.append((base + 1, base + 3, base + 2))

    if not vertices:
        return (
            np.zeros((0, 3), dtype=np.float32),
            np.zeros((0, 3), dtype=np.int32),
        )

    return (
        np.vstack(vertices).astype(np.float32),
        np.asarray(triangles, dtype=np.int32),
    )


__all__ = ["build_line_ribbon"]
