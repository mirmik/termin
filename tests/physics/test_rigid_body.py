"""Тесты физического движка: падение кубиков на плоскость."""

import math
import numpy as np
from termin.geombase.pose3 import Pose3
from termin.physics import RigidBody, PhysicsWorld


def test_drop_cube():
    """Тест: падение кубика и отскок от земли."""
    world = PhysicsWorld(
        gravity=np.array([0, 0, -9.81]),
        iterations=10,
        restitution=0.5,
        friction=0.3,
    )

    # Кубик на высоте 2
    cube = RigidBody.create_box(
        size=(1, 1, 1),
        mass=1.0,
        pose=Pose3.identity().with_translation(np.array([0, 0, 2.0])),
    )
    world.add_body(cube)

    # Симуляция 2 секунды
    dt = 1.0 / 60.0
    for _ in range(120):
        world.step(dt)

    # Кубик должен лежать на земле (z ≈ 0.5 для единичного кубика)
    assert cube.position[2] < 1.0, "Кубик должен упасть"
    assert cube.position[2] > 0.4, "Кубик должен лежать на земле"
    assert abs(cube.velocity.lin[2]) < 0.5, "Кубик должен быть в покое"


def test_tilted_cube():
    """Тест: падение наклонённого кубика."""
    world = PhysicsWorld(
        gravity=np.array([0, 0, -9.81]),
        iterations=20,
        restitution=0.3,
        friction=0.5,
    )

    # Кубик наклонён на 30 градусов вокруг оси X
    angle = math.radians(30)
    quat = np.array([
        math.sin(angle / 2), 0, 0, math.cos(angle / 2)
    ])
    pose = Pose3(ang=quat, lin=np.array([0, 0, 2.0]))

    cube = RigidBody.create_box(
        size=(1, 1, 1),
        mass=1.0,
        pose=pose,
    )
    world.add_body(cube)

    # Симуляция 3 секунды
    dt = 1.0 / 60.0
    for _ in range(180):
        world.step(dt)

    # Кубик должен упасть и успокоиться
    assert cube.position[2] < 1.0, "Кубик должен упасть"
    assert cube.position[2] > 0.4, "Кубик должен лежать на земле"


def test_box_box_collision():
    """Тест: столкновение двух кубиков."""
    world = PhysicsWorld(
        gravity=np.array([0, 0, -9.81]),
        iterations=10,
        restitution=0.2,
        friction=0.5,
    )

    # Нижний кубик (на земле)
    cube_bottom = RigidBody.create_box(
        size=(1, 1, 1),
        mass=1.0,
        pose=Pose3.identity().with_translation(np.array([0, 0, 0.5])),
    )
    world.add_body(cube_bottom)

    # Верхний кубик (падает на нижний)
    cube_top = RigidBody.create_box(
        size=(1, 1, 1),
        mass=1.0,
        pose=Pose3.identity().with_translation(np.array([0, 0, 3.0])),
    )
    world.add_body(cube_top)

    # Симуляция
    dt = 1.0 / 60.0
    for _ in range(120):
        world.step(dt)

    # Нижний кубик остаётся на месте
    assert cube_bottom.position[2] > 0.4, "Нижний кубик на земле"
    assert cube_bottom.position[2] < 0.6, "Нижний кубик на земле"

    # Верхний кубик лежит на нижнем (z ≈ 1.5)
    assert cube_top.position[2] > 1.3, "Верхний кубик на нижнем"
    assert cube_top.position[2] < 1.7, "Верхний кубик на нижнем"


def test_sphere_creation():
    """Тест: создание сферы с правильной инерцией."""
    sphere = RigidBody.create_sphere(
        radius=0.5,
        mass=2.0,
        pose=Pose3.identity(),
    )

    assert sphere.mass == 2.0
    # I = (2/5) * m * r^2 = (2/5) * 2 * 0.25 = 0.2
    expected_I = (2.0 / 5.0) * 2.0 * 0.5**2
    assert abs(sphere.spatial_inertia.Ic[0, 0] - expected_I) < 1e-10


def test_static_body():
    """Тест: статическое тело не двигается."""
    world = PhysicsWorld(gravity=np.array([0, 0, -9.81]))

    static_box = RigidBody.create_box(
        size=(1, 1, 1),
        mass=1.0,
        pose=Pose3.identity().with_translation(np.array([0, 0, 5.0])),
        is_static=True,
    )
    world.add_body(static_box)

    initial_z = static_box.position[2]

    dt = 1.0 / 60.0
    for _ in range(60):
        world.step(dt)

    # Статическое тело не должно упасть
    assert static_box.position[2] == initial_z


if __name__ == "__main__":
    test_drop_cube()
    print("test_drop_cube passed")

    test_tilted_cube()
    print("test_tilted_cube passed")

    test_box_box_collision()
    print("test_box_box_collision passed")

    test_sphere_creation()
    print("test_sphere_creation passed")

    test_static_body()
    print("test_static_body passed")

    print("\nAll tests passed!")
