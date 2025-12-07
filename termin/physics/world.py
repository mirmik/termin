"""Физический мир — симуляция твёрдых тел."""

from __future__ import annotations

from typing import List, Callable
import numpy as np

from termin.physics.rigid_body import RigidBody
from termin.physics.contact import Contact, ContactConstraint


class PhysicsWorld:
    """
    Физический мир для симуляции твёрдых тел.

    Обрабатывает динамику твёрдых тел с обнаружением и откликом на коллизии
    методом Sequential Impulses.
    """

    def __init__(
        self,
        gravity: np.ndarray | None = None,
        iterations: int = 10,
        restitution: float = 0.3,
        friction: float = 0.5,
    ):
        if gravity is None:
            self.gravity = np.array([0, 0, -9.81], dtype=np.float64)
        else:
            self.gravity = np.asarray(gravity, dtype=np.float64)

        self.iterations = iterations
        self.restitution = restitution
        self.friction = friction

        self.bodies: List[RigidBody] = []
        self._contact_constraints: List[ContactConstraint] = []

        # Плоскость земли (z = 0 по умолчанию)
        self.ground_height = 0.0
        self.ground_enabled = True

    def add_body(self, body: RigidBody) -> RigidBody:
        """Добавить твёрдое тело в мир."""
        self.bodies.append(body)
        return body

    def remove_body(self, body: RigidBody):
        """Удалить твёрдое тело из мира."""
        if body in self.bodies:
            self.bodies.remove(body)

    def step(self, dt: float):
        """
        Продвинуть симуляцию на dt секунд.

        Использует полу-неявный Эйлер со спекулятивными контактами:
        1. Приложение сил → обновление скоростей
        2. Интегрирование позиций (предварительное)
        3. Обнаружение коллизий в новых позициях
        4. Решение скоростных ограничений (Sequential Impulses)
        5. Коррекция позиций
        """
        # 1. Интегрирование сил (гравитация, внешние силы)
        for body in self.bodies:
            body.integrate_forces(dt, self.gravity)

        # 2. Сначала интегрируем позиции (предварительно)
        for body in self.bodies:
            body.integrate_positions(dt)

        # 3. Обнаружение коллизий в новых позициях
        contacts = self._detect_collisions()

        # 4. Создание контактных ограничений
        self._contact_constraints = [
            ContactConstraint(
                contact=c,
                restitution=self.restitution,
                friction=self.friction,
            )
            for c in contacts
        ]

        # 5. Решение скоростей (Sequential Impulses)
        for _ in range(self.iterations):
            for constraint in self._contact_constraints:
                constraint.solve_normal(dt)
                constraint.solve_friction()

        # 6. Коррекция позиций (раздвигаем тела)
        self._solve_position_constraints()

    def _detect_collisions(self) -> List[Contact]:
        """Обнаружить коллизии между всеми телами и землёй."""
        contacts = []

        # Коллизии с землёй
        if self.ground_enabled:
            for body in self.bodies:
                if body.is_static:
                    continue

                ground_contacts = self._detect_ground_collision(body)
                contacts.extend(ground_contacts)

        # Коллизии между телами
        for i, body_a in enumerate(self.bodies):
            for body_b in self.bodies[i + 1:]:
                if body_a.is_static and body_b.is_static:
                    continue

                pair_contacts = self._detect_body_collision(body_a, body_b)
                contacts.extend(pair_contacts)

        return contacts

    def _detect_ground_collision(self, body: RigidBody) -> List[Contact]:
        """Обнаружить коллизию тела с плоскостью земли."""
        contacts = []

        collider = body.world_collider()
        if collider is None:
            # Простая сферическая аппроксимация для тел без коллайдера
            z = body.position[2]
            if z < self.ground_height:
                contacts.append(Contact(
                    body_a=None,
                    body_b=body,
                    point=np.array([body.position[0], body.position[1], self.ground_height]),
                    normal=np.array([0, 0, 1], dtype=np.float64),
                    penetration=self.ground_height - z,
                ))
            return contacts

        # Используем коллайдер для обнаружения коллизий
        from termin.colliders.box import BoxCollider
        from termin.colliders.sphere import SphereCollider

        if isinstance(collider, SphereCollider):
            # Сфера vs земля
            center = collider.center
            radius = collider.radius
            z = center[2]

            if z - radius < self.ground_height:
                contact_point = np.array([center[0], center[1], self.ground_height])
                penetration = self.ground_height - (z - radius)
                contacts.append(Contact(
                    body_a=None,
                    body_b=body,
                    point=contact_point,
                    normal=np.array([0, 0, 1], dtype=np.float64),
                    penetration=penetration,
                ))

        elif isinstance(collider, BoxCollider):
            # Кубоид vs земля — проверяем все 8 вершин
            aabb = collider.local_aabb()
            corners_local = [
                np.array([aabb.min_point[0], aabb.min_point[1], aabb.min_point[2]]),
                np.array([aabb.max_point[0], aabb.min_point[1], aabb.min_point[2]]),
                np.array([aabb.min_point[0], aabb.max_point[1], aabb.min_point[2]]),
                np.array([aabb.max_point[0], aabb.max_point[1], aabb.min_point[2]]),
                np.array([aabb.min_point[0], aabb.min_point[1], aabb.max_point[2]]),
                np.array([aabb.max_point[0], aabb.min_point[1], aabb.max_point[2]]),
                np.array([aabb.min_point[0], aabb.max_point[1], aabb.max_point[2]]),
                np.array([aabb.max_point[0], aabb.max_point[1], aabb.max_point[2]]),
            ]

            for corner_local in corners_local:
                corner_world = collider.pose.transform_point(corner_local)
                z = corner_world[2]

                if z < self.ground_height:
                    contact_point = np.array([
                        corner_world[0],
                        corner_world[1],
                        self.ground_height,
                    ], dtype=np.float64)
                    penetration = self.ground_height - z

                    contacts.append(Contact(
                        body_a=None,
                        body_b=body,
                        point=contact_point,
                        normal=np.array([0, 0, 1], dtype=np.float64),
                        penetration=penetration,
                    ))

        return contacts

    def _detect_body_collision(
        self, body_a: RigidBody, body_b: RigidBody
    ) -> List[Contact]:
        """Обнаружить коллизию между двумя телами."""
        contacts = []

        collider_a = body_a.world_collider()
        collider_b = body_b.world_collider()

        if collider_a is None or collider_b is None:
            return contacts

        # Используем closest_to_collider для обнаружения коллизий
        try:
            p_a, p_b, distance = collider_a.closest_to_collider(collider_b)

            # Отрицательное расстояние означает пенетрацию (из SAT)
            if distance <= 0.01:  # Порог контакта
                if distance < 0:
                    # Пенетрация — для Box-Box SAT:
                    # p_a = нормаль контакта (от A к B)
                    # p_b = точка контакта
                    penetration = -distance
                    normal = np.asarray(p_a, dtype=np.float64)
                    contact_point = np.asarray(p_b, dtype=np.float64)
                else:
                    # Близко, но не пенетрируют
                    diff = p_b - p_a
                    dist = np.linalg.norm(diff)
                    if dist > 1e-8:
                        normal = diff / dist
                    else:
                        normal = np.array([0, 0, 1], dtype=np.float64)
                    contact_point = (p_a + p_b) / 2
                    penetration = max(0, 0.01 - distance)

                contacts.append(Contact(
                    body_a=body_a,
                    body_b=body_b,
                    point=contact_point,
                    normal=normal,
                    penetration=penetration,
                ))
        except NotImplementedError:
            # Обнаружение коллизий не реализовано для этой пары
            pass

        return contacts

    def ray_cast(
        self,
        origin: np.ndarray,
        direction: np.ndarray,
        max_distance: float = 1000.0,
    ) -> tuple[RigidBody | None, np.ndarray | None, float]:
        """
        Бросить луч и вернуть первое пересечённое тело.

        Возвращает:
            (body, hit_point, distance) или (None, None, inf) если нет попадания
        """
        from termin.geombase.ray import Ray3

        ray = Ray3(origin, direction)
        best_body = None
        best_point = None
        best_dist = max_distance

        for body in self.bodies:
            collider = body.world_collider()
            if collider is None:
                continue

            try:
                p_col, p_ray, dist = collider.closest_to_ray(ray)
                t = np.dot(p_ray - origin, direction)

                if 0 < t < best_dist and dist < 0.01:
                    best_dist = t
                    best_body = body
                    best_point = p_col
            except (NotImplementedError, AttributeError):
                pass

        return best_body, best_point, best_dist

    def _solve_position_constraints(self):
        """
        Прямая коррекция позиций для разрешения пенетрации.

        Простой подход: раздвигаем тела вдоль нормали контакта
        пропорционально глубине пенетрации.
        """
        # Повторно обнаруживаем коллизии после интегрирования позиций
        contacts = self._detect_collisions()

        for contact in contacts:
            if contact.penetration <= 0.001:
                continue

            n = contact.normal
            correction = contact.penetration * 0.8  # 80% коррекция

            if contact.body_a is None:
                # Контакт с землёй — двигаем только body_b
                if not contact.body_b.is_static:
                    contact.body_b.position = contact.body_b.position + n * correction
            else:
                # Контакт между телами
                total_inv_mass = 0.0
                if not contact.body_a.is_static:
                    total_inv_mass += contact.body_a.inv_mass
                if not contact.body_b.is_static:
                    total_inv_mass += contact.body_b.inv_mass

                if total_inv_mass > 1e-10:
                    if not contact.body_a.is_static:
                        ratio_a = contact.body_a.inv_mass / total_inv_mass
                        contact.body_a.position = contact.body_a.position - n * correction * ratio_a
                    if not contact.body_b.is_static:
                        ratio_b = contact.body_b.inv_mass / total_inv_mass
                        contact.body_b.position = contact.body_b.position + n * correction * ratio_b
