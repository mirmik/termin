import numpy as np

from termin.robot.hqsolver import HQPSolver, Level
from termin.robot.hqtasks import (
    JointTrackingTask,
    CartesianTrackingTask,
    JointEqualityConstraint,
    CartesianEqualityConstraint,
    JointBoundsConstraint,
    JointVelocityDampingTask,
    JointPositionBoundsConstraint,
    build_joint_soft_limit_task,
)


def test_joint_tracking_and_bounds_tasks():
    solver = HQPSolver(n_vars=2)

    lvl = Level(priority=0)
    lvl.add_task(JointTrackingTask(q_ref=[2.0, -1.0]))
    lvl.add_inequality(JointBoundsConstraint(lower=[-0.5, -0.5], upper=[1.0, 0.0]))
    solver.add_level(lvl)

    x = solver.solve()
    np.testing.assert_allclose(x, [1.0, -0.5], atol=1e-7)


def test_cartesian_tasks_with_equalities():
    solver = HQPSolver(n_vars=3)

    lvl0 = Level(priority=0)
    sel = np.array([[1.0, 0.0, 0.0]])
    lvl0.add_equality(JointEqualityConstraint(q_target=[1.0, 0.0, 0.0], selection=sel))
    solver.add_level(lvl0)

    lvl1 = Level(priority=1)
    J_cart = np.array([[0.0, 1.0, 0.0],
                       [0.0, 0.0, 1.0]])
    desired = np.array([2.0, -3.0])
    lvl1.add_task(CartesianTrackingTask(J_cart, desired))
    lvl1.add_equality(CartesianEqualityConstraint(np.array([[0.0, 1.0, 1.0]]), np.array([0.0])))
    solver.add_level(lvl1)

    x = solver.solve()
    np.testing.assert_allclose(x, [1.0, 2.5, -2.5], atol=1e-7)


def test_joint_velocity_damping_task_prefers_zero():
    solver = HQPSolver(n_vars=1)
    lvl = Level(priority=0)
    lvl.add_task(JointTrackingTask(q_ref=[5.0]))
    lvl.add_task(JointVelocityDampingTask(n_dofs=1, weight=np.array([10.0])))
    solver.add_level(lvl)

    x = solver.solve()
    np.testing.assert_allclose(x, [10.0 / 22.0], atol=1e-9)


def test_joint_position_bounds_constraint_builds_expected_matrices():
    q = np.array([0.5, -0.5])
    constraint = JointPositionBoundsConstraint(
        q_current=q,
        lower=np.array([-1.0, -1.0]),
        upper=np.array([1.0, 1.0]),
        dt=0.5,
    )

    expected_C = np.array([
        [0.5, 0.0],
        [0.0, 0.5],
        [-0.5, 0.0],
        [0.0, -0.5],
    ])
    expected_d = np.array([0.5, 1.5, 1.5, 0.5])

    np.testing.assert_allclose(constraint.C, expected_C)
    np.testing.assert_allclose(constraint.d, expected_d)


def test_build_joint_soft_limit_task():
    q = np.array([np.deg2rad(118.0), np.deg2rad(-118.0)])
    bounds = np.array([np.deg2rad(120.0), np.deg2rad(120.0)])
    task = build_joint_soft_limit_task(
        q_current=q,
        lower=-bounds,
        upper=bounds,
        margin=np.deg2rad(5.0),
        gain=2.0,
    )
    assert task is not None
    assert task.J.shape[1] == 2
    # Первый сустав должен отталкиваться в отрицательную сторону
    assert task.v[0] < 0.0
    # Второй сустав — в положительную
    assert task.v[-1] > 0.0
