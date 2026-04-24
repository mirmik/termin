"""Тесты физического движка: падение кубиков на плоскость."""

import math
import numpy as np
from termin.geombase._geom_native import Pose3, Vec3, Quat
from termin.physics import RigidBody, PhysicsWorld


def test_drop_cube():
    """Тест: падение кубика и отскок от земли."""
    world = PhysicsWorld()
    world.gravity = Vec3(0, 0, -9.81)
    world.solver_iterations = 10
    world.restitution = 0.5
    world.friction = 0.3
    world.ground_enabled = True

    # Кубик на высоте 2
    pose = Pose3()
    pose.lin = Vec3(0, 0, 2.0)
    idx = world.add_box(1, 1, 1, 1.0, pose)

    # Симуляция 2 секунды
    dt = 1.0 / 60.0
    for _ in range(120):
        world.step(dt)

    cube = world.get_body(idx)

    # Кубик должен лежать на земле (z ≈ 0.5 для единичного кубика)
    assert cube.position().z < 1.0, "Кубик должен упасть"
    assert cube.position().z > 0.4, "Кубик должен лежать на земле"
    assert abs(cube.linear_velocity.z) < 0.5, "Кубик должен быть в покое"


def test_tilted_cube():
    """Тест: падение наклонённого кубика."""
    world = PhysicsWorld()
    world.gravity = Vec3(0, 0, -9.81)
    world.solver_iterations = 20
    world.restitution = 0.3
    world.friction = 0.5
    world.ground_enabled = True

    # Кубик наклонён на 30 градусов вокруг оси X
    angle = math.radians(30)
    pose = Pose3(
        Quat(math.sin(angle / 2), 0, 0, math.cos(angle / 2)),
        Vec3(0, 0, 2.0)
    )
    idx = world.add_box(1, 1, 1, 1.0, pose)

    # Симуляция 3 секунды
    dt = 1.0 / 60.0
    for _ in range(180):
        world.step(dt)

    cube = world.get_body(idx)

    # Кубик должен упасть и успокоиться
    assert cube.position().z < 1.0, "Кубик должен упасть"
    assert cube.position().z > 0.4, "Кубик должен лежать на земле"


def test_box_box_collision():
    """Тест: столкновение двух кубиков."""
    world = PhysicsWorld()
    world.gravity = Vec3(0, 0, -9.81)
    world.solver_iterations = 10
    world.restitution = 0.2
    world.friction = 0.5
    world.ground_enabled = True

    # Нижний кубик (на земле)
    pose_bottom = Pose3()
    pose_bottom.lin = Vec3(0, 0, 0.5)
    idx_bottom = world.add_box(1, 1, 1, 1.0, pose_bottom)

    # Верхний кубик (падает на нижний)
    pose_top = Pose3()
    pose_top.lin = Vec3(0, 0, 3.0)
    idx_top = world.add_box(1, 1, 1, 1.0, pose_top)

    # Симуляция
    dt = 1.0 / 60.0
    for _ in range(120):
        world.step(dt)

    cube_bottom = world.get_body(idx_bottom)
    cube_top = world.get_body(idx_top)

    # Нижний кубик остаётся на месте
    assert cube_bottom.position().z > 0.4, "Нижний кубик на земле"
    assert cube_bottom.position().z < 0.6, "Нижний кубик на земле"

    # Верхний кубик лежит на нижнем (z ≈ 1.5)
    assert cube_top.position().z > 1.3, "Верхний кубик на нижнем"
    assert cube_top.position().z < 1.7, "Верхний кубик на нижнем"


def test_sphere_creation():
    """Тест: создание сферы с правильной инерцией."""
    sphere = RigidBody.create_sphere(0.5, 2.0)

    assert sphere.mass == 2.0
    # I = (2/5) * m * r^2 = (2/5) * 2 * 0.25 = 0.2
    expected_I = (2.0 / 5.0) * 2.0 * 0.5**2
    assert abs(sphere.inertia.x - expected_I) < 1e-10


def test_static_body():
    """Тест: статическое тело не двигается."""
    world = PhysicsWorld()
    world.gravity = Vec3(0, 0, -9.81)

    pose = Pose3()
    pose.lin = Vec3(0, 0, 5.0)
    idx = world.add_box(1, 1, 1, 1.0, pose, is_static=True)

    static_box = world.get_body(idx)
    initial_z = static_box.position().z

    dt = 1.0 / 60.0
    for _ in range(60):
        world.step(dt)

    # Статическое тело не должно упасть
    assert static_box.position().z == initial_z


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
