"""
PathfindingWorldComponent — глобальный компонент для поиска пути.

Собирает NavMesh из VoxelizerComponent, строит NavMeshGraph и обрабатывает запросы на поиск пути.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional
import numpy as np

from termin._native import log
from termin.visualization.core.python_component import PythonComponent
from termin.visualization.core.scene import get_current_scene
from termin.navmesh.pathfinding import RegionGraph, NavMeshGraph
from termin.navmesh.types import NavMesh

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene
    from termin.voxels.voxelizer_component import VoxelizerComponent


class PathfindingWorldComponent(PythonComponent):
    """
    Глобальный компонент для поиска пути по NavMesh.

    Использование:
    1. Добавить компонент к любой сущности в сцене
    2. Компонент автоматически соберёт NavMesh из всех VoxelizerComponent
    3. Вызывать find_path(start, end) для поиска пути
    """

    def __init__(self) -> None:
        super().__init__(enabled=True)

        self._navmesh_graph: NavMeshGraph = NavMeshGraph()
        self._voxelizer_components: List["VoxelizerComponent"] = []
        self._initialized: bool = False
        self._navmesh_sources: List[NavMesh] = []

    @property
    def navmesh_graph(self) -> NavMeshGraph:
        """Глобальный граф навигации."""
        return self._navmesh_graph

    @property
    def region_count(self) -> int:
        """Количество регионов в графе."""
        return len(self._navmesh_graph.regions)

    def start(self) -> None:
        """Инициализация при старте сцены."""
        super().start()
        scene = get_current_scene()
        if not scene:
            return

        self._collect_navmeshes(scene)
        self._build_graph()
        self._initialized = True

    def _collect_navmeshes(self, scene: "Scene") -> None:
        """Найти все VoxelizerComponent и собрать их NavMesh."""
        from termin.voxels.voxelizer_component import VoxelizerComponent
        from termin.visualization.core.resources import ResourceManager

        self._voxelizer_components.clear()
        self._navmesh_sources.clear()

        rm = ResourceManager.instance()

        visited_entities = set()
        for entity in scene.entities:
            self._collect_from_entity(entity, visited_entities, rm)

        log.info(f"[PathfindingWorld] collected {len(self._navmesh_sources)} NavMeshes")

    def _collect_from_entity(self, entity, visited_entities: set, rm) -> None:
        """Рекурсивно собрать NavMesh из дерева сущностей."""
        from termin.voxels.voxelizer_component import VoxelizerComponent

        entity_id = id(entity)
        if entity_id in visited_entities:
            return
        visited_entities.add(entity_id)

        vox_comp = entity.get_component(VoxelizerComponent)
        if vox_comp is not None:
            self._voxelizer_components.append(vox_comp)

            # Получаем NavMesh из ResourceManager по имени грида
            name = vox_comp.grid_name.strip()
            if not name:
                name = entity.name or "voxel_grid"

            log.info(f"[PathfindingWorld] found VoxelizerComponent '{entity.name}', grid_name='{name}'")
            navmesh = rm.get_navmesh(name)
            if navmesh is not None:
                self._navmesh_sources.append(navmesh)
                log.info(f"[PathfindingWorld] found NavMesh '{name}' ({navmesh.polygon_count()} polygons)")
            else:
                log.warn(f"[PathfindingWorld] NavMesh '{name}' not found in ResourceManager")

        # Рекурсивно обходим детей
        for child_transform in entity.transform.children:
            if child_transform.entity is not None:
                self._collect_from_entity(child_transform.entity, visited_entities, rm)

    def _build_graph(self) -> None:
        """Построить NavMeshGraph из собранных NavMesh."""
        self._navmesh_graph = NavMeshGraph()

        region_id = 0
        for navmesh in self._navmesh_sources:
            for polygon in navmesh.polygons:
                if len(polygon.vertices) == 0 or len(polygon.triangles) == 0:
                    continue

                # Создаём RegionGraph для каждого полигона
                region = RegionGraph.from_mesh(
                    vertices=polygon.vertices,
                    triangles=polygon.triangles,
                    region_id=region_id,
                )
                self._navmesh_graph.add_region(region)
                region_id += 1

        log.info(f"[PathfindingWorld] built graph with {region_id} regions")

    def rebuild(self) -> None:
        """Перестроить граф (вызывать после изменения NavMesh)."""
        scene = get_current_scene()
        if scene:
            self._collect_navmeshes(scene)
            self._build_graph()

    def find_path(
        self,
        start: np.ndarray,
        end: np.ndarray,
    ) -> Optional[List[np.ndarray]]:
        """
        Найти путь между двумя точками.

        Args:
            start: Начальная точка (3D).
            end: Конечная точка (3D).

        Returns:
            Список точек пути (центры треугольников), или None если путь не найден.
        """
        if not self._initialized:
            log.warn("[PathfindingWorld] not initialized")
            return None

        # Сначала ищем путь по графу регионов
        path_indices = self._navmesh_graph.find_path(start, end)
        if path_indices is None:
            return None

        # Конвертируем индексы треугольников в мировые координаты (центры)
        path_points: List[np.ndarray] = []

        for region_idx, tri_idx in path_indices:
            if region_idx < len(self._navmesh_graph.regions):
                region = self._navmesh_graph.regions[region_idx]
                if tri_idx < len(region.centroids):
                    path_points.append(region.centroids[tri_idx].copy())

        return path_points if path_points else None

    def find_path_triangles(
        self,
        start: np.ndarray,
        end: np.ndarray,
    ) -> Optional[List[tuple[int, int]]]:
        """
        Найти путь между двумя точками (возвращает индексы треугольников).

        Args:
            start: Начальная точка (3D).
            end: Конечная точка (3D).

        Returns:
            Список (region_id, triangle_id), или None если путь не найден.
        """
        if not self._initialized:
            return None

        return self._navmesh_graph.find_path(start, end)

    def get_triangle_center(self, region_id: int, triangle_id: int) -> Optional[np.ndarray]:
        """Получить центр треугольника по его индексам."""
        if region_id >= len(self._navmesh_graph.regions):
            return None

        region = self._navmesh_graph.regions[region_id]
        if triangle_id >= len(region.centroids):
            return None

        return region.centroids[triangle_id].copy()

    def find_containing_triangle(self, point: np.ndarray) -> Optional[tuple[int, int]]:
        """
        Найти треугольник, содержащий точку.

        Args:
            point: Точка в 3D пространстве.

        Returns:
            (region_id, triangle_id) или None если точка вне NavMesh.
        """
        for region_id, region in enumerate(self._navmesh_graph.regions):
            tri_idx = region.find_triangle(point)
            if tri_idx >= 0:
                return (region_id, tri_idx)
        return None

    def raycast(
        self,
        origin: np.ndarray,
        direction: np.ndarray,
        max_distance: float = 1000.0,
    ) -> Optional[tuple[np.ndarray, float, int, int]]:
        """
        Raycast по всем треугольникам NavMesh.

        Args:
            origin: Начало луча (3D).
            direction: Направление луча (нормализованное).
            max_distance: Максимальная дистанция.

        Returns:
            (hit_point, distance, region_id, triangle_id) или None если нет пересечения.
        """
        closest_hit: Optional[tuple[np.ndarray, float, int, int]] = None
        closest_dist = max_distance

        for region_id, region in enumerate(self._navmesh_graph.regions):
            for tri_idx in range(len(region.triangles)):
                tri = region.triangles[tri_idx]
                v0 = region.vertices[tri[0]]
                v1 = region.vertices[tri[1]]
                v2 = region.vertices[tri[2]]

                hit = _ray_triangle_intersect(origin, direction, v0, v1, v2)
                if hit is not None:
                    t = hit
                    if 0 < t < closest_dist:
                        closest_dist = t
                        hit_point = origin + direction * t
                        closest_hit = (hit_point, t, region_id, tri_idx)

        return closest_hit

    def raycast_from_screen(
        self,
        screen_x: float,
        screen_y: float,
        camera,
        viewport_rect: tuple,
        max_distance: float = 1000.0,
    ) -> Optional[tuple[np.ndarray, float, int, int]]:
        """
        Raycast от экранных координат.

        Args:
            screen_x: X координата на экране.
            screen_y: Y координата на экране.
            camera: CameraComponent для построения луча.
            viewport_rect: (x, y, width, height) вьюпорта.
            max_distance: Максимальная дистанция.

        Returns:
            (hit_point, distance, region_id, triangle_id) или None.
        """
        ray = camera.screen_point_to_ray(screen_x, screen_y, viewport_rect)

        origin = np.array([ray.origin.x, ray.origin.y, ray.origin.z], dtype=np.float32)
        direction = np.array([ray.direction.x, ray.direction.y, ray.direction.z], dtype=np.float32)

        # Нормализуем направление
        length = np.linalg.norm(direction)
        if length > 1e-8:
            direction = direction / length

        return self.raycast(origin, direction, max_distance)


def _ray_triangle_intersect(
    origin: np.ndarray,
    direction: np.ndarray,
    v0: np.ndarray,
    v1: np.ndarray,
    v2: np.ndarray,
    epsilon: float = 1e-8,
) -> Optional[float]:
    """
    Möller–Trumbore ray-triangle intersection.

    Args:
        origin: Начало луча.
        direction: Направление луча (нормализованное).
        v0, v1, v2: Вершины треугольника.
        epsilon: Порог для определения параллельности.

    Returns:
        Дистанция до пересечения (t) или None если нет пересечения.
    """
    edge1 = v1 - v0
    edge2 = v2 - v0

    h = np.cross(direction, edge2)
    a = np.dot(edge1, h)

    if -epsilon < a < epsilon:
        # Луч параллелен треугольнику
        return None

    f = 1.0 / a
    s = origin - v0
    u = f * np.dot(s, h)

    if u < 0.0 or u > 1.0:
        return None

    q = np.cross(s, edge1)
    v = f * np.dot(direction, q)

    if v < 0.0 or u + v > 1.0:
        return None

    t = f * np.dot(edge2, q)

    if t > epsilon:
        return float(t)

    return None
