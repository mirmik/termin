"""Тест на сохранение энергии в физическом движке."""

import numpy as np
from termin.geombase.pose3 import Pose3
from termin.physics import RigidBody, PhysicsWorld


def compute_total_energy(world: PhysicsWorld, gravity: np.ndarray) -> float:
    """Вычислить полную механическую энергию системы."""
    total = 0.0

    for body in world.bodies:
        if body.is_static:
            continue

        # Кинетическая энергия
        # T = 0.5 * m * v² + 0.5 * ω · (I · ω)
        m = body.mass
        v = body.linear_velocity
        omega = body.omega

        # Инерция в мировой СК
        I_world = body.rotation @ body.spatial_inertia.Ic @ body.rotation.T

        T = 0.5 * m * np.dot(v, v) + 0.5 * np.dot(omega, I_world @ omega)

        # Потенциальная энергия (относительно z=0)
        # U = m * g * h
        h = body.position[2]
        g = -gravity[2]  # gravity направлена вниз, берём модуль
        U = m * g * h

        total += T + U

    return total


def test_free_fall_energy():
    """Тест: энергия сохраняется при свободном падении (без коллизий)."""
    gravity = np.array([0, 0, -9.81])

    world = PhysicsWorld(
        gravity=gravity,
        iterations=10,
        restitution=0.0,
        friction=0.0,
    )
    world.ground_enabled = False  # Отключаем землю

    # Кубик падает свободно
    cube = RigidBody.create_box(
        size=(1, 1, 1),
        mass=1.0,
        pose=Pose3.identity().with_translation(np.array([0, 0, 10.0])),
    )
    world.add_body(cube)

    dt = 1.0 / 60.0

    initial_energy = compute_total_energy(world, gravity)
    print(f"Initial energy: {initial_energy:.6f}")

    energies = [initial_energy]

    for i in range(120):  # 2 секунды
        world.step(dt)
        E = compute_total_energy(world, gravity)
        energies.append(E)

        if i % 30 == 0:
            print(f"Step {i}: E={E:.6f}, z={cube.position[2]:.3f}, "
                  f"v_z={cube.linear_velocity[2]:.3f}, "
                  f"omega={np.linalg.norm(cube.omega):.6f}")

    final_energy = energies[-1]

    # Энергия должна сохраняться (с небольшой погрешностью из-за численного интегрирования)
    energy_drift = abs(final_energy - initial_energy) / initial_energy
    print(f"\nFinal energy: {final_energy:.6f}")
    print(f"Energy drift: {energy_drift * 100:.4f}%")

    # Допускаем 5% дрейфа за 2 секунды (полу-неявный Эйлер имеет численную диссипацию)
    assert energy_drift < 0.05, f"Energy drift too large: {energy_drift * 100:.2f}%"


def test_spinning_cube_energy():
    """Тест: энергия сохраняется при вращении без гравитации."""
    world = PhysicsWorld(
        gravity=np.array([0, 0, 0]),  # Без гравитации
        iterations=10,
        restitution=0.0,
        friction=0.0,
    )
    world.ground_enabled = False

    cube = RigidBody.create_box(
        size=(1, 1, 1),
        mass=1.0,
        pose=Pose3.identity().with_translation(np.array([0, 0, 5.0])),
    )
    # Задаём начальную угловую скорость
    from termin.geombase.screw import Screw3
    cube.velocity = Screw3(
        ang=np.array([1.0, 0.5, 0.3]),  # Вращение
        lin=np.array([0.0, 0.0, 0.0]),  # Без линейной скорости
    )
    world.add_body(cube)

    dt = 1.0 / 60.0
    gravity = np.array([0, 0, 0])

    initial_energy = compute_total_energy(world, gravity)
    print(f"\nSpinning cube test:")
    print(f"Initial energy: {initial_energy:.6f}")
    print(f"Initial omega: {cube.omega}")

    energies = [initial_energy]

    for i in range(300):  # 5 секунд
        world.step(dt)
        E = compute_total_energy(world, gravity)
        energies.append(E)

        if i % 60 == 0:
            print(f"Step {i}: E={E:.6f}, omega_norm={np.linalg.norm(cube.omega):.6f}")

    final_energy = energies[-1]

    energy_drift = abs(final_energy - initial_energy) / initial_energy if initial_energy > 0 else 0
    print(f"\nFinal energy: {final_energy:.6f}")
    print(f"Energy drift: {energy_drift * 100:.4f}%")

    # Энергия должна сохраняться
    assert energy_drift < 0.05, f"Energy drift too large: {energy_drift * 100:.2f}%"


def test_multiple_cubes_energy():
    """Тест: несколько кубиков без столкновений."""
    gravity = np.array([0, 0, -9.81])

    world = PhysicsWorld(
        gravity=gravity,
        iterations=10,
        restitution=0.0,
        friction=0.0,
    )
    world.ground_enabled = False

    # Несколько кубиков на разных высотах
    cubes = []
    for i in range(5):
        cube = RigidBody.create_box(
            size=(1, 1, 1),
            mass=1.0,
            pose=Pose3.identity().with_translation(np.array([i * 3.0, 0, 10.0 + i * 2.0])),
        )
        world.add_body(cube)
        cubes.append(cube)

    dt = 1.0 / 60.0

    initial_energy = compute_total_energy(world, gravity)
    print(f"\nMultiple cubes test:")
    print(f"Initial energy: {initial_energy:.6f}")

    for i in range(120):
        world.step(dt)

        if i % 30 == 0:
            E = compute_total_energy(world, gravity)
            print(f"Step {i}: E={E:.6f}")

    final_energy = compute_total_energy(world, gravity)
    energy_drift = abs(final_energy - initial_energy) / initial_energy

    print(f"Final energy: {final_energy:.6f}")
    print(f"Energy drift: {energy_drift * 100:.4f}%")

    # Допускаем 5% дрейфа (численная диссипация)
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
