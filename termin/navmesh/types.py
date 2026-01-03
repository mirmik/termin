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

    max_edge_length: float = 0.0
    """Макс. длина ребра треугольника. 0 = без ограничения."""

    min_edge_length: float = 0.0
    """Мин. длина внутреннего ребра (edge collapse). 0 = без схлопывания."""

    min_contour_edge_length: float = 0.0
    """Мин. длина ребра на контуре (edge collapse). 0 = без схлопывания."""

    max_vertex_valence: int = 0
    """Макс. количество треугольников на вершину. 0 = без ограничения."""

    use_delaunay_flip: bool = True
    """Применять Delaunay edge flipping для улучшения качества треугольников."""

    use_valence_flip: bool = False
    """Применять edge flipping для уменьшения валентности вершин."""

    use_angle_flip: bool = False
    """Применять edge flipping для максимизации минимального угла."""

    use_cvt_smoothing: bool = False
    """Применять CVT (Centroidal Voronoi Tessellation) для оптимизации позиций вершин."""

    use_second_pass: bool = False
    """Повторный проход flips + smoothing после edge collapse."""


@dataclass
class Portal:
    """
    Портал между двумя регионами NavMesh.

    Представляет собой границу между соседними полигонами.
    """

    region_a: int
    """Индекс первого региона."""

    region_b: int
    """Индекс второго региона."""

    voxels: list[tuple[int, int, int]]
    """Воксели, образующие портал."""

    center: np.ndarray
    """Центр портала в мировых координатах, shape (3,)."""

    width: float
    """Ширина портала (расстояние между крайними вокселями)."""

    left: np.ndarray = field(default_factory=lambda: np.zeros(3, dtype=np.float32))
    """Левый конец портала в мировых координатах."""

    right: np.ndarray = field(default_factory=lambda: np.zeros(3, dtype=np.float32))
    """Правый конец портала в мировых координатах."""


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

    source_path: str | None = None
    """Путь к файлу-источнику."""

    def polygon_count(self) -> int:
        """Количество полигонов."""
        return len(self.polygons)

    def triangle_count(self) -> int:
        """Общее количество треугольников."""
        return sum(len(p.triangles) for p in self.polygons)

    def vertex_count(self) -> int:
        """Общее количество вершин."""
        return sum(len(p.vertices) for p in self.polygons)

    # ----------------------------------------------------------------
    # Сериализация
    # ----------------------------------------------------------------

    def direct_serialize(self) -> dict:
        """
        Сериализует NavMesh в словарь.

        Если source_path задан, возвращает ссылку на файл.
        Иначе сериализует данные inline.
        """
        if self.source_path is not None:
            return {
                "type": "path",
                "path": self.source_path,
            }

        return {
            "type": "inline",
            "name": self.name,
            "cell_size": self.cell_size,
            "origin": self.origin.tolist(),
            "polygons": [
                {
                    "vertices": p.vertices.tolist(),
                    "triangles": p.triangles.tolist(),
                    "normal": p.normal.tolist(),
                    "neighbors": p.neighbors,
                }
                for p in self.polygons
            ],
        }

    @classmethod
    def direct_deserialize(cls, data: dict) -> "NavMesh":
        """Десериализует NavMesh из словаря."""
        source_path = data.get("path") if data.get("type") == "path" else None

        polygons = []
        for p_data in data.get("polygons", []):
            polygon = NavPolygon(
                vertices=np.array(p_data["vertices"], dtype=np.float32),
                triangles=np.array(p_data["triangles"], dtype=np.int32),
                normal=np.array(p_data["normal"], dtype=np.float32),
                neighbors=p_data.get("neighbors", []),
            )
            polygons.append(polygon)

        return cls(
            polygons=polygons,
            cell_size=data.get("cell_size", 0.25),
            origin=np.array(data.get("origin", [0, 0, 0]), dtype=np.float32),
            name=data.get("name", ""),
            source_path=source_path,
        )
