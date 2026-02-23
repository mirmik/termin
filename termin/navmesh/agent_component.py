"""
NavMeshAgentComponent — агент для перемещения по NavMesh.

Использует PathfindingWorldComponent для поиска пути.
При ЛКМ клике делает raycast по NavMesh и идёт к точке.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, List
import numpy as np

from tcbase import log
from termin.visualization.core.component import InputComponent
from termin.visualization.core.input_events import MouseButtonEvent
from termin.visualization.platform.backends.base import MouseButton, Action
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.navmesh.pathfinding_world_component import PathfindingWorldComponent


class NavMeshAgentComponent(InputComponent):
    """
    Агент для навигации по NavMesh.

    Использование:
    1. Добавить компонент к entity агента
    2. ЛКМ клик по NavMesh — агент идёт к точке клика
    3. Или вызвать set_destination(target) программно
    """

    inspect_fields = {
        "speed": InspectField(
            path="speed",
            label="Speed",
            kind="float",
            min=0.1,
            max=50.0,
            step=0.5,
        ),
        "stopping_distance": InspectField(
            path="stopping_distance",
            label="Stopping Distance",
            kind="float",
            min=0.01,
            max=5.0,
            step=0.1,
        ),
        "debug_draw_path": InspectField(
            path="debug_draw_path",
            label="Debug Draw Path",
            kind="bool",
        ),
        "click_to_move": InspectField(
            path="click_to_move",
            label="Click To Move",
            kind="bool",
        ),
    }

    serializable_fields = ["speed", "stopping_distance", "debug_draw_path", "click_to_move"]

    def __init__(
        self,
        speed: float = 5.0,
        stopping_distance: float = 0.1,
        debug_draw_path: bool = True,
        click_to_move: bool = True,
    ) -> None:
        super().__init__(enabled=True)

        self.active_in_editor = True

        self.speed: float = speed
        self.stopping_distance: float = stopping_distance
        self.debug_draw_path: bool = debug_draw_path
        self.click_to_move: bool = click_to_move

        self._pathfinding_world: Optional["PathfindingWorldComponent"] = None
        self._current_path: List[np.ndarray] = []
        self._current_path_index: int = 0
        self._destination: Optional[np.ndarray] = None
        self._is_moving: bool = False

    @property
    def is_moving(self) -> bool:
        """Двигается ли агент к цели."""
        return self._is_moving

    @property
    def has_path(self) -> bool:
        """Есть ли активный путь."""
        return len(self._current_path) > 0 and self._current_path_index < len(self._current_path)

    @property
    def destination(self) -> Optional[np.ndarray]:
        """Текущая цель."""
        return self._destination

    @property
    def current_waypoint(self) -> Optional[np.ndarray]:
        """Текущая промежуточная точка пути."""
        if self.has_path:
            return self._current_path[self._current_path_index]
        return None

    def start(self) -> None:
        """Инициализация — находим PathfindingWorldComponent."""
        super().start()
        self._find_pathfinding_world()

    def _find_pathfinding_world(self) -> None:
        """Найти PathfindingWorldComponent в сцене."""
        from termin.navmesh.pathfinding_world_component import PathfindingWorldComponent

        scene = self.entity.scene if self.entity else None
        if scene is None:
            return

        # Ищем в entity сцены
        for entity in scene.get_all_entities():
            comp = entity.get_component(PathfindingWorldComponent)
            if comp is not None:
                self._pathfinding_world = comp
                log.info(f"[NavMeshAgent] found PathfindingWorld with {comp.region_count} regions")
                return

            # Ищем в детях
            found = self._search_in_children(entity, PathfindingWorldComponent)
            if found is not None:
                self._pathfinding_world = found
                log.info(f"[NavMeshAgent] found PathfindingWorld with {found.region_count} regions")
                return

        log.warn("[NavMeshAgent] PathfindingWorldComponent not found in scene")

    def _search_in_children(self, entity, component_class):
        """Рекурсивный поиск компонента в детях."""
        for child_transform in entity.transform.children:
            if child_transform.entity is not None:
                comp = child_transform.entity.get_component(component_class)
                if comp is not None:
                    return comp
                found = self._search_in_children(child_transform.entity, component_class)
                if found is not None:
                    return found
        return None

    def set_destination(self, target: np.ndarray) -> bool:
        """
        Установить цель для движения.

        Args:
            target: Целевая точка в мировых координатах.

        Returns:
            True если путь найден, False если нет.
        """
        log.info("[NavMeshAgent] set_destination called")
        if self._pathfinding_world is None:
            self._find_pathfinding_world()
            if self._pathfinding_world is None:
                log.warn("[NavMeshAgent] no PathfindingWorld available")
                return False

        if self.entity is None:
            log.warn("[NavMeshAgent] entity is None")
            return False

        # Получаем текущую позицию агента (мировые координаты)
        position = self.entity.transform.global_pose().lin
        start = np.array([position.x, position.y, position.z], dtype=np.float32)
        log.info(f"[NavMeshAgent] agent position: ({position.x:.2f}, {position.y:.2f}, {position.z:.2f})")

        # Ищем путь
        log.info("[NavMeshAgent] calling find_path")
        path = self._pathfinding_world.find_path(start, target)
        log.info(f"[NavMeshAgent] find_path returned: {path}")
        if path is None or len(path) == 0:
            log.info(f"[NavMeshAgent] no path found to ({target[0]:.2f}, {target[1]:.2f}, {target[2]:.2f})")
            self._current_path = []
            self._is_moving = False
            return False

        self._destination = target.copy()
        self._current_path = path
        self._current_path_index = 0
        self._is_moving = True

        log.info(f"[NavMeshAgent] path found with {len(path)} waypoints")
        return True

    def stop(self) -> None:
        """Остановить движение."""
        self._is_moving = False
        self._current_path = []
        self._current_path_index = 0
        self._destination = None

    def update(self, dt: float) -> None:
        """Обновление — движение к следующей точке пути."""
        if not self._is_moving or not self.has_path:
            return

        if self.entity is None:
            return

        # Текущая позиция (мировые координаты)
        position = self.entity.transform.global_pose().lin
        current_pos = np.array([position.x, position.y, position.z], dtype=np.float32)

        # Целевая точка пути
        target = self._current_path[self._current_path_index]

        # Вектор к цели
        direction = target - current_pos
        distance = float(np.linalg.norm(direction))

        if distance < self.stopping_distance:
            # Достигли текущей точки — переходим к следующей
            self._current_path_index += 1

            if self._current_path_index >= len(self._current_path):
                # Достигли конца пути
                log.info("[NavMeshAgent] destination reached")
                self._is_moving = False
                return

            return

        # Нормализуем направление
        direction = direction / distance

        # Двигаемся
        move_distance = min(self.speed * dt, distance)
        new_pos = current_pos + direction * move_distance

        # Обновляем позицию entity (локальные координаты)
        from termin.geombase._geom_native import Vec3
        self.entity.transform.set_local_position(Vec3(new_pos[0], new_pos[1], new_pos[2]))

    def get_path_points(self) -> List[np.ndarray]:
        """Получить все точки текущего пути для отладочной визуализации."""
        return self._current_path.copy()

    def get_remaining_path(self) -> List[np.ndarray]:
        """Получить оставшиеся точки пути."""
        if not self.has_path:
            return []
        return self._current_path[self._current_path_index:]

    def on_mouse_button(self, event: MouseButtonEvent) -> None:
        """Обработка клика мыши — ЛКМ для движения к точке."""
        if not self.click_to_move:
            return

        # Только ЛКМ при нажатии
        if event.button != MouseButton.LEFT or event.action != Action.PRESS:
            return

        if self._pathfinding_world is None:
            self._find_pathfinding_world()
            if self._pathfinding_world is None:
                log.warn("[NavMeshAgent] click ignored - no PathfindingWorld")
                return

        # Получаем луч из позиции курсора
        ray = event.viewport.screen_point_to_ray(event.x, event.y)
        if ray is None:
            log.warn("[NavMeshAgent] click ignored - no ray from viewport")
            return

        # Raycast по NavMesh
        origin = np.array([ray.origin.x, ray.origin.y, ray.origin.z], dtype=np.float32)
        direction = np.array([ray.direction.x, ray.direction.y, ray.direction.z], dtype=np.float32)

        # Нормализуем
        length = float(np.linalg.norm(direction))
        if length > 1e-8:
            direction = direction / length

        hit = self._pathfinding_world.raycast(origin, direction)
        if hit is None:
            log.info("[NavMeshAgent] click missed NavMesh")
            return

        hit_point, distance, region_id, triangle_id = hit
        log.info(f"[NavMeshAgent] click hit NavMesh at ({hit_point[0]:.2f}, {hit_point[1]:.2f}, {hit_point[2]:.2f}), region={region_id}, tri={triangle_id}")
        self.set_destination(hit_point)
