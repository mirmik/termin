from termin.robotics import (
    ArticulationTask3D,
    InverseDynamicsHqpController3D,
    JointLimitConstraint3D,
    JointVelocityLimitConstraint3D,
    PointAccelerationTask3D,
    PointVelocityTask3D,
    VelocityHqpController3D,
)


def test_explicit_hqp_task_composition_surface() -> None:
    tasks = [
        JointLimitConstraint3D(priority=0),
        JointVelocityLimitConstraint3D([], [-2.0], [2.0], priority=0),
        PointVelocityTask3D(
            0,
            (0.0, 0.0, 0.0),
            (1.0, 2.0, 3.0),
            priority=0,
            diagonal_weight=[1.0, 1.0, 0.0],
        ),
        PointAccelerationTask3D(
            0,
            (0.0, 0.0, 0.0),
            (1.0, 2.0, 3.0),
            priority=1,
            diagonal_weight=[0.0, 0.0, 1.0],
        ),
    ]

    assert all(isinstance(task, ArticulationTask3D) for task in tasks)
    assert callable(VelocityHqpController3D.solve)
    assert callable(InverseDynamicsHqpController3D.solve)
