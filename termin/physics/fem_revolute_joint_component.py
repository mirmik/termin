"""FEM Revolute Joint Component — шарнир между двумя телами."""

from __future__ import annotations

from typing import TYPE_CHECKING
import numpy as np

from termin.visualization.core.python_component import PythonComponent
from termin.fem.multibody3d_3 import RevoluteJoint3D
from termin.editor.inspect_field import InspectField
from termin._native import log

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene
    from termin.visualization.core.entity import Entity
    from termin.physics.fem_physics_world_component import FEMPhysicsWorldComponent
    from termin.physics.fem_rigid_body_component import FEMRigidBodyComponent
    from termin.visualization.render.immediate import ImmediateRenderer


class FEMRevoluteJointComponent(PythonComponent):
    """
    Компонент вращательного шарнира для FEM симуляции.

    Соединяет два тела в точке, позволяя им вращаться
    относительно друг друга.

    Точка шарнира задаётся смещением в локальной СК тела A.
    Позиция самого entity игнорируется.
    """

    inspect_fields = {
        "body_a_entity_name": InspectField(
            path="body_a_entity_name",
            label="Body A",
            kind="string",
        ),
        "body_b_entity_name": InspectField(
            path="body_b_entity_name",
            label="Body B",
            kind="string",
        ),
        "joint_offset_in_body_a": InspectField(
            path="joint_offset_in_body_a",
            label="Joint Offset (in Body A)",
            kind="vec3",
        ),
        "damping": InspectField(
            path="damping",
            label="Damping",
            kind="float",
            min=0.0,
            step=0.01,
        ),
    }

    def __init__(
        self,
        body_a_entity_name: str = "",
        body_b_entity_name: str = "",
        joint_offset_in_body_a: np.ndarray | None = None,
        damping: float = 0.0,
    ):
        super().__init__(enabled=True)

        self.body_a_entity_name = body_a_entity_name
        self.body_b_entity_name = body_b_entity_name
        self.damping = damping

        if joint_offset_in_body_a is None:
            joint_offset_in_body_a = np.zeros(3, dtype=np.float64)
        self.joint_offset_in_body_a = np.asarray(joint_offset_in_body_a, dtype=np.float64)

        self._fem_joint: RevoluteJoint3D | None = None
        self._fem_world: "FEMPhysicsWorldComponent | None" = None
        self._body_a_component: "FEMRigidBodyComponent | None" = None
        self._body_b_component: "FEMRigidBodyComponent | None" = None

    def _compute_joint_point(self, entity_a: "Entity") -> np.ndarray:
        """Вычислить точку шарнира в мировых координатах."""
        pose_a = entity_a.transform.global_pose()
        # Преобразуем локальное смещение в мировые координаты
        return np.asarray(pose_a.transform_point(self.joint_offset_in_body_a), dtype=np.float64)

    def _find_entity_by_name(self, scene: "Scene", name: str) -> "Entity | None":
        """Найти entity по имени."""
        if not name:
            return None
        for entity in scene.entities:
            if entity.name == name:
                return entity
        return None

    def _register_with_fem_world(self, world: "FEMPhysicsWorldComponent", scene: "Scene"):
        """Зарегистрировать joint в FEM мире."""
        from termin.physics.fem_rigid_body_component import FEMRigidBodyComponent

        self._fem_world = world

        # Найти тело A
        entity_a = self._find_entity_by_name(scene, self.body_a_entity_name)
        if entity_a is None:
            log.error(f"FEMRevoluteJointComponent: body A '{self.body_a_entity_name}' not found")
            return

        self._body_a_component = entity_a.get_component(FEMRigidBodyComponent)
        if self._body_a_component is None:
            log.error(f"FEMRevoluteJointComponent: entity '{self.body_a_entity_name}' has no FEMRigidBodyComponent")
            return

        # Найти тело B
        entity_b = self._find_entity_by_name(scene, self.body_b_entity_name)
        if entity_b is None:
            log.error(f"FEMRevoluteJointComponent: body B '{self.body_b_entity_name}' not found")
            return

        self._body_b_component = entity_b.get_component(FEMRigidBodyComponent)
        if self._body_b_component is None:
            log.error(f"FEMRevoluteJointComponent: entity '{self.body_b_entity_name}' has no FEMRigidBodyComponent")
            return

        fem_body_a = self._body_a_component.fem_body
        fem_body_b = self._body_b_component.fem_body

        if fem_body_a is None or fem_body_b is None:
            log.error("FEMRevoluteJointComponent: FEM bodies not initialized")
            return

        # Вычислить точку шарнира из позиции тела A и смещения
        joint_point = self._compute_joint_point(entity_a)

        # Создать joint
        self._fem_joint = RevoluteJoint3D(
            bodyA=fem_body_a,
            bodyB=fem_body_b,
            coords_of_joint=joint_point,
            assembler=world.assembler,
        )

    def draw(self, context):
        """Нарисовать линии от шарнира до обоих тел."""
        renderer: "ImmediateRenderer | None" = context.get("immediate_renderer")
        if renderer is None:
            return

        # Вычисляем точку шарнира из позиции тела A
        if self._body_a_component is None or self._body_a_component.entity is None:
            return

        entity_a = self._body_a_component.entity
        joint_pos = self._compute_joint_point(entity_a).astype(np.float32)

        # Линия к телу A
        body_a_pos = np.asarray(
            entity_a.transform.global_pose().lin,
            dtype=np.float32
        )
        renderer.line(
            start=joint_pos,
            end=body_a_pos,
            color=(0.2, 0.8, 0.8, 1.0),  # cyan
            width=2.0,
        )

        # Линия к телу B
        if self._body_b_component is not None and self._body_b_component.entity is not None:
            body_b_pos = np.asarray(
                self._body_b_component.entity.transform.global_pose().lin,
                dtype=np.float32
            )
            renderer.line(
                start=joint_pos,
                end=body_b_pos,
                color=(0.8, 0.2, 0.8, 1.0),  # magenta
                width=2.0,
            )

        # Сфера в точке шарнира
        renderer.sphere_solid(
            center=joint_pos,
            radius=0.05,
            color=(0.2, 0.8, 0.2, 1.0),  # green
            segments=8,
        )

    def compute_damping_dissipation(self, dt: float) -> float:
        """
        Вычислить диссипацию энергии за шаг dt.

        Шарнир сопротивляется относительной угловой скорости:
        ω_rel = ω_A - ω_B
        τ_damp = -c * ω_rel  → P = c * |ω_rel|²
        """
        if self._body_a_component is None or self._body_b_component is None:
            return 0.0

        fem_body_a = self._body_a_component.fem_body
        fem_body_b = self._body_b_component.fem_body

        if fem_body_a is None or fem_body_b is None:
            return 0.0

        omega_a = fem_body_a.velocity_var.value[3:6]
        omega_b = fem_body_b.velocity_var.value[3:6]
        omega_rel = omega_a - omega_b

        return self.damping * np.dot(omega_rel, omega_rel) * dt
