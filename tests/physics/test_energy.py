"""Тест на сохранение энергии в физическом движке."""

import numpy as np
from termin.geombase._geom_native import Pose3, Vec3, Quat
from termin.physics import RigidBody, PhysicsWorld


def compute_total_energy(world: PhysicsWorld, gravity_z: float) -> float:
    """Вычислить полную механическую энергию системы."""
    total = 0.0

    for i in range(world.body_count()):
        body = world.get_body(i)
        if body.is_static:
            continue

        # Кинетическая энергия
        # T = 0.5 * m * v² + 0.5 * ω · (I · ω)
        m = body.mass
        v = body.linear_velocity
        omega = body.angular_velocity

        # Линейная КЭ
        v_sq = v.x**2 + v.y**2 + v.z**2
        T_lin = 0.5 * m * v_sq

        # Угловая КЭ (упрощённо, в СК тела инерция диагональная)
        # Для точности нужно преобразовать omega в СК тела
        R = body.pose.rotation_matrix()  # numpy array (3,3)

        # omega_body = R^T @ omega_world
        omega_arr = np.array([omega.x, omega.y, omega.z])
        omega_body = R.T @ omega_arr

        I = body.inertia
        T_rot = 0.5 * (I.x * omega_body[0]**2 + I.y * omega_body[1]**2 + I.z * omega_body[2]**2)

        T = T_lin + T_rot

        # Потенциальная энергия (относительно z=0)
        h = body.position().z
        g = abs(gravity_z)
        U = m * g * h

        total += T + U

    return total


def test_free_fall_energy():
    """Тест: энергия сохраняется при свободном падении (без коллизий)."""
    world = PhysicsWorld()
    world.gravity = Vec3(0, 0, -9.81)
    world.solver_iterations = 10
    world.restitution = 0.0
    world.friction = 0.0
    world.ground_enabled = False

    # Кубик падает свободно
    pose = Pose3()
    pose.lin = Vec3(0, 0, 10.0)
    idx = world.add_box(1, 1, 1, 1.0, pose)

    # Отключаем демпфирование для чистого теста энергии
    body = world.get_body(idx)
    body.linear_damping = 0.0
    body.angular_damping = 0.0

    dt = 1.0 / 60.0
    gravity_z = -9.81

    initial_energy = compute_total_energy(world, gravity_z)
    print(f"Initial energy: {initial_energy:.6f}")

    for i in range(120):  # 2 секунды
        world.step(dt)

        if i % 30 == 0:
            E = compute_total_energy(world, gravity_z)
            pos = world.get_body(idx).position()
            vel = world.get_body(idx).linear_velocity
            print(f"Step {i}: E={E:.6f}, z={pos.z:.3f}, v_z={vel.z:.3f}")

    final_energy = compute_total_energy(world, gravity_z)

    # Энергия должна сохраняться (с небольшой погрешностью из-за численного интегрирования)
    energy_drift = abs(final_energy - initial_energy) / initial_energy
    print(f"\nFinal energy: {final_energy:.6f}")
    print(f"Energy drift: {energy_drift * 100:.4f}%")

    # Допускаем 5% дрейфа за 2 секунды
    assert energy_drift < 0.05, f"Energy drift too large: {energy_drift * 100:.2f}%"


def test_spinning_cube_energy():
    """Тест: энергия сохраняется при вращении без гравитации."""
    world = PhysicsWorld()
    world.gravity = Vec3(0, 0, 0)
    world.solver_iterations = 10
    world.ground_enabled = False

    pose = Pose3()
    pose.lin = Vec3(0, 0, 5.0)
    idx = world.add_box(1, 1, 1, 1.0, pose)

    body = world.get_body(idx)
    body.angular_velocity = Vec3(1.0, 0.5, 0.3)
    body.linear_damping = 0.0
    body.angular_damping = 0.0

    dt = 1.0 / 60.0

    initial_energy = compute_total_energy(world, 0.0)
    print(f"\nSpinning cube test:")
    print(f"Initial energy: {initial_energy:.6f}")

    for i in range(300):  # 5 секунд
        world.step(dt)

        if i % 60 == 0:
            E = compute_total_energy(world, 0.0)
            omega = world.get_body(idx).angular_velocity
            omega_norm = (omega.x**2 + omega.y**2 + omega.z**2)**0.5
            print(f"Step {i}: E={E:.6f}, omega_norm={omega_norm:.6f}")

    final_energy = compute_total_energy(world, 0.0)

    energy_drift = abs(final_energy - initial_energy) / initial_energy if initial_energy > 0 else 0
    print(f"\nFinal energy: {final_energy:.6f}")
    print(f"Energy drift: {energy_drift * 100:.4f}%")

    # Энергия должна сохраняться
    assert energy_drift < 0.05, f"Energy drift too large: {energy_drift * 100:.2f}%"


def test_multiple_cubes_energy():
    """Тест: несколько кубиков без столкновений."""
    world = PhysicsWorld()
    world.gravity = Vec3(0, 0, -9.81)
    world.solver_iterations = 10
    world.ground_enabled = False

    # Несколько кубиков на разных высотах
    indices = []
    for i in range(5):
        pose = Pose3()
        pose.lin = Vec3(i * 3.0, 0, 10.0 + i * 2.0)
        idx = world.add_box(1, 1, 1, 1.0, pose)
        body = world.get_body(idx)
        body.linear_damping = 0.0
        body.angular_damping = 0.0
        indices.append(idx)

    dt = 1.0 / 60.0
    gravity_z = -9.81

    initial_energy = compute_total_energy(world, gravity_z)
    print(f"\nMultiple cubes test:")
    print(f"Initial energy: {initial_energy:.6f}")

    for i in range(120):
        world.step(dt)

        if i % 30 == 0:
            E = compute_total_energy(world, gravity_z)
            print(f"Step {i}: E={E:.6f}")

    final_energy = compute_total_energy(world, gravity_z)
    energy_drift = abs(final_energy - initial_energy) / initial_energy

    print(f"Final energy: {final_energy:.6f}")
    print(f"Energy drift: {energy_drift * 100:.4f}%")

    # Допускаем 5% дрейфа
    assert energy_drift < 0.05, f"Energy drift too large: {energy_drift * 100:.2f}%"


if __name__ == "__main__":
    print("=" * 60)
    print("TEST: Free fall energy conservation")
    print("=" * 60)
    test_free_fall_energy()
    print("\nPASSED\n")

    print("=" * 60)
    print("TEST: Spinning cube energy conservation")
    print("=" * 60)
    test_spinning_cube_energy()
    print("\nPASSED\n")

    print("=" * 60)
    print("TEST: Multiple cubes energy conservation")
    print("=" * 60)
    test_multiple_cubes_energy()
    print("\nPASSED\n")

    print("All energy tests passed!")
