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
from termin.editor.inspect_field import InspectField
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

    inspect_fields = {
        "skip_astar_if_los": InspectField(
            path="skip_astar_if_los",
            label="Skip A* if direct LOS",
            kind="bool",
        ),
        "use_funnel": InspectField(
            path="use_funnel",
            label="Use Funnel Algorithm",
            kind="bool",
        ),
        "use_los_optimization": InspectField(
            path="use_los_optimization",
            label="Optimize with LOS",
            kind="bool",
        ),
        "use_edge_centers": InspectField(
            path="use_edge_centers",
            label="Use Edge Centers",
            kind="bool",
        ),
        "show_graph_edges": InspectField(
            path="show_graph_edges",
            label="Show Graph Edges",
            kind="bool",
        ),
    }

    serializable_fields = [
        "skip_astar_if_los",
        "use_funnel",
        "use_los_optimization",
        "use_edge_centers",
        "show_graph_edges",
    ]

    def __init__(
        self,
        skip_astar_if_los: bool = True,
        use_funnel: bool = True,
        use_los_optimization: bool = True,
        use_edge_centers: bool = False,
        show_graph_edges: bool = False,
    ) -> None:
        super().__init__(enabled=True)

        self.active_in_editor = True

        self.skip_astar_if_los = skip_astar_if_los
        self.use_funnel = use_funnel
        self.use_los_optimization = use_los_optimization
        self.use_edge_centers = use_edge_centers
        self.show_graph_edges = show_graph_edges

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

    def update(self, dt: float) -> None:
        """Обновление каждый кадр."""
        self.draw()

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

        # Получаем entity для трансформации
        entity = self._region_entities.get(start_region)
        transform = entity.transform.global_pose().as_matrix() if entity else None
        inverse = np.linalg.inv(transform) if transform is not None else None

        # Трансформируем start/end в локальные координаты
        if inverse is not None:
            local_start = self._transform_point(start, inverse)
            local_end = self._transform_point(end, inverse)
        else:
            local_start = start.copy()
            local_end = end.copy()

        # Быстрая проверка: прямая видимость?
        if self.skip_astar_if_los and navmesh_line_of_sight(
            local_start, local_end, start_tri_idx,
            region.triangles, region.vertices, region.neighbors
        ):
            log.info("[PathfindingWorld] direct LOS, skipping A*")
            local_path = [local_start, local_end]
            # Трансформируем результат в мировые координаты
            path_points: List[np.ndarray] = []
            for local_point in local_path:
                if transform is not None:
                    world_point = self._transform_point(local_point, transform)
                    path_points.append(world_point)
                else:
                    path_points.append(local_point.copy())
            return path_points

        if start_tri_idx == end_tri_idx:
            path_indices = [start_tri_idx]
        else:
            from termin.navmesh.pathfinding import astar_triangles
            if self.use_edge_centers:
                path_indices = astar_triangles(
                    start_tri_idx, end_tri_idx, region.neighbors, region.centroids,
                    region.triangles, region.vertices,
                    start_pos=local_start, end_pos=local_end
                )
            else:
                path_indices = astar_triangles(
                    start_tri_idx, end_tri_idx, region.neighbors, region.centroids,
                    start_pos=local_start, end_pos=local_end
                )
            if path_indices is None:
                return None

        log.info(f"[PathfindingWorld] A* path: {len(path_indices)} triangles")

        # Строим путь в зависимости от настроек
        if self.use_funnel:
            # Funnel Algorithm
            portals = get_portals_from_path(
                path_indices, region.triangles, region.vertices, region.neighbors
            )
            log.info(f"[PathfindingWorld] portals: {len(portals)}")

            # Вычисляем нормаль региона из первого треугольника
            first_tri = region.triangles[path_indices[0]]
            v0 = region.vertices[first_tri[0]]
            v1 = region.vertices[first_tri[1]]
            v2 = region.vertices[first_tri[2]]
            region_normal = np.cross(v1 - v0, v2 - v0)
            n_len = float(np.linalg.norm(region_normal))
            if n_len > 1e-10:
                region_normal = region_normal / n_len
            else:
                region_normal = np.array([0.0, 1.0, 0.0], dtype=np.float64)

            local_path = funnel_algorithm(local_start, local_end, portals, region_normal)
            log.info(f"[PathfindingWorld] funnel path: {len(local_path)} points")
        else:
            # Путь через центроиды треугольников
            local_path = [local_start]
            for tri_idx in path_indices:
                local_path.append(region.centroids[tri_idx].copy())
            local_path.append(local_end)
            log.info(f"[PathfindingWorld] centroid path: {len(local_path)} points")

        # Оптимизация через line of sight
        if self.use_los_optimization and len(local_path) > 2:
            local_path = self._optimize_path_los(
                local_path, start_tri_idx, region.triangles, region.vertices, region.neighbors
            )
            log.info(f"[PathfindingWorld] LOS optimized: {len(local_path)} points")

        # Трансформируем результат в мировые координаты
        path_points: List[np.ndarray] = []
        for local_point in local_path:
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
        if self.use_edge_centers:
            path_indices = astar_triangles(
                start_tri_idx, end_tri_idx, region.neighbors, region.centroids,
                region.triangles, region.vertices
            )
        else:
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
        current_tri = start_tri

        while current_idx < len(path) - 1:
            # Пробуем найти самую дальнюю точку с прямой видимостью
            best_skip = current_idx + 1

            for test_idx in range(len(path) - 1, current_idx + 1, -1):
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

            # Добавляем следующую точку и обновляем current_tri
            next_point = path[best_skip]
            optimized.append(next_point)

            # Находим треугольник для новой текущей точки
            next_tri = find_triangle_containing_point(next_point, vertices, triangles)
            if next_tri >= 0:
                current_tri = next_tri
            # Если не нашли — оставляем предыдущий (не идеально, но лучше чем start_tri)

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

    def draw(self) -> None:
        """Отрисовка отладочной визуализации."""
        if not self.show_graph_edges:
            return

        from termin.visualization.render.immediate import ImmediateRenderer
        from termin.geombase import Vec3
        from termin.graphics import Color4

        renderer = ImmediateRenderer.instance()
        if renderer is None:
            return

        if not self._navmesh_graph.regions:
            return

        renderer.begin()
        green = Color4(0.0, 1.0, 0.0, 1.0)
        cyan = Color4(0.0, 0.8, 0.8, 0.5)

        # Рисуем рёбра графа для каждого региона
        for region_id, region in enumerate(self._navmesh_graph.regions):
            entity = self._region_entities.get(region_id)
            transform = None
            if entity is not None:
                transform = entity.transform.global_pose().as_matrix()

            triangles = region.triangles
            vertices = region.vertices
            neighbors = region.neighbors
            centroids = region.centroids

            # Для каждого треугольника рисуем линии к соседям
            drawn_edges: set[tuple[int, int]] = set()
            for tri_idx in range(len(triangles)):
                tri_centroid = centroids[tri_idx]

                for edge_idx in range(3):
                    neighbor_idx = neighbors[tri_idx, edge_idx]
                    if neighbor_idx < 0:
                        continue

                    # Избегаем дублирования рёбер
                    edge_key = (min(tri_idx, neighbor_idx), max(tri_idx, neighbor_idx))
                    if edge_key in drawn_edges:
                        continue
                    drawn_edges.add(edge_key)

                    neighbor_centroid = centroids[neighbor_idx]

                    if self.use_edge_centers:
                        # Через центры рёбер: centroid -> edge_center -> centroid
                        v0_idx = triangles[tri_idx, edge_idx]
                        v1_idx = triangles[tri_idx, (edge_idx + 1) % 3]
                        edge_center = (vertices[v0_idx] + vertices[v1_idx]) * 0.5

                        start = tri_centroid.copy()
                        end = edge_center.copy()
                        if transform is not None:
                            start = self._transform_point(start, transform)
                            end = self._transform_point(end, transform)
                        renderer.line(
                            Vec3(float(start[0]), float(start[1]), float(start[2])),
                            Vec3(float(end[0]), float(end[1]), float(end[2])),
                            green,
                            depth_test=True,
                        )

                        start = edge_center.copy()
                        end = neighbor_centroid.copy()
                        if transform is not None:
                            start = self._transform_point(start, transform)
                            end = self._transform_point(end, transform)
                        renderer.line(
                            Vec3(float(start[0]), float(start[1]), float(start[2])),
                            Vec3(float(end[0]), float(end[1]), float(end[2])),
                            green,
                            depth_test=True,
                        )
                    else:
                        # Напрямую: centroid -> centroid
                        start = tri_centroid.copy()
                        end = neighbor_centroid.copy()
                        if transform is not None:
                            start = self._transform_point(start, transform)
                            end = self._transform_point(end, transform)
                        renderer.line(
                            Vec3(float(start[0]), float(start[1]), float(start[2])),
                            Vec3(float(end[0]), float(end[1]), float(end[2])),
                            green,
                            depth_test=True,
                        )

            # Рисуем рёбра треугольников
            for tri_idx in range(len(triangles)):
                tri = triangles[tri_idx]
                for edge_idx in range(3):
                    v0 = vertices[tri[edge_idx]].copy()
                    v1 = vertices[tri[(edge_idx + 1) % 3]].copy()

                    if transform is not None:
                        v0 = self._transform_point(v0, transform)
                        v1 = self._transform_point(v1, transform)

                    renderer.line(
                        Vec3(float(v0[0]), float(v0[1]), float(v0[2])),
                        Vec3(float(v1[0]), float(v1[1]), float(v1[2])),
                        cyan,
                        depth_test=True,
                    )


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
