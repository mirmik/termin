"""
Базовые структуры данных для NavMesh.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import numpy as np


@dataclass
class NavMeshConfig:
    """Конфигурация для построения NavMesh."""

    normal_threshold: float = 0.9
    """Порог схожести нормалей (косинус угла). 0.9 ≈ 25°, 0.866 ≈ 30°."""

    min_region_voxels: int = 1
    """Минимальное количество вокселей в регионе."""

    contour_epsilon: float = 0.1
    """Порог для Douglas-Peucker упрощения контуров (в мировых координатах)."""

    voronoi_cell_size: float = 1.0
    """Размер ячейки Вороного (шаг сетки сидов, в мировых координатах)."""


@dataclass
class NavPolygon:
    """
    Полигон навигационной сетки.

    Представляет собой плоскую область, по которой можно перемещаться.
    """

    vertices: np.ndarray
    """Вершины полигона в мировых координатах, shape (N, 3)."""

    triangles: np.ndarray
    """Индексы треугольников, shape (M, 3)."""

    normal: np.ndarray
    """Усреднённая нормаль полигона, shape (3,)."""

    voxel_coords: list[tuple[int, int, int]] = field(default_factory=list)
    """Воксельные координаты, из которых построен полигон."""

    neighbors: list[int] = field(default_factory=list)
    """Индексы соседних полигонов (заполняется позже)."""

    outer_contour: Optional[list[int]] = None
    """Внешний контур — упорядоченный список индексов вершин (CCW). None если не вычислен."""

    holes: list[list[int]] = field(default_factory=list)
    """Дыры — список контуров, каждый контур — список индексов вершин (CW)."""


@dataclass
class NavMesh:
    """
    Навигационная сетка.

    Набор полигонов с информацией о связности.
    """

    polygons: list[NavPolygon] = field(default_factory=list)
    """Список полигонов."""

    cell_size: float = 0.25
    """Размер вокселя, из которого построена сетка."""

    origin: np.ndarray = field(default_factory=lambda: np.zeros(3, dtype=np.float32))
    """Начало координат воксельной сетки."""

    name: str = ""
    """Имя навигационной сетки."""

    def polygon_count(self) -> int:
        """Количество полигонов."""
        return len(self.polygons)

    def triangle_count(self) -> int:
        """Общее количество треугольников."""
        return sum(len(p.triangles) for p in self.polygons)

    def vertex_count(self) -> int:
        """Общее количество вершин."""
        return sum(len(p.vertices) for p in self.polygons)
