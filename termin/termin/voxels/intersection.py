"""
Тесты пересечения для вокселизации.
"""

from __future__ import annotations

import numpy as np
from typing import Tuple

# Epsilon для численной устойчивости при сравнении с границами
_EPSILON = 1e-6


def triangle_aabb_intersect(
    v0: np.ndarray,
    v1: np.ndarray,
    v2: np.ndarray,
    box_center: np.ndarray,
    box_half_size: np.ndarray,
) -> bool:
    """
    Тест пересечения треугольника и AABB (axis-aligned bounding box).

    Алгоритм Tomas Akenine-Möller (SAT — Separating Axis Theorem).

    Args:
        v0, v1, v2: Вершины треугольника.
        box_center: Центр AABB.
        box_half_size: Половина размера AABB по каждой оси.

    Returns:
        True если пересекаются.
    """
    # Переносим треугольник так, чтобы центр AABB был в origin
    v0 = v0 - box_center
    v1 = v1 - box_center
    v2 = v2 - box_center

    # Рёбра треугольника
    e0 = v1 - v0
    e1 = v2 - v1
    e2 = v0 - v2

    hx, hy, hz = box_half_size

    # --- Тест 1: оси AABB (X, Y, Z) ---

    # Проверяем, что проекции треугольника и AABB пересекаются по каждой оси
    # Добавляем epsilon для численной устойчивости на границах

    # Ось X
    min_x = min(v0[0], v1[0], v2[0])
    max_x = max(v0[0], v1[0], v2[0])
    if min_x > hx + _EPSILON or max_x < -hx - _EPSILON:
        return False

    # Ось Y
    min_y = min(v0[1], v1[1], v2[1])
    max_y = max(v0[1], v1[1], v2[1])
    if min_y > hy + _EPSILON or max_y < -hy - _EPSILON:
        return False

    # Ось Z
    min_z = min(v0[2], v1[2], v2[2])
    max_z = max(v0[2], v1[2], v2[2])
    if min_z > hz + _EPSILON or max_z < -hz - _EPSILON:
        return False

    # --- Тест 2: нормаль треугольника ---

    normal = np.cross(e0, e1)
    d = -np.dot(normal, v0)

    # Проекция AABB на нормаль
    r = (
        hx * abs(normal[0]) +
        hy * abs(normal[1]) +
        hz * abs(normal[2])
    )

    if d > r + _EPSILON or d < -r - _EPSILON:
        return False

    # --- Тест 3: кросс-произведения рёбер ---

    # 9 осей: cross(edge_i, axis_j) для i=0,1,2 и j=X,Y,Z

    # e0 × X = (0, -e0.z, e0.y)
    if not _axis_test_x(e0, v0, v2, hy, hz):
        return False
    # e0 × Y = (e0.z, 0, -e0.x)
    if not _axis_test_y(e0, v0, v2, hx, hz):
        return False
    # e0 × Z = (-e0.y, e0.x, 0)
    if not _axis_test_z(e0, v0, v2, hx, hy):
        return False

    # e1 × X, Y, Z
    if not _axis_test_x(e1, v1, v0, hy, hz):
        return False
    if not _axis_test_y(e1, v1, v0, hx, hz):
        return False
    if not _axis_test_z(e1, v1, v0, hx, hy):
        return False

    # e2 × X, Y, Z
    if not _axis_test_x(e2, v2, v1, hy, hz):
        return False
    if not _axis_test_y(e2, v2, v1, hx, hz):
        return False
    if not _axis_test_z(e2, v2, v1, hx, hy):
        return False

    return True


def _axis_test_x(edge: np.ndarray, va: np.ndarray, vb: np.ndarray, hy: float, hz: float) -> bool:
    """Тест оси edge × X."""
    # axis = (0, -edge.z, edge.y)
    p0 = -edge[2] * va[1] + edge[1] * va[2]
    p1 = -edge[2] * vb[1] + edge[1] * vb[2]
    r = hy * abs(edge[2]) + hz * abs(edge[1])
    return not (min(p0, p1) > r + _EPSILON or max(p0, p1) < -r - _EPSILON)


def _axis_test_y(edge: np.ndarray, va: np.ndarray, vb: np.ndarray, hx: float, hz: float) -> bool:
    """Тест оси edge × Y."""
    # axis = (edge.z, 0, -edge.x)
    p0 = edge[2] * va[0] - edge[0] * va[2]
    p1 = edge[2] * vb[0] - edge[0] * vb[2]
    r = hx * abs(edge[2]) + hz * abs(edge[0])
    return not (min(p0, p1) > r + _EPSILON or max(p0, p1) < -r - _EPSILON)


def _axis_test_z(edge: np.ndarray, va: np.ndarray, vb: np.ndarray, hx: float, hy: float) -> bool:
    """Тест оси edge × Z."""
    # axis = (-edge.y, edge.x, 0)
    p0 = -edge[1] * va[0] + edge[0] * va[1]
    p1 = -edge[1] * vb[0] + edge[0] * vb[1]
    r = hx * abs(edge[1]) + hy * abs(edge[0])
    return not (min(p0, p1) > r + _EPSILON or max(p0, p1) < -r - _EPSILON)


def triangle_aabb(
    v0: np.ndarray,
    v1: np.ndarray,
    v2: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Вычислить AABB треугольника.

    Returns:
        (min_corner, max_corner)
    """
    min_corner = np.minimum(np.minimum(v0, v1), v2)
    max_corner = np.maximum(np.maximum(v0, v1), v2)
    return min_corner, max_corner
