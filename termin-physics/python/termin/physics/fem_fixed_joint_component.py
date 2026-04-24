"""FEM Fixed Joint Component — фиксирует точку тела в пространстве."""

from __future__ import annotations

from typing import TYPE_CHECKING
import numpy as np

from termin.visualization.core.python_component import PythonComponent
from termin.fem.multibody3d_3 import FixedRotationJoint3D
from termin.editor.inspect_field import InspectField
from tcbase import log

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene
    from termin.visualization.core.entity import Entity
    from termin.physics.fem_physics_world_component import FEMPhysicsWorldComponent
    from termin.physics.fem_rigid_body_component import FEMRigidBodyComponent
    from termin.visualization.render.immediate import ImmediateRenderer


class FEMFixedJointComponent(PythonComponent):
    """
    Компонент фиксированного шарнира для FEM симуляции.

    Фиксирует одну точку тела в пространстве, но позволяет телу
    свободно вращаться вокруг этой точки (как маятник).

    Позиция entity = точка крепления (anchor).
    body_entity_name = имя entity с FEMRigidBodyComponent.
    """

    inspect_fields = {
        "body_entity_name": InspectField(
            path="body_entity_name",
            label="Body Entity",
            kind="string",
        ),
        "damping": InspectField(
            path="damping",
            label="Angular Damping",
            kind="float",
            min=0.0,
            step=0.01,
        ),
    }

    def __init__(
        self,
        body_entity_name: str = "",
        damping: float = 0.0,
    ):
        super().__init__(enabled=True)

        self.body_entity_name = body_entity_name
        self.damping = damping

        self._fem_joint: FixedRotationJoint3D | None = None
        self._fem_world: "FEMPhysicsWorldComponent | None" = None
        self._body_component: "FEMRigidBodyComponent | None" = None

    @property
    def anchor_point(self) -> np.ndarray:
        """Точка крепления = позиция этого entity."""
        if self.entity is None:
            return np.zeros(3, dtype=np.float64)
        pose = self.entity.transform.global_pose()
        return np.asarray(pose.lin, dtype=np.float64)

    def _find_body_entity(self, scene: "Scene") -> "Entity | None":
        """Найти entity тела по имени."""
        if not self.body_entity_name:
            return None

        for entity in scene.entities:
            if entity.name == self.body_entity_name:
                return entity

        return None

    def _register_with_fem_world(self, world: "FEMPhysicsWorldComponent", scene: "Scene"):
        """Зарегистрировать joint в FEM мире."""
        self._fem_world = world

        # Найти тело
        body_entity = self._find_body_entity(scene)
        if body_entity is None:
            log.error(f"FEMFixedJointComponent: body entity '{self.body_entity_name}' not found")
            return

        # Найти компонент тела
        from termin.physics.fem_rigid_body_component import FEMRigidBodyComponent

        self._body_component = body_entity.get_component(FEMRigidBodyComponent)
        if self._body_component is None:
            log.error(f"FEMFixedJointComponent: entity '{self.body_entity_name}' has no FEMRigidBodyComponent")
            return

        fem_body = self._body_component.fem_body
        if fem_body is None:
            log.error(f"FEMFixedJointComponent: FEMRigidBodyComponent not initialized")
            return

        # Создать joint
        self._fem_joint = FixedRotationJoint3D(
            body=fem_body,
            coords_of_joint=self.anchor_point,
            assembler=world.assembler,
        )

    def draw(self, context):
        """Нарисовать линию от anchor до тела."""
        if self._body_component is None or self.entity is None:
            return

        body_entity = self._body_component.entity
        if body_entity is None:
            return

        renderer: "ImmediateRenderer | None" = context.get("immediate_renderer")
        if renderer is None:
            return

        anchor = self.anchor_point
        body_pos = np.asarray(body_entity.transform.global_pose().lin, dtype=np.float32)

        # Линия связи
        renderer.line(
            start=anchor.astype(np.float32),
            end=body_pos,
            color=(0.8, 0.8, 0.2, 1.0),  # жёлтая линия
            width=2.0,
        )

        # Маленькая сфера в точке крепления
        renderer.sphere_solid(
            center=anchor.astype(np.float32),
            radius=0.05,
            color=(1.0, 0.5, 0.0, 1.0),  # оранжевая
            segments=8,
        )

    def compute_damping_dissipation(self, dt: float) -> float:
        """
        Вычислить диссипацию энергии за шаг dt.

        Сферический шарнир — сопротивляется угловой скорости тела:
        τ_damp = -c * ω  → P = c * |ω|²
        """
        if self._body_component is None or self._body_component.fem_body is None:
            return 0.0

        omega = self._body_component.fem_body.velocity_var.value[3:6]
        return self.damping * np.dot(omega, omega) * dt
