"""FEM Physics World Component — управляет FEM симуляцией для сцены."""

from __future__ import annotations

from typing import TYPE_CHECKING, List
import numpy as np

from termin.visualization.core.python_component import PythonComponent
from termin.fem.dynamic_assembler import DynamicMatrixAssembler
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.physics.fem_rigid_body_component import FEMRigidBodyComponent
    from termin.physics.fem_fixed_joint_component import FEMFixedJointComponent
    from termin.physics.fem_revolute_joint_component import FEMRevoluteJointComponent


class FEMPhysicsWorldComponent(PythonComponent):
    """
    Компонент, управляющий FEM физической симуляцией.

    Использует Python FEM solver для точной симуляции
    многотельных систем с ограничениями.

    Прикрепите к любой сущности в сцене. Он будет:
    1. Собирать все FEMRigidBodyComponent и FEMJointComponent
    2. Выполнять FEM симуляцию каждый кадр
    3. Синхронизировать трансформы обратно в сущности
    """

    inspect_fields = {
        "gravity": InspectField(
            path="gravity",
            label="Gravity",
            kind="vec3",
        ),
        "time_step": InspectField(
            path="time_step",
            label="Time Step",
            kind="float",
            min=0.001,
            max=0.1,
            step=0.001,
        ),
        "substeps": InspectField(
            path="substeps",
            label="Substeps",
            kind="int",
            min=1,
            max=20,
        ),
        "energy_stabilization": InspectField(
            path="energy_stabilization",
            label="Energy Stabilization",
            kind="bool",
        ),
        "strict_energy_mode": InspectField(
            path="strict_energy_mode",
            label="Strict Energy Mode",
            kind="bool",
        ),
    }

    def __init__(
        self,
        gravity: np.ndarray | None = None,
        time_step: float = 0.01,
        substeps: int = 1,
        energy_stabilization: bool = True,
        strict_energy_mode: bool = False,
    ):
        super().__init__(enabled=True)

        if gravity is None:
            gravity = np.array([0.0, 0.0, -9.81], dtype=np.float64)

        self.gravity = np.asarray(gravity, dtype=np.float64)
        self.time_step = time_step
        self.substeps = substeps
        self.energy_stabilization = energy_stabilization
        self.strict_energy_mode = strict_energy_mode

        self._assembler: DynamicMatrixAssembler | None = None
        self._bodies: List["FEMRigidBodyComponent"] = []
        self._fixed_joints: List["FEMFixedJointComponent"] = []
        self._revolute_joints: List["FEMRevoluteJointComponent"] = []
        self._initialized = False
        self._accumulated_time = 0.0
        self._target_energy: float | None = None

    @property
    def assembler(self) -> DynamicMatrixAssembler | None:
        return self._assembler

    def start(self):
        super().start()
        self._scene = self.entity.scene if self.entity else None
        self._rebuild_simulation()
        self._initialized = True

    def _rebuild_simulation(self):
        """Пересобрать симуляцию: создать assembler и зарегистрировать все тела/joints."""
        self._assembler = DynamicMatrixAssembler()
        self._assembler.time_step = self.time_step

        self._bodies.clear()
        self._fixed_joints.clear()
        self._revolute_joints.clear()

        # Собрать все компоненты
        visited = set()
        if self._scene:
            for entity in self._scene.get_all_entities():
                self._collect_from_entity(entity, visited)

        # Инициализировать тела
        for body_comp in self._bodies:
            body_comp._register_with_fem_world(self)

        # Инициализировать joints (после тел, т.к. им нужны ссылки на тела)
        for joint_comp in self._fixed_joints:
            joint_comp._register_with_fem_world(self, self._scene)

        for joint_comp in self._revolute_joints:
            joint_comp._register_with_fem_world(self, self._scene)

    def _collect_from_entity(self, entity, visited: set):
        """Рекурсивно собрать FEM компоненты из дерева сущностей."""
        from termin.physics.fem_rigid_body_component import FEMRigidBodyComponent
        from termin.physics.fem_fixed_joint_component import FEMFixedJointComponent
        from termin.physics.fem_revolute_joint_component import FEMRevoluteJointComponent

        entity_id = id(entity)
        if entity_id in visited:
            return
        visited.add(entity_id)

        # Тела
        body_comp = entity.get_component(FEMRigidBodyComponent)
        if body_comp is not None:
            self._bodies.append(body_comp)

        # Fixed joints
        fixed_joint = entity.get_component(FEMFixedJointComponent)
        if fixed_joint is not None:
            self._fixed_joints.append(fixed_joint)

        # Revolute joints
        revolute_joint = entity.get_component(FEMRevoluteJointComponent)
        if revolute_joint is not None:
            self._revolute_joints.append(revolute_joint)

        # Дочерние
        for child_transform in entity.transform.children:
            if child_transform.entity is not None:
                self._collect_from_entity(child_transform.entity, visited)

    def update(self, dt: float):
        """Шаг физики и синхронизация трансформов."""
        if not self._initialized or not self.enabled:
            return

        if self._assembler is None or len(self._bodies) == 0:
            return

        # Накапливаем время и делаем фиксированные шаги
        self._accumulated_time += dt
        step_dt = self.time_step / self.substeps

        while self._accumulated_time >= step_dt:
            self._step_simulation(step_dt)
            self._accumulated_time -= step_dt

    def _step_simulation(self, dt: float):
        """Один шаг FEM симуляции."""
        self._assembler.time_step = dt

        # 1. Собрать систему
        matrices = self._assembler.assemble()

        # 2. Построить расширенную систему (с ограничениями)
        A_ext, b_ext, variables = self._assembler.assemble_extended_system(matrices)

        # 3. Решить систему
        try:
            x_ext = np.linalg.solve(A_ext, b_ext)
        except np.linalg.LinAlgError:
            # Сингулярная матрица — пропускаем шаг
            return

        # 4. Разделить на ускорения и множители Лагранжа
        q_ddot, _, _ = self._assembler.sort_results(x_ext)

        # 5. Интегрировать с коррекцией ограничений
        self._assembler.integrate_with_constraint_projection(q_ddot, matrices)

        # 6. Стабилизация энергии (предотвращает численный рост)
        if self.energy_stabilization:
            self._stabilize_energy()

        # 7. Синхронизировать результаты обратно в entity transforms
        for body_comp in self._bodies:
            body_comp._sync_from_physics()

    def _compute_total_energy(self) -> float:
        """Вычислить полную механическую энергию системы."""
        total_energy = 0.0

        for body_comp in self._bodies:
            fem_body = body_comp.fem_body
            if fem_body is None:
                continue

            # Кинетическая энергия
            v = fem_body.velocity_var.value
            v_lin = v[0:3]
            omega = v[3:6]

            mass = fem_body.inertia.mass
            I_diag = fem_body.inertia.I_diag

            T_lin = 0.5 * mass * np.dot(v_lin, v_lin)
            T_rot = 0.5 * np.dot(omega * I_diag, omega)

            # Потенциальная энергия (гравитация)
            pos = fem_body.pose().lin
            g = self.gravity
            U = -mass * np.dot(g, pos)

            total_energy += T_lin + T_rot + U

        return total_energy

    def _compute_total_damping_dissipation(self, dt: float) -> float:
        """Вычислить суммарную диссипацию энергии от всех источников демпфирования."""
        total = 0.0

        # Демпфирование тел (сопротивление среды)
        for body_comp in self._bodies:
            total += body_comp.compute_damping_dissipation(dt)

        # Демпфирование fixed joints
        for joint_comp in self._fixed_joints:
            total += joint_comp.compute_damping_dissipation(dt)

        # Демпфирование revolute joints
        for joint_comp in self._revolute_joints:
            total += joint_comp.compute_damping_dissipation(dt)

        return total

    def _stabilize_energy(self):
        """Масштабировать скорости для стабилизации энергии."""
        current_energy = self._compute_total_energy()
        dt = self._assembler.time_step

        # Вычислить ожидаемую диссипацию от демпфирования
        damping_loss = self._compute_total_damping_dissipation(dt)

        # Инициализация целевой энергии на первом шаге
        if self._target_energy is None:
            self._target_energy = current_energy
            return

        # Уменьшить целевую энергию на величину диссипации
        self._target_energy = max(self._target_energy - damping_loss, 0.0)

        # Вычисляем кинетическую энергию
        kinetic_energy = self._compute_kinetic_energy()

        if kinetic_energy < 1e-10:
            return

        # Разница энергий: положительная = избыток, отрицательная = недостаток
        energy_diff = current_energy - self._target_energy

        # Определяем, нужна ли коррекция
        if self.strict_energy_mode:
            # Строгий режим: корректируем в обе стороны
            needs_correction = abs(energy_diff) > 1e-10
        else:
            # Обычный режим: корректируем только избыток
            needs_correction = energy_diff > 1e-10

        if needs_correction:
            # Новая кинетическая энергия = kinetic - diff
            # (diff > 0: уменьшаем, diff < 0: увеличиваем)
            new_kinetic = kinetic_energy - energy_diff

            # Ограничиваем снизу нулём
            if new_kinetic < 0.0:
                new_kinetic = 0.0

            # Коэффициент масштабирования скоростей
            scale = np.sqrt(new_kinetic / kinetic_energy)

            # Применяем масштабирование ко всем телам
            for body_comp in self._bodies:
                fem_body = body_comp.fem_body
                if fem_body is not None:
                    fem_body.velocity_var.value *= scale

    def _compute_kinetic_energy(self) -> float:
        """Вычислить суммарную кинетическую энергию системы."""
        kinetic_energy = 0.0
        for body_comp in self._bodies:
            fem_body = body_comp.fem_body
            if fem_body is None:
                continue
            v = fem_body.velocity_var.value
            v_lin = v[0:3]
            omega = v[3:6]
            mass = fem_body.inertia.mass
            I_diag = fem_body.inertia.I_diag
            kinetic_energy += 0.5 * mass * np.dot(v_lin, v_lin)
            kinetic_energy += 0.5 * np.dot(omega * I_diag, omega)
        return kinetic_energy

    def get_body_by_entity(self, entity) -> "FEMRigidBodyComponent | None":
        """Найти FEMRigidBodyComponent для заданного entity."""
        for body_comp in self._bodies:
            if body_comp.entity is entity:
                return body_comp
        return None
