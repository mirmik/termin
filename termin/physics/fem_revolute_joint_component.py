"""FEM Revolute Joint Component — шарнир между двумя телами."""

from __future__ import annotations

from typing import TYPE_CHECKING
import numpy as np

from termin.visualization.core.component import Component
from termin.fem.multibody3d_3 import RevoluteJoint3D
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene
    from termin.visualization.core.entity import Entity
    from termin.physics.fem_physics_world_component import FEMPhysicsWorldComponent
    from termin.physics.fem_rigid_body_component import FEMRigidBodyComponent
    from termin.visualization.render.immediate import ImmediateRenderer


class FEMRevoluteJointComponent(Component):
    """
    Компонент вращательного шарнира для FEM симуляции.

    Соединяет два тела в точке, позволяя им вращаться
    относительно друг друга.

    Позиция entity = точка шарнира.
    body_a_entity_name, body_b_entity_name = имена entity с телами.
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
    }

    def __init__(
        self,
        body_a_entity_name: str = "",
        body_b_entity_name: str = "",
    ):
        super().__init__(enabled=True)

        self.body_a_entity_name = body_a_entity_name
        self.body_b_entity_name = body_b_entity_name

        self._fem_joint: RevoluteJoint3D | None = None
        self._fem_world: "FEMPhysicsWorldComponent | None" = None
        self._body_a_component: "FEMRigidBodyComponent | None" = None
        self._body_b_component: "FEMRigidBodyComponent | None" = None

    @property
    def joint_point(self) -> np.ndarray:
        """Точка шарнира = позиция этого entity."""
        if self.entity is None:
            return np.zeros(3, dtype=np.float64)
        pose = self.entity.transform.global_pose()
        return np.asarray(pose.lin, dtype=np.float64)

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
            print(f"FEMRevoluteJointComponent: body A '{self.body_a_entity_name}' not found")
            return

        self._body_a_component = entity_a.get_component(FEMRigidBodyComponent)
        if self._body_a_component is None:
            print(f"FEMRevoluteJointComponent: entity '{self.body_a_entity_name}' has no FEMRigidBodyComponent")
            return

        # Найти тело B
        entity_b = self._find_entity_by_name(scene, self.body_b_entity_name)
        if entity_b is None:
            print(f"FEMRevoluteJointComponent: body B '{self.body_b_entity_name}' not found")
            return

        self._body_b_component = entity_b.get_component(FEMRigidBodyComponent)
        if self._body_b_component is None:
            print(f"FEMRevoluteJointComponent: entity '{self.body_b_entity_name}' has no FEMRigidBodyComponent")
            return

        fem_body_a = self._body_a_component.fem_body
        fem_body_b = self._body_b_component.fem_body

        if fem_body_a is None or fem_body_b is None:
            print("FEMRevoluteJointComponent: FEM bodies not initialized")
            return

        # Создать joint
        self._fem_joint = RevoluteJoint3D(
            bodyA=fem_body_a,
            bodyB=fem_body_b,
            coords_of_joint=self.joint_point,
            assembler=world.assembler,
        )

    def draw(self, context):
        """Нарисовать линии от шарнира до обоих тел."""
        renderer: "ImmediateRenderer | None" = context.get("immediate_renderer")
        if renderer is None:
            return

        joint_pos = self.joint_point.astype(np.float32)

        # Линия к телу A
        if self._body_a_component is not None and self._body_a_component.entity is not None:
            body_a_pos = np.asarray(
                self._body_a_component.entity.transform.global_pose().lin,
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
