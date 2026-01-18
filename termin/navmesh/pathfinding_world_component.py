"""
PathfindingWorldComponent — глобальный компонент для поиска пути.

Собирает NavMesh из NavMeshRegistry, строит NavMeshGraph и обрабатывает запросы на поиск пути.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional
import numpy as np

from termin._native import log
from termin.visualization.core.python_component import PythonComponent
from termin.editor.inspect_field import InspectField
from termin.navmesh.pathfinding import (
    RegionGraph,
    NavMeshGraph,
    get_portals_from_path,
    funnel_algorithm,
    navmesh_line_of_sight,
)
from termin.navmesh.types import NavMesh, Portal
from termin.navmesh.region_growing import NEIGHBORS_26

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene
    from termin.visualization.core.entity import Entity


def _rebuild_graph_action(component: "PathfindingWorldComponent") -> None:
    """Rebuild graph button action."""
    component.rebuild()


class PathfindingWorldComponent(PythonComponent):
    """
    Глобальный компонент для поиска пути по NavMesh.

    Использование:
    1. Добавить компонент к любой сущности в сцене
    2. Компонент автоматически соберёт NavMesh из всех VoxelizerComponent
    3. Вызывать find_path(start, end) для поиска пути

    Доступ через статический instance:
        PathfindingWorldComponent.instance()
    """

    _instance: "PathfindingWorldComponent | None" = None

    @classmethod
    def instance(cls) -> "PathfindingWorldComponent | None":
        """Get the global PathfindingWorldComponent instance."""
        return cls._instance

    inspect_fields = {
        "agent_type_name": InspectField(
            path="agent_type_name",
            label="Agent Type",
            kind="agent_type",
        ),
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
        "show_portals": InspectField(
            path="show_portals",
            label="Show Portals",
            kind="bool",
        ),
        "rebuild_btn": InspectField(
            label="Rebuild Graph",
            kind="button",
            action=_rebuild_graph_action,
            is_serializable=False,
        ),
    }

    serializable_fields = [
        "agent_type_name",
        "skip_astar_if_los",
        "use_funnel",
        "use_los_optimization",
        "use_edge_centers",
        "show_graph_edges",
        "show_portals",
    ]

    def __init__(
        self,
        agent_type_name: str = "Human",
        skip_astar_if_los: bool = True,
        use_funnel: bool = True,
        use_los_optimization: bool = True,
        use_edge_centers: bool = False,
        show_graph_edges: bool = False,
        show_portals: bool = False,
    ) -> None:
        super().__init__(enabled=True)

        self.active_in_editor = True

        self.agent_type_name = agent_type_name
        self.skip_astar_if_los = skip_astar_if_los
        self.use_funnel = use_funnel
        self.use_los_optimization = use_los_optimization
        self.use_edge_centers = use_edge_centers
        self.show_graph_edges = show_graph_edges
        self.show_portals = show_portals

        self._navmesh_graph: NavMeshGraph = NavMeshGraph()
        self._initialized: bool = False
        # (navmesh, entity) - from NavMeshRegistry
        self._navmesh_sources: List[tuple[NavMesh, "Entity"]] = []
        # Маппинг region_id -> entity (для получения актуальной трансформации)
        self._region_entities: dict[int, "Entity"] = {}
        # Порталы между регионами
        self._portals: List[Portal] = []
        # Маппинг region_id -> navmesh info для вычисления порталов
        self._region_navmesh_info: dict[int, tuple[NavMesh, int]] = {}

    @property
    def navmesh_graph(self) -> NavMeshGraph:
        """Глобальный граф навигации."""
        return self._navmesh_graph

    @property
    def region_count(self) -> int:
        """Количество регионов в графе."""
        return len(self._navmesh_graph.regions)

    def on_added(self, scene: "Scene") -> None:
        """Called when added to scene. Build graph in editor mode."""
        super().on_added(scene)
        # Register as global instance
        PathfindingWorldComponent._instance = self
        # Auto-rebuild in editor mode
        self.rebuild()

    def start(self) -> None:
        """Инициализация при старте сцены (game mode)."""
        super().start()
        # Register as global instance
        PathfindingWorldComponent._instance = self
        # Rebuild graph for game mode
        self.rebuild()

    def update(self, dt: float) -> None:
        """Обновление каждый кадр."""
        self.draw()

    def _collect_navmeshes(self, scene: "Scene") -> None:
        """Собрать NavMesh из NavMeshRegistry для выбранного типа агента."""
        from termin.navmesh.registry import NavMeshRegistry

        self._navmesh_sources.clear()

        registry = NavMeshRegistry.for_scene(scene)
        entries = registry.get_all(self.agent_type_name)

        if not entries:
            log.warn(f"[PathfindingWorld] no NavMesh found for agent type '{self.agent_type_name}'")
            return

        for navmesh, entity in entries:
            self._navmesh_sources.append((navmesh, entity))

        print(f"[PathfindingWorld] collected {len(self._navmesh_sources)} NavMesh for agent '{self.agent_type_name}'")

    def _build_graph(self) -> None:
        """Построить NavMeshGraph из собранных NavMesh."""
        self._navmesh_graph = NavMeshGraph()
        self._region_entities.clear()
        self._region_navmesh_info.clear()
        self._portals.clear()

        region_id = 0
        for navmesh, entity in self._navmesh_sources:
            for poly_idx, polygon in enumerate(navmesh.polygons):
                verts_count = len(polygon.vertices) if polygon.vertices is not None else 0
                tris_count = len(polygon.triangles) if polygon.triangles is not None else 0
                if verts_count == 0 or tris_count == 0:
                    continue

                # Вершины в локальных координатах entity
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
                # Сохраняем navmesh и poly_idx для вычисления порталов
                self._region_navmesh_info[region_id] = (navmesh, poly_idx)
                region_id += 1

        print(f"[PathfindingWorld] built graph with {region_id} regions")

        # Вычисляем порталы между регионами
        self._compute_portals()

    def _compute_portals(self) -> None:
        """
        Вычислить порталы между соседними регионами.

        Алгоритм:
        1. Строим voxel_to_region map
        2. Находим соседние воксели между разными регионами
        3. Кластеризуем границу по связности
        4. Каждый кластер становится порталом
        """
        from collections import deque

        self._portals.clear()

        if not self._region_navmesh_info:
            return

        # Шаг 1: Построить voxel_to_region map
        voxel_to_region: dict[tuple[int, int, int], int] = {}
        for region_id, (navmesh, poly_idx) in self._region_navmesh_info.items():
            polygon = navmesh.polygons[poly_idx]
            for voxel in polygon.voxel_coords:
                voxel_to_region[voxel] = region_id

        if not voxel_to_region:
            # log.debug("[PathfindingWorld] no voxel coords in polygons, skipping portal computation")
            return

        # Шаг 2: Найти все пары соседних регионов и граничные воксели
        # Структура: {(region_a, region_b): set of voxels from region_a on boundary}
        boundary_pairs: dict[tuple[int, int], set[tuple[int, int, int]]] = {}

        for voxel, region_id in voxel_to_region.items():
            vx, vy, vz = voxel
            for dx, dy, dz in NEIGHBORS_26:
                neighbor = (vx + dx, vy + dy, vz + dz)
                if neighbor in voxel_to_region:
                    neighbor_region = voxel_to_region[neighbor]
                    if neighbor_region != region_id:
                        # Нашли границу между регионами
                        # Используем упорядоченную пару для ключа
                        pair_key = (min(region_id, neighbor_region), max(region_id, neighbor_region))
                        if pair_key not in boundary_pairs:
                            boundary_pairs[pair_key] = set()
                        boundary_pairs[pair_key].add(voxel)
                        boundary_pairs[pair_key].add(neighbor)

        # Шаг 3: Для каждой пары регионов кластеризуем граничные воксели
        for (region_a, region_b), boundary_voxels in boundary_pairs.items():
            # Кластеризация по связности
            remaining = set(boundary_voxels)

            while remaining:
                # BFS для нахождения связного кластера
                cluster: list[tuple[int, int, int]] = []
                seed = next(iter(remaining))
                queue: deque[tuple[int, int, int]] = deque([seed])
                remaining.remove(seed)

                while queue:
                    current = queue.popleft()
                    cluster.append(current)

                    vx, vy, vz = current
                    for dx, dy, dz in NEIGHBORS_26:
                        neighbor = (vx + dx, vy + dy, vz + dz)
                        if neighbor in remaining:
                            remaining.remove(neighbor)
                            queue.append(neighbor)

                # Создаём портал для этого кластера
                if cluster:
                    portal = self._create_portal(region_a, region_b, cluster)
                    self._portals.append(portal)

        # log.debug(f"[PathfindingWorld] computed {len(self._portals)} portals")

        # Строим граф смежности регионов
        self._navmesh_graph.build_region_adjacency(self._portals)
        # log.debug(f"[PathfindingWorld] built region adjacency: {len(self._navmesh_graph.region_adjacency)} regions")

    def _create_portal(
        self,
        region_a: int,
        region_b: int,
        voxels: list[tuple[int, int, int]],
    ) -> Portal:
        """Создать портал из списка граничных вокселей."""
        # Получаем cell_size и origin из navmesh
        navmesh, _ = self._region_navmesh_info[region_a]
        cell_size = navmesh.cell_size
        origin = navmesh.origin

        # Конвертируем воксели в мировые координаты
        world_coords = []
        for vx, vy, vz in voxels:
            world_pos = np.array([
                origin[0] + vx * cell_size + cell_size * 0.5,
                origin[1] + vy * cell_size + cell_size * 0.5,
                origin[2] + vz * cell_size + cell_size * 0.5,
            ], dtype=np.float32)
            world_coords.append(world_pos)

        # Вычисляем центр портала
        center = np.mean(world_coords, axis=0).astype(np.float32)

        # Вычисляем ширину и находим крайние точки (left/right)
        width = 0.0
        left_idx = 0
        right_idx = 0
        if len(world_coords) > 1:
            for i in range(len(world_coords)):
                for j in range(i + 1, len(world_coords)):
                    dist = float(np.linalg.norm(world_coords[i] - world_coords[j]))
                    if dist > width:
                        width = dist
                        left_idx = i
                        right_idx = j

        left = world_coords[left_idx].copy()
        right = world_coords[right_idx].copy() if right_idx != left_idx else left.copy()

        return Portal(
            region_a=region_a,
            region_b=region_b,
            voxels=voxels,
            center=center,
            width=width,
            left=left,
            right=right,
        )

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
        if self._scene is None:
            return
        self._collect_navmeshes(self._scene)
        self._build_graph()
        self._initialized = True

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

        # log.debug(f"[PathfindingWorld] find_path: start={start}, end={end}")

        # Ищем треугольники с учётом трансформаций
        start_tri = self.find_containing_triangle(start)
        # log.debug(f"[PathfindingWorld] start_tri={start_tri}")
        end_tri = self.find_containing_triangle(end)
        # log.debug(f"[PathfindingWorld] end_tri={end_tri}")

        if start_tri is None:
            # log.debug("[PathfindingWorld] start point not on navmesh")
            return None
        if end_tri is None:
            # log.debug("[PathfindingWorld] end point not on navmesh")
            return None

        start_region, start_tri_idx = start_tri
        end_region, end_tri_idx = end_tri

        # Межрегиональный путь
        if start_region != end_region:
            return self._find_cross_region_path(
                start, end, start_region, end_region, start_tri_idx, end_tri_idx
            )

        # Путь внутри одного региона
        return self._find_single_region_path(
            start, end, start_region, start_tri_idx, end_tri_idx
        )

    def _find_single_region_path(
        self,
        start: np.ndarray,
        end: np.ndarray,
        region_id: int,
        start_tri_idx: int,
        end_tri_idx: int,
    ) -> Optional[List[np.ndarray]]:
        """Найти путь внутри одного региона."""
        region = self._navmesh_graph.regions[region_id]

        # Получаем entity для трансформации
        entity = self._region_entities.get(region_id)
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
            # log.debug("[PathfindingWorld] direct LOS, skipping A*")
            return self._transform_path_to_world([local_start, local_end], transform)

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

        # log.debug(f"[PathfindingWorld] A* path: {len(path_indices)} triangles")

        # Строим путь в зависимости от настроек
        if self.use_funnel:
            # Funnel Algorithm
            portals = get_portals_from_path(
                path_indices, region.triangles, region.vertices, region.neighbors
            )
            # log.debug(f"[PathfindingWorld] portals: {len(portals)}")

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
            # log.debug(f"[PathfindingWorld] funnel path: {len(local_path)} points")
        else:
            # Путь через центроиды треугольников
            local_path = [local_start]
            for tri_idx in path_indices:
                local_path.append(region.centroids[tri_idx].copy())
            local_path.append(local_end)
            # log.debug(f"[PathfindingWorld] centroid path: {len(local_path)} points")

        # Оптимизация через line of sight
        if self.use_los_optimization and len(local_path) > 2:
            local_path = self._optimize_path_los(
                local_path, start_tri_idx, region.triangles, region.vertices, region.neighbors
            )
            # log.debug(f"[PathfindingWorld] LOS optimized: {len(local_path)} points")

        return self._transform_path_to_world(local_path, transform)

    def _find_cross_region_path(
        self,
        start: np.ndarray,
        end: np.ndarray,
        start_region: int,
        end_region: int,
        start_tri_idx: int,
        end_tri_idx: int,
    ) -> Optional[List[np.ndarray]]:
        """Найти путь между разными регионами через порталы."""
        # log.debug(f"[PathfindingWorld] cross-region: {start_region} -> {end_region}")

        # Высокоуровневый A* для поиска пути через регионы
        try:
            region_path = self._navmesh_graph.find_region_path(
                start_region, end_region, self._portals
            )
        except Exception as e:
            log.error(f"[PathfindingWorld] find_region_path failed: {e}")
            return None

        if region_path is None:
            # log.debug("[PathfindingWorld] no region path found")
            return None

        # log.debug(f"[PathfindingWorld] region path: {region_path}")

        # Собираем полный путь через все регионы
        full_path: List[np.ndarray] = [start.copy()]
        current_pos = start.copy()
        current_tri_idx = start_tri_idx

        for i, (region_id, portal_idx) in enumerate(region_path):
            is_last = (i == len(region_path) - 1)
            is_first = (i == 0)

            # log.debug(f"[PathfindingWorld] segment {i}: region={region_id}, portal_idx={portal_idx}, is_last={is_last}")

            # Для первого сегмента используем start_tri_idx, для остальных ищем в текущем регионе
            if is_first:
                current_tri_idx = start_tri_idx
            else:
                current_tri_idx = self._find_triangle_in_region(current_pos, region_id)
                if current_tri_idx < 0:
                    log.warn(f"[PathfindingWorld] current_pos not in region {region_id}, using nearest")
                    # Портал на границе — попробуем найти ближайший треугольник
                    current_tri_idx = self._find_nearest_triangle_in_region(current_pos, region_id)
                    if current_tri_idx < 0:
                        log.warn(f"[PathfindingWorld] no triangle found, skipping to target")
                        # Всё равно идём к target напрямую
                        pass

            # Определяем целевую точку в этом регионе
            if is_last:
                target_pos = end.copy()
                target_tri_idx = end_tri_idx
            else:
                # Идём к порталу
                if portal_idx < 0 or portal_idx >= len(self._portals):
                    log.warn(f"[PathfindingWorld] invalid portal_idx={portal_idx}")
                    continue

                portal = self._portals[portal_idx]
                entity = self._region_entities.get(region_id)
                transform = entity.transform.global_pose().as_matrix() if entity else None

                # Трансформируем концы портала в мировые координаты
                if transform is not None:
                    portal_left = self._transform_point(portal.left, transform)
                    portal_right = self._transform_point(portal.right, transform)
                else:
                    portal_left = portal.left.copy()
                    portal_right = portal.right.copy()

                # Находим оптимальную точку на ребре портала
                # (ближайшую к прямой current_pos -> end)
                target_pos = self._closest_point_on_segment_to_line(
                    portal_left, portal_right, current_pos, end
                )

                # Находим треугольник для портала в текущем регионе
                target_tri_idx = self._find_triangle_in_region(target_pos, region_id)
                if target_tri_idx < 0:
                    log.warn(f"[PathfindingWorld] portal point not in region {region_id}")
                    full_path.append(target_pos.copy())
                    current_pos = target_pos.copy()
                    continue

            # log.debug(f"[PathfindingWorld] current_pos={current_pos}, target_pos={target_pos}")
            # log.debug(f"[PathfindingWorld] current_tri={current_tri_idx}, target_tri={target_tri_idx}")

            # Находим путь внутри региона
            segment_path = None
            if current_tri_idx >= 0 and target_tri_idx >= 0:
                try:
                    segment_path = self._find_single_region_path(
                        current_pos, target_pos, region_id, current_tri_idx, target_tri_idx
                    )
                except Exception as e:
                    log.error(f"[PathfindingWorld] error in _find_single_region_path: {e}")
                    segment_path = None

            if segment_path is not None and len(segment_path) > 1:
                # Добавляем точки сегмента (пропуская первую — она уже есть)
                for point in segment_path[1:]:
                    full_path.append(point)
                # log.debug(f"[PathfindingWorld] added {len(segment_path) - 1} points from segment")
            else:
                # Если не нашли путь внутри региона, идём напрямую
                full_path.append(target_pos.copy())
                # log.debug("[PathfindingWorld] segment failed, adding direct line")

            current_pos = target_pos.copy()

        # log.debug(f"[PathfindingWorld] cross-region path: {len(full_path)} points")
        return full_path if len(full_path) > 1 else None

    def _transform_path_to_world(
        self,
        local_path: List[np.ndarray],
        transform: Optional[np.ndarray],
    ) -> List[np.ndarray]:
        """Трансформировать путь из локальных в мировые координаты."""
        path_points: List[np.ndarray] = []
        for local_point in local_path:
            if transform is not None:
                world_point = self._transform_point(local_point, transform)
                path_points.append(world_point)
            else:
                path_points.append(local_point.copy())
        return path_points

    def _find_triangle_in_region(self, point: np.ndarray, region_id: int) -> int:
        """
        Найти треугольник, содержащий точку, в конкретном регионе.

        Args:
            point: Точка в мировых координатах.
            region_id: ID региона для поиска.

        Returns:
            Индекс треугольника в регионе, или -1 если не найден.
        """
        if region_id >= len(self._navmesh_graph.regions):
            return -1

        region = self._navmesh_graph.regions[region_id]

        # Трансформируем точку в локальные координаты региона
        entity = self._region_entities.get(region_id)
        if entity is not None:
            inverse = np.linalg.inv(entity.transform.global_pose().as_matrix())
            local_point = self._transform_point(point, inverse)
        else:
            local_point = point

        return region.find_triangle(local_point)

    def _find_nearest_triangle_in_region(self, point: np.ndarray, region_id: int) -> int:
        """
        Найти ближайший треугольник к точке в конкретном регионе.

        Используется когда точка на границе и find_triangle не находит её.

        Args:
            point: Точка в мировых координатах.
            region_id: ID региона для поиска.

        Returns:
            Индекс ближайшего треугольника, или -1 если регион пустой.
        """
        if region_id >= len(self._navmesh_graph.regions):
            return -1

        region = self._navmesh_graph.regions[region_id]
        if len(region.centroids) == 0:
            return -1

        # Трансформируем точку в локальные координаты региона
        entity = self._region_entities.get(region_id)
        if entity is not None:
            inverse = np.linalg.inv(entity.transform.global_pose().as_matrix())
            local_point = self._transform_point(point, inverse)
        else:
            local_point = point

        # Находим ближайший центроид
        best_idx = 0
        best_dist = float('inf')
        for i, centroid in enumerate(region.centroids):
            dist = float(np.linalg.norm(local_point - centroid))
            if dist < best_dist:
                best_dist = dist
                best_idx = i

        return best_idx

    def _closest_point_on_segment_to_line(
        self,
        seg_a: np.ndarray,
        seg_b: np.ndarray,
        line_p: np.ndarray,
        line_q: np.ndarray,
    ) -> np.ndarray:
        """
        Найти точку на отрезке [seg_a, seg_b], ближайшую к прямой line_p -> line_q.

        Используется для выбора оптимальной точки прохода через портал.
        """
        # Направление отрезка
        seg_dir = seg_b - seg_a
        seg_len_sq = float(np.dot(seg_dir, seg_dir))

        if seg_len_sq < 1e-10:
            # Вырожденный отрезок
            return seg_a.copy()

        # Направление линии
        line_dir = line_q - line_p
        line_len_sq = float(np.dot(line_dir, line_dir))

        if line_len_sq < 1e-10:
            # Вырожденная линия — возвращаем ближайшую точку к line_p
            t = np.dot(line_p - seg_a, seg_dir) / seg_len_sq
            t = max(0.0, min(1.0, t))
            return (seg_a + t * seg_dir).astype(np.float32)

        # Находим точку пересечения двух прямых (или ближайшие точки)
        # Используем метод для 3D: находим параметры s и t такие что
        # seg_a + s * seg_dir и line_p + t * line_dir минимизируют расстояние

        w0 = seg_a - line_p
        a = float(np.dot(seg_dir, seg_dir))
        b = float(np.dot(seg_dir, line_dir))
        c = float(np.dot(line_dir, line_dir))
        d = float(np.dot(seg_dir, w0))
        e = float(np.dot(line_dir, w0))

        denom = a * c - b * b
        if abs(denom) < 1e-10:
            # Параллельные линии — проецируем line_p на отрезок
            s = np.dot(line_p - seg_a, seg_dir) / seg_len_sq
        else:
            s = (b * e - c * d) / denom

        # Ограничиваем s в пределах [0, 1]
        s = max(0.0, min(1.0, s))

        return (seg_a + s * seg_dir).astype(np.float32)

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
        # log.debug(f"[PathfindingWorld] find_containing_triangle: point={point}")
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
                # log.debug(f"[PathfindingWorld] found in region {region_id}, tri {tri_idx}")
                return (region_id, tri_idx)
        # log.debug("[PathfindingWorld] not found in any region")
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
        from termin.visualization.render.immediate import ImmediateRenderer
        from termin.geombase import Vec3
        from termin.graphics import Color4

        renderer = ImmediateRenderer.instance()
        if renderer is None:
            return

        # Всегда вызываем begin() чтобы очистить предыдущий кадр
        renderer.begin()

        if not self.show_graph_edges and not self.show_portals:
            return

        # Рисуем порталы
        if self.show_portals and self._portals:
            magenta = Color4(1.0, 0.0, 1.0, 1.0)
            yellow = Color4(1.0, 1.0, 0.0, 1.0)

            for portal in self._portals:
                # Получаем трансформацию entity для региона A
                entity = self._region_entities.get(portal.region_a)
                transform = None
                if entity is not None:
                    transform = entity.transform.global_pose().as_matrix()

                # Рисуем центр портала как крестик
                center = portal.center.copy()
                if transform is not None:
                    center = self._transform_point(center, transform)

                # Размер крестика зависит от ширины портала
                cross_size = max(0.1, portal.width * 0.3)

                # Крестик в XZ плоскости
                renderer.line(
                    Vec3(float(center[0]) - cross_size, float(center[1]), float(center[2])),
                    Vec3(float(center[0]) + cross_size, float(center[1]), float(center[2])),
                    magenta,
                    depth_test=True,
                )
                renderer.line(
                    Vec3(float(center[0]), float(center[1]), float(center[2]) - cross_size),
                    Vec3(float(center[0]), float(center[1]), float(center[2]) + cross_size),
                    magenta,
                    depth_test=True,
                )

                # Рисуем воксели портала
                navmesh, _ = self._region_navmesh_info.get(portal.region_a, (None, 0))
                if navmesh is not None:
                    cell_size = navmesh.cell_size
                    origin = navmesh.origin

                    for vx, vy, vz in portal.voxels:
                        world_pos = np.array([
                            origin[0] + vx * cell_size + cell_size * 0.5,
                            origin[1] + vy * cell_size + cell_size * 0.5,
                            origin[2] + vz * cell_size + cell_size * 0.5,
                        ], dtype=np.float32)

                        if transform is not None:
                            world_pos = self._transform_point(world_pos, transform)

                        # Маленький квадрат для каждого вокселя
                        half = cell_size * 0.3
                        renderer.line(
                            Vec3(float(world_pos[0]) - half, float(world_pos[1]), float(world_pos[2]) - half),
                            Vec3(float(world_pos[0]) + half, float(world_pos[1]), float(world_pos[2]) - half),
                            yellow,
                            depth_test=True,
                        )
                        renderer.line(
                            Vec3(float(world_pos[0]) + half, float(world_pos[1]), float(world_pos[2]) - half),
                            Vec3(float(world_pos[0]) + half, float(world_pos[1]), float(world_pos[2]) + half),
                            yellow,
                            depth_test=True,
                        )
                        renderer.line(
                            Vec3(float(world_pos[0]) + half, float(world_pos[1]), float(world_pos[2]) + half),
                            Vec3(float(world_pos[0]) - half, float(world_pos[1]), float(world_pos[2]) + half),
                            yellow,
                            depth_test=True,
                        )
                        renderer.line(
                            Vec3(float(world_pos[0]) - half, float(world_pos[1]), float(world_pos[2]) + half),
                            Vec3(float(world_pos[0]) - half, float(world_pos[1]), float(world_pos[2]) - half),
                            yellow,
                            depth_test=True,
                        )

        if not self.show_graph_edges:
            return

        if not self._navmesh_graph.regions:
            return

        green = Color4(0.0, 1.0, 0.0, 1.0)
        cyan = Color4(0.0, 0.8, 0.8, 0.5)

        normal_offset = 0.15  # Смещение по нормали для видимости

        # Рисуем рёбра графа для каждого региона
        for region_id, region in enumerate(self._navmesh_graph.regions):
            if region_id not in self._region_navmesh_info:
                continue
            entity = self._region_entities.get(region_id)
            transform = None
            if entity is not None:
                transform = entity.transform.global_pose().as_matrix()

            # Получаем нормаль региона для смещения
            region_normal = np.array([0.0, 1.0, 0.0], dtype=np.float32)
            navmesh_info = self._region_navmesh_info.get(region_id)
            if navmesh_info is not None:
                navmesh, poly_idx = navmesh_info
                if poly_idx < len(navmesh.polygons):
                    region_normal = navmesh.polygons[poly_idx].normal

            triangles = region.triangles
            vertices = region.vertices + region_normal * normal_offset
            neighbors = region.neighbors
            centroids = region.centroids + region_normal * normal_offset

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
