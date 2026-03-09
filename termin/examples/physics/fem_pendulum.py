"""FEM Physics Pendulum Demo — простой маятник на FEM solver."""

from __future__ import annotations

import numpy as np

from termin.geombase import Pose3
from termin.mesh.mesh import UVSphereMesh
from termin.visualization import (
    Entity,
    MeshDrawable,
    Scene,
    Material,
    VisualizationWorld,
    PerspectiveCameraComponent,
    OrbitCameraController,
)
from termin.visualization.render.components import MeshRenderer, LightComponent
from termin.physics import (
    FEMPhysicsWorldComponent,
    FEMRigidBodyComponent,
    FEMFixedJointComponent,
)


def build_scene(world: VisualizationWorld) -> tuple[Scene, PerspectiveCameraComponent]:
    scene = Scene()

    # --- FEM Physics World ---
    physics_entity = Entity(name="FEM Physics")
    physics_entity.add_component(FEMPhysicsWorldComponent(
        gravity=np.array([0.0, 0.0, -9.81]),
        time_step=0.01,
        substeps=2,
    ))
    scene.add(physics_entity)

    # --- Pendulum Bob ---
    sphere_mesh = UVSphereMesh(radius=0.2, n_meridians=16, n_parallels=12)
    drawable = MeshDrawable(sphere_mesh)
    material = Material(color=np.array([0.3, 0.6, 0.9, 1.0], dtype=np.float32))

    # Начальная позиция: сбоку от точки подвеса
    bob_entity = Entity(
        pose=Pose3(lin=np.array([1.0, 0.0, 0.0])),
        name="Pendulum Bob",
    )
    bob_entity.add_component(MeshRenderer(drawable, material))
    bob_entity.add_component(FEMRigidBodyComponent(
        mass=1.0,
        inertia_diagonal=FEMRigidBodyComponent.inertia_for_sphere(1.0, 0.2),
    ))
    scene.add(bob_entity)

    # --- Fixed Joint (anchor point) ---
    joint_entity = Entity(
        pose=Pose3(lin=np.array([0.0, 0.0, 1.0])),  # точка подвеса выше (по Z)
        name="Fixed Joint",
    )
    joint_entity.add_component(FEMFixedJointComponent(
        body_entity_name="Pendulum Bob",
    ))
    scene.add(joint_entity)

    # --- Light ---
    light_entity = Entity(
        pose=Pose3.from_euler(np.deg2rad(-45), np.deg2rad(-45), 0),
        name="Light",
    )
    light_entity.add_component(LightComponent())
    scene.add(light_entity)

    # --- Camera ---
    camera_entity = Entity(name="Camera")
    camera = PerspectiveCameraComponent()
    camera_entity.add_component(camera)
    orbit = OrbitCameraController()
    orbit.distance = 5.0
    orbit.pitch = -20.0
    camera_entity.add_component(orbit)
    scene.add(camera_entity)

    world.add_scene(scene)
    return scene, camera


def main():
    world = VisualizationWorld()
    scene, camera = build_scene(world)
    window = world.create_window(title="FEM Pendulum Demo")
    window.add_viewport(scene, camera)
    world.run()


if __name__ == "__main__":
    main()
