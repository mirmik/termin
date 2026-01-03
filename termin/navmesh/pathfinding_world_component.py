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
from termin.navmesh.pathfinding import (
    RegionGraph,
    NavMeshGraph,
    get_portals_from_path,
    funnel_algorithm,
    navmesh_line_of_sight,
)
from termin.navmesh.types import NavMesh

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene
    from termin.visualization.core.entity import Entity
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
        # (navmesh, entity)
        self._navmesh_sources: List[tuple[NavMesh, "Entity"]] = []
        # Маппинг region_id -> entity (для получения актуальной трансформации)
        self._region_entities: dict[int, "Entity"] = {}

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
                self._navmesh_sources.append((navmesh, entity))
                pos = entity.transform.global_pose().lin
                log.info(f"[PathfindingWorld] found NavMesh '{name}' ({navmesh.polygon_count()} polygons) at ({pos.x:.2f}, {pos.y:.2f}, {pos.z:.2f})")
            else:
                log.warn(f"[PathfindingWorld] NavMesh '{name}' not found in ResourceManager")

        # Рекурсивно обходим детей
        for child_transform in entity.transform.children:
            if child_transform.entity is not None:
                self._collect_from_entity(child_transform.entity, visited_entities, rm)

    def _build_graph(self) -> None:
        """Построить NavMeshGraph из собранных NavMesh."""
        self._navmesh_graph = NavMeshGraph()
        self._region_entities.clear()

        region_id = 0
        for navmesh, entity in self._navmesh_sources:
            for poly_idx, polygon in enumerate(navmesh.polygons):
                verts_count = len(polygon.vertices) if polygon.vertices is not None else 0
                tris_count = len(polygon.triangles) if polygon.triangles is not None else 0
                log.info(f"[PathfindingWorld] polygon {poly_idx}: {verts_count} verts, {tris_count} tris")
                if verts_count == 0 or tris_count == 0:
                    continue

                # Храним вершины в ЛОКАЛЬНЫХ координатах
                local_verts = polygon.vertices

                # Создаём RegionGraph для каждого полигона
                region = RegionGraph.from_mesh(
                    vertices=local_verts,
                    triangles=polygon.triangles,
                    region_id=region_id,
                )
                self._navmesh_graph.add_region(region)

                # Сохраняем entity для получения актуальной трансформации
                self._region_entities[region_id] = entity
                region_id += 1

        log.info(f"[PathfindingWorld] built graph with {region_id} regions")

    def _transform_vertices(self, vertices: np.ndarray, matrix: np.ndarray) -> np.ndarray:
        """Трансформировать вершины с помощью матрицы 4x4."""
        n = len(vertices)
        if n == 0:
            return vertices

        # Добавляем w=1 для гомогенных координат
        ones = np.ones((n, 1), dtype=np.float32)
        verts_h = np.hstack([vertices, ones])  # (N, 4)

        # Применяем трансформ
        transformed = (matrix @ verts_h.T).T  # (N, 4)

        # Возвращаем xyz
        return transformed[:, :3].astype(np.float32)

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
            start: Начальная точка (3D) в мировых координатах.
            end: Конечная точка (3D) в мировых координатах.

        Returns:
            Список точек пути (центры треугольников) в мировых координатах,
            или None если путь не найден.
        """
        if not self._initialized:
            log.warn("[PathfindingWorld] not initialized")
            return None

        log.info(f"[PathfindingWorld] find_path: start={start}, end={end}")

        # Ищем треугольники с учётом трансформаций
        start_tri = self.find_containing_triangle(start)
        log.info(f"[PathfindingWorld] start_tri={start_tri}")
        end_tri = self.find_containing_triangle(end)
        log.info(f"[PathfindingWorld] end_tri={end_tri}")

        if start_tri is None:
            log.info("[PathfindingWorld] start point not on navmesh")
            return None
        if end_tri is None:
            log.info("[PathfindingWorld] end point not on navmesh")
            return None

        start_region, start_tri_idx = start_tri
        end_region, end_tri_idx = end_tri

        # Пока поддерживаем только путь внутри одного региона
        if start_region != end_region:
            log.info("[PathfindingWorld] cross-region pathfinding not yet supported")
            return None

        region = self._navmesh_graph.regions[start_region]

        if start_tri_idx == end_tri_idx:
            path_indices = [start_tri_idx]
        else:
            from termin.navmesh.pathfinding import astar_triangles
            path_indices = astar_triangles(
                start_tri_idx, end_tri_idx, region.neighbors, region.centroids
            )
            if path_indices is None:
                return None

        log.info(f"[PathfindingWorld] A* path: {len(path_indices)} triangles")

        # Получаем entity для трансформации
        entity = self._region_entities.get(start_region)
        transform = entity.transform.global_pose().as_matrix() if entity else None
        inverse = np.linalg.inv(transform) if transform is not None else None

        # Трансформируем start/end в локальные координаты для funnel algorithm
        if inverse is not None:
            local_start = self._transform_point(start, inverse)
            local_end = self._transform_point(end, inverse)
        else:
            local_start = start.copy()
            local_end = end.copy()

        # Извлекаем порталы из пути
        portals = get_portals_from_path(
            path_indices, region.triangles, region.vertices, region.neighbors
        )
        log.info(f"[PathfindingWorld] portals: {len(portals)}")

        # Применяем Funnel Algorithm
        local_path = funnel_algorithm(local_start, local_end, portals)
        log.info(f"[PathfindingWorld] funnel path: {len(local_path)} points")

        # Оптимизация: пробуем срезать путь через line of sight
        optimized_path = self._optimize_path_los(
            local_path, start_tri_idx, region.triangles, region.vertices, region.neighbors
        )
        log.info(f"[PathfindingWorld] optimized path: {len(optimized_path)} points")

        # Трансформируем результат в мировые координаты
        path_points: List[np.ndarray] = []
        for local_point in optimized_path:
            if transform is not None:
                world_point = self._transform_point(local_point, transform)
                path_points.append(world_point)
            else:
                path_points.append(local_point.copy())

        return path_points

    def find_path_triangles(
        self,
        start: np.ndarray,
        end: np.ndarray,
    ) -> Optional[List[tuple[int, int]]]:
        """
        Найти путь между двумя точками (возвращает индексы треугольников).

        Args:
            start: Начальная точка (3D) в мировых координатах.
            end: Конечная точка (3D) в мировых координатах.

        Returns:
            Список (region_id, triangle_id), или None если путь не найден.
        """
        if not self._initialized:
            return None

        # Ищем треугольники с учётом трансформаций
        start_tri = self.find_containing_triangle(start)
        end_tri = self.find_containing_triangle(end)

        if start_tri is None or end_tri is None:
            return None

        start_region, start_tri_idx = start_tri
        end_region, end_tri_idx = end_tri

        # Пока поддерживаем только путь внутри одного региона
        if start_region != end_region:
            return None

        region = self._navmesh_graph.regions[start_region]

        if start_tri_idx == end_tri_idx:
            return [(start_region, start_tri_idx)]

        from termin.navmesh.pathfinding import astar_triangles
        path_indices = astar_triangles(
            start_tri_idx, end_tri_idx, region.neighbors, region.centroids
        )
        if path_indices is None:
            return None

        return [(start_region, tri_idx) for tri_idx in path_indices]

    def get_triangle_center(self, region_id: int, triangle_id: int) -> Optional[np.ndarray]:
        """Получить центр треугольника по его индексам (в мировых координатах)."""
        if region_id >= len(self._navmesh_graph.regions):
            return None

        region = self._navmesh_graph.regions[region_id]
        if triangle_id >= len(region.centroids):
            return None

        local_centroid = region.centroids[triangle_id]
        entity = self._region_entities.get(region_id)
        if entity is not None:
            transform = entity.transform.global_pose().as_matrix()
            return self._transform_point(local_centroid, transform)
        return local_centroid.copy()

    def find_containing_triangle(self, point: np.ndarray) -> Optional[tuple[int, int]]:
        """
        Найти треугольник, содержащий точку.

        Args:
            point: Точка в 3D пространстве (мировые координаты).

        Returns:
            (region_id, triangle_id) или None если точка вне NavMesh.
        """
        log.info(f"[PathfindingWorld] find_containing_triangle: point={point}")
        for region_id, region in enumerate(self._navmesh_graph.regions):
            # Трансформируем точку в локальные координаты региона
            entity = self._region_entities.get(region_id)
            if entity is not None:
                inverse = np.linalg.inv(entity.transform.global_pose().as_matrix())
                local_point = self._transform_point(point, inverse)
            else:
                local_point = point

            tri_idx = region.find_triangle(local_point)
            if tri_idx >= 0:
                log.info(f"[PathfindingWorld] found in region {region_id}, tri {tri_idx}")
                return (region_id, tri_idx)
        log.info("[PathfindingWorld] not found in any region")
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
            origin: Начало луча (3D) в мировых координатах.
            direction: Направление луча (нормализованное) в мировых координатах.
            max_distance: Максимальная дистанция.

        Returns:
            (hit_point, distance, region_id, triangle_id) или None если нет пересечения.
            hit_point в мировых координатах.
        """
        closest_hit: Optional[tuple[np.ndarray, float, int, int]] = None
        closest_dist = max_distance

        for region_id, region in enumerate(self._navmesh_graph.regions):
            # Получаем актуальную трансформацию entity
            entity = self._region_entities.get(region_id)
            if entity is None:
                continue

            # Трансформируем луч в локальное пространство entity
            transform_matrix = entity.transform.global_pose().as_matrix()
            inverse_matrix = np.linalg.inv(transform_matrix)

            local_origin = self._transform_point(origin, inverse_matrix)
            local_direction = self._transform_direction(direction, inverse_matrix)

            # Нормализуем направление после трансформации
            dir_len = float(np.linalg.norm(local_direction))
            if dir_len < 1e-8:
                continue
            local_direction = local_direction / dir_len

            for tri_idx in range(len(region.triangles)):
                tri = region.triangles[tri_idx]
                v0 = region.vertices[tri[0]]
                v1 = region.vertices[tri[1]]
                v2 = region.vertices[tri[2]]

                hit = _ray_triangle_intersect(local_origin, local_direction, v0, v1, v2)
                if hit is not None:
                    t_local = hit
                    # Точка попадания в локальных координатах
                    local_hit = local_origin + local_direction * t_local
                    # Трансформируем обратно в мировые координаты
                    world_hit = self._transform_point(local_hit, transform_matrix)
                    # Расстояние в мировых координатах
                    world_dist = float(np.linalg.norm(world_hit - origin))

                    if 0 < world_dist < closest_dist:
                        closest_dist = world_dist
                        closest_hit = (world_hit, world_dist, region_id, tri_idx)

        return closest_hit

    def _transform_point(self, point: np.ndarray, matrix: np.ndarray) -> np.ndarray:
        """Трансформировать точку с помощью матрицы 4x4."""
        p_h = np.array([point[0], point[1], point[2], 1.0], dtype=np.float64)
        result = matrix @ p_h
        return result[:3].astype(np.float32)

    def _transform_direction(self, direction: np.ndarray, matrix: np.ndarray) -> np.ndarray:
        """Трансформировать направление с помощью матрицы 4x4 (без translation)."""
        d_h = np.array([direction[0], direction[1], direction[2], 0.0], dtype=np.float64)
        result = matrix @ d_h
        return result[:3].astype(np.float32)

    def _optimize_path_los(
        self,
        path: List[np.ndarray],
        start_tri: int,
        triangles: np.ndarray,
        vertices: np.ndarray,
        neighbors: np.ndarray,
    ) -> List[np.ndarray]:
        """
        Оптимизировать путь через проверку прямой видимости.

        Пробует срезать промежуточные точки, если есть прямая видимость.
        """
        if len(path) <= 2:
            return path

        from termin.navmesh.pathfinding import find_triangle_containing_point

        optimized: List[np.ndarray] = [path[0]]
        current_idx = 0

        while current_idx < len(path) - 1:
            # Пробуем найти самую дальнюю точку с прямой видимостью
            best_skip = current_idx + 1

            for test_idx in range(len(path) - 1, current_idx + 1, -1):
                # Находим треугольник текущей точки
                current_tri = find_triangle_containing_point(
                    optimized[-1], vertices, triangles
                )
                if current_tri < 0:
                    current_tri = start_tri

                # Проверяем прямую видимость
                if navmesh_line_of_sight(
                    optimized[-1],
                    path[test_idx],
                    current_tri,
                    triangles,
                    vertices,
                    neighbors,
                ):
                    best_skip = test_idx
                    break

            optimized.append(path[best_skip])
            current_idx = best_skip

        return optimized

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
