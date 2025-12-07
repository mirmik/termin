"""Test script: drop a cube on the ground."""

import numpy as np
from termin.geombase.pose3 import Pose3
from termin.physics import RigidBody, PhysicsWorld


def test_drop_cube():
    """Simple test: drop a cube and watch it bounce."""
    # Create world
    world = PhysicsWorld(
        gravity=np.array([0, 0, -9.81]),
        iterations=10,
        restitution=0.5,
        friction=0.3,
    )

    # Create a cube at height 2
    cube = RigidBody.create_box(
        size=(1, 1, 1),
        mass=1.0,
        pose=Pose3.identity().with_translation(np.array([0, 0, 2.0])),
    )
    world.add_body(cube)

    # Simulate
    dt = 1.0 / 60.0
    print("Starting simulation: dropping cube from z=2")
    print("-" * 50)

    for frame in range(120):  # 2 seconds
        world.step(dt)

        if frame % 10 == 0:
            z = cube.position[2]
            vz = cube.velocity.lin[2]
            print(f"Frame {frame:3d}: z={z:6.3f}, vz={vz:7.3f}")

    print("-" * 50)
    print(f"Final position: {cube.position}")
    print(f"Final velocity: {cube.velocity.lin}")

    # Check that cube is resting on ground (z ≈ 0.5 for unit cube)
    assert cube.position[2] < 1.0, "Cube should have fallen"
    assert cube.position[2] > 0.4, "Cube should rest on ground"
    assert abs(cube.velocity.lin[2]) < 0.5, "Cube should be nearly at rest"

    print("\nTest passed!")


def test_tilted_cube():
    """Test: drop a tilted cube."""
    world = PhysicsWorld(
        gravity=np.array([0, 0, -9.81]),
        iterations=20,
        restitution=0.3,
        friction=0.5,
    )

    # Create a tilted cube
    from termin.geombase.pose3 import Pose3
    import math

    # Rotate 30 degrees around X axis
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

    # Simulate
    dt = 1.0 / 60.0
    print("\nStarting simulation: dropping tilted cube")
    print("-" * 50)

    for frame in range(180):  # 3 seconds
        world.step(dt)

        if frame % 20 == 0:
            z = cube.position[2]
            omega = np.linalg.norm(cube.omega)
            print(f"Frame {frame:3d}: z={z:6.3f}, |omega|={omega:7.3f}")

    print("-" * 50)
    print(f"Final position: {cube.position}")
    print(f"Final angular velocity: {cube.omega}")

    print("\nTilted cube test completed!")


if __name__ == "__main__":
    test_drop_cube()
    test_tilted_cube()
