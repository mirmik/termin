"""Обнаружение контактов и решение ограничений."""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from termin.physics.rigid_body import RigidBody


@dataclass
class Contact:
    """
    Точка контакта между двумя твёрдыми телами.

    Атрибуты:
        body_a: Первое тело (может быть None для контакта с землёй)
        body_b: Второе тело
        point: Точка контакта в мировых координатах
        normal: Нормаль контакта (направлена от A к B, или вверх для земли)
        penetration: Глубина проникновения (положительная = пересечение)
    """
    body_a: RigidBody | None
    body_b: RigidBody
    point: np.ndarray
    normal: np.ndarray
    penetration: float

    # Для warm starting (накопленный импульс с предыдущего кадра)
    accumulated_normal_impulse: float = 0.0
    accumulated_tangent_impulse: np.ndarray = None

    def __post_init__(self):
        if self.accumulated_tangent_impulse is None:
            self.accumulated_tangent_impulse = np.zeros(2, dtype=np.float64)


class ContactConstraint:
    """
    Решатель контактных ограничений методом Sequential Impulses.
    """

    def __init__(
        self,
        contact: Contact,
        restitution: float = 0.3,
        friction: float = 0.5,
        baumgarte: float = 0.2,
        slop: float = 0.005,
    ):
        self.contact = contact
        self.restitution = restitution
        self.friction = friction
        self.baumgarte = baumgarte
        self.slop = slop

        # Предвычисление данных ограничения
        self._precompute()

        # Сохраняем начальную скорость сближения для реституции (вычисляется один раз)
        self._initial_v_n = None

    def _precompute(self):
        """Предвычисление эффективной массы и смещения."""
        c = self.contact
        n = c.normal

        # Вычисление эффективной массы для нормального импульса
        # w = 1/m_a + 1/m_b + n·(I_a^{-1} @ (r_a×n))×r_a + n·(I_b^{-1} @ (r_b×n))×r_b

        w = 0.0

        if c.body_a is not None and not c.body_a.is_static:
            r_a = c.point - c.body_a.position
            rxn_a = np.cross(r_a, n)
            w += c.body_a.inv_mass
            w += np.dot(n, np.cross(c.body_a.world_inertia_inv() @ rxn_a, r_a))

        if c.body_b is not None and not c.body_b.is_static:
            r_b = c.point - c.body_b.position
            rxn_b = np.cross(r_b, n)
            w += c.body_b.inv_mass
            w += np.dot(n, np.cross(c.body_b.world_inertia_inv() @ rxn_b, r_b))

        self.effective_mass_normal = 1.0 / w if w > 1e-10 else 0.0

        # Вычисление касательных направлений для трения
        # Находим два ортогональных касательных вектора
        if abs(n[0]) < 0.9:
            t1 = np.cross(n, np.array([1, 0, 0], dtype=np.float64))
        else:
            t1 = np.cross(n, np.array([0, 1, 0], dtype=np.float64))
        t1 = t1 / np.linalg.norm(t1)
        t2 = np.cross(n, t1)

        self.tangent1 = t1
        self.tangent2 = t2

        # Эффективная масса для касательных импульсов
        self.effective_mass_tangent1 = self._compute_effective_mass(t1)
        self.effective_mass_tangent2 = self._compute_effective_mass(t2)

    def _compute_effective_mass(self, direction: np.ndarray) -> float:
        """Вычисление эффективной массы в заданном направлении."""
        c = self.contact
        w = 0.0

        if c.body_a is not None and not c.body_a.is_static:
            r_a = c.point - c.body_a.position
            rxd_a = np.cross(r_a, direction)
            w += c.body_a.inv_mass
            w += np.dot(direction, np.cross(c.body_a.world_inertia_inv() @ rxd_a, r_a))

        if c.body_b is not None and not c.body_b.is_static:
            r_b = c.point - c.body_b.position
            rxd_b = np.cross(r_b, direction)
            w += c.body_b.inv_mass
            w += np.dot(direction, np.cross(c.body_b.world_inertia_inv() @ rxd_b, r_b))

        return 1.0 / w if w > 1e-10 else 0.0

    def relative_velocity(self) -> np.ndarray:
        """Вычисление относительной скорости в точке контакта (v_b - v_a)."""
        c = self.contact

        v_b = np.zeros(3, dtype=np.float64)
        if c.body_b is not None:
            v_b = c.body_b.point_velocity(c.point)

        v_a = np.zeros(3, dtype=np.float64)
        if c.body_a is not None:
            v_a = c.body_a.point_velocity(c.point)

        return v_b - v_a

    def solve_normal(self, dt: float):
        """Решение нормального ограничения (непроникновение)."""
        c = self.contact
        n = c.normal

        # Относительная скорость вдоль нормали (положительная = расхождение, отрицательная = сближение)
        v_rel = self.relative_velocity()
        v_n = np.dot(v_rel, n)

        # Сохраняем начальную скорость сближения для реституции (только один раз)
        if self._initial_v_n is None:
            self._initial_v_n = v_n

        # Целевая скорость: хотим v_n >= 0 (непроникновение)
        # Для покоящегося контакта: v_n = 0
        # Для отскока: v_n = -restitution * initial_v_n

        target_v_n = 0.0

        # Применяем реституцию только при первом ударе (когда быстро сближаемся)
        if self._initial_v_n < -1.0:
            target_v_n = -self.restitution * self._initial_v_n

        # Вычисляем импульс для достижения целевой скорости
        # impulse = m_eff * (target_v_n - v_n)
        impulse = self.effective_mass_normal * (target_v_n - v_n)

        # Ограничиваем накопленный импульс (контакт может только толкать, не тянуть)
        old_accumulated = c.accumulated_normal_impulse
        c.accumulated_normal_impulse = max(0.0, old_accumulated + impulse)
        impulse = c.accumulated_normal_impulse - old_accumulated

        # Применяем импульс
        impulse_vec = n * impulse
        self._apply_impulse(impulse_vec)

    def solve_friction(self):
        """Решение касательных ограничений (трение)."""
        c = self.contact

        # Максимальный импульс трения (кулоновское трение)
        max_friction = self.friction * c.accumulated_normal_impulse

        # Решаем tangent1
        v_rel = self.relative_velocity()
        v_t1 = np.dot(v_rel, self.tangent1)
        impulse_t1 = self.effective_mass_tangent1 * (-v_t1)

        old_t1 = c.accumulated_tangent_impulse[0]
        c.accumulated_tangent_impulse[0] = np.clip(
            old_t1 + impulse_t1, -max_friction, max_friction
        )
        impulse_t1 = c.accumulated_tangent_impulse[0] - old_t1

        # Решаем tangent2
        v_rel = self.relative_velocity()
        v_t2 = np.dot(v_rel, self.tangent2)
        impulse_t2 = self.effective_mass_tangent2 * (-v_t2)

        old_t2 = c.accumulated_tangent_impulse[1]
        c.accumulated_tangent_impulse[1] = np.clip(
            old_t2 + impulse_t2, -max_friction, max_friction
        )
        impulse_t2 = c.accumulated_tangent_impulse[1] - old_t2

        # Применяем импульсы трения
        impulse_vec = self.tangent1 * impulse_t1 + self.tangent2 * impulse_t2
        self._apply_impulse(impulse_vec)

    def _apply_impulse(self, impulse: np.ndarray):
        """Применить импульс к обоим телам."""
        c = self.contact

        if c.body_a is not None and not c.body_a.is_static:
            c.body_a.apply_impulse(-impulse, c.point)

        if c.body_b is not None and not c.body_b.is_static:
            c.body_b.apply_impulse(impulse, c.point)
