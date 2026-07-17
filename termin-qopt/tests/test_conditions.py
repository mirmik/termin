import numpy as np

from termin.robot.conditions import ConditionCollection, SymCondition


def test_robot_conditions_build_weighted_normal_equations() -> None:
    first = SymCondition(
        np.array([[1.0, 0.0]]),
        np.array([2.0]),
        weight=2.0,
    )
    second = SymCondition(
        np.array([[0.0, 1.0]]),
        np.array([3.0]),
    )
    conditions = ConditionCollection()
    conditions.add(first)
    conditions.add(second, weight=4.0)

    np.testing.assert_allclose(conditions.A(), np.diag([2.0, 4.0]))
    np.testing.assert_allclose(conditions.b(), np.array([4.0, 12.0]))
    np.testing.assert_allclose(first.NullProj(), np.diag([0.0, 1.0]))
    assert conditions.weights == [2.0, 4.0]
