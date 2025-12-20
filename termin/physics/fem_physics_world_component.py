"""FEM Physics World Component — управляет FEM симуляцией для сцены."""

from __future__ import annotations

from typing import TYPE_CHECKING, List
import numpy as np

from termin.visualization.core.component import Component
from termin.fem.dynamic_assembler import DynamicMatrixAssembler
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene
    from termin.physics.fem_rigid_body_component import FEMRigidBodyComponent
    from termin.physics.fem_fixed_joint_component import FEMFixedJointComponent
    from termin.physics.fem_revolute_joint_component import FEMRevoluteJointComponent


class FEMPhysicsWorldComponent(Component):
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
    }

    def __init__(
        self,
        gravity: np.ndarray | None = None,
        time_step: float = 0.01,
        substeps: int = 1,
    ):
        super().__init__(enabled=True)

        if gravity is None:
            gravity = np.array([0.0, 0.0, -9.81], dtype=np.float64)

        self.gravity = np.asarray(gravity, dtype=np.float64)
        self.time_step = time_step
        self.substeps = substeps

        self._assembler: DynamicMatrixAssembler | None = None
        self._bodies: List["FEMRigidBodyComponent"] = []
        self._fixed_joints: List["FEMFixedJointComponent"] = []
        self._revolute_joints: List["FEMRevoluteJointComponent"] = []
        self._initialized = False
        self._accumulated_time = 0.0

    @property
    def assembler(self) -> DynamicMatrixAssembler | None:
        return self._assembler

    def start(self, scene: "Scene"):
        super().start(scene)
        self._scene = scene
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
        for entity in self._scene.entities:
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

        # 6. Синхронизировать результаты обратно в entity transforms
        for body_comp in self._bodies:
            body_comp._sync_from_physics()

    def get_body_by_entity(self, entity) -> "FEMRigidBodyComponent | None":
        """Найти FEMRigidBodyComponent для заданного entity."""
        for body_comp in self._bodies:
            if body_comp.entity is entity:
                return body_comp
        return None
