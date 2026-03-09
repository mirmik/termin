import numpy as np

from termin.robot.hqsolver import (
    HQPSolver,
    Level,
    QuadraticTask,
    EqualityConstraint,
    InequalityConstraint
)

from termin.linalg.solve import solve_qp_active_set
from termin.linalg.subspaces import nullspace_basis

# -------------------------------------------------------------
# ТЕСТ 1: ПРОСТАЯ QP (ОДИН УРОВЕНЬ)
# -------------------------------------------------------------

def test_hqp_single_level_basic():
    solver = HQPSolver(n_vars=2)

    lvl = Level(priority=0)
    J = np.eye(2)
    v = np.array([1., 2.])
    lvl.add_task(QuadraticTask(J, v))
    solver.add_level(lvl)

    x = solver.solve()

    # Ожидаем x = v (минимум ||x - v||^2)
    assert np.allclose(x, [1., 2.], atol=1e-7)


# -------------------------------------------------------------
# ТЕСТ 2: ДВА УРОВНЯ, ВТОРОЙ РАБОТАЕТ В NULLSPACE ПЕРВОГО
# -------------------------------------------------------------

def test_hqp_two_levels_nullspace_simple():
    solver = HQPSolver(n_vars=2)

    # Level 0: тянем x → [1, 0]
    lvl0 = Level(priority=0)
    lvl0.add_task(QuadraticTask(np.eye(2), np.array([1., 0.])))
    solver.add_level(lvl0)

    # Level 1: x → [1, 5], но только в nullspace первого уровня
    lvl1 = Level(priority=1)
    lvl1.add_task(QuadraticTask(np.eye(2), np.array([1., 5.])))
    solver.add_level(lvl1)

    x = solver.solve()

    assert abs(x[0] - 1.0) < 1e-7   # не нарушено первым уровнем
    assert abs(x[1] - 0.0) < 1e-7   # второй уровень не может изменить x1

# -------------------------------------------------------------
# ТЕСТ 2.2: ДВА УРОВНЯ, ВТОРОЙ РАБОТАЕТ В NULLSPACE ПЕРВОГО
# -------------------------------------------------------------

def test_hqp_two_levels_nullspace():
    solver = HQPSolver(n_vars=4)

    # Level 0: Теперь делаем невырожденный nullspace
    lvl0 = Level(priority=0)

    J = np.array([
        [1,0,0,0],
        [0,1,0,0],
        [0,0,1,1.1],
    ])

    lvl0.add_task(QuadraticTask(J, np.array([1., 0., 0.])))
    solver.add_level(lvl0)

    # Level 1: x → [1, 5], но только в nullspace первого уровня
    lvl1 = Level(priority=1)
    lvl1.add_task(QuadraticTask(np.eye(4), np.array([1., 5., -2., 2.])))
    solver.add_level(lvl1)

    x = solver.solve()

    assert abs(x[0] - 1.0) < 1e-7   # не нарушено первым уровнем
    assert abs(x[1] - 0.0) < 1e-7   # второй уровень не может изменить x2
    assert abs(x[2] + 1.1 * x[3]) < 1e-7  # сохраняем ограничение первого уровня

    N = nullspace_basis(J)
    x0 = np.array([1., 0., 0., 0.])
    x_des = np.array([1., 5., -2., 2.])
    z = N.T @ (x_des - x0)
    x_expected = x0 + N @ z
    assert np.allclose(x, x_expected, atol=1e-7)


# -------------------------------------------------------------
# ТЕСТ 3: РАВЕНСТВО НА УРОВНЕ HQP
# -------------------------------------------------------------

def test_hqp_equality_constraint():
    solver = HQPSolver(n_vars=2)

    lvl = Level(priority=0)
    lvl.add_task(QuadraticTask(np.eye(2), np.array([2., 2.])))
    lvl.add_equality(EqualityConstraint(
        A=np.array([[1., 1.]]),
        b=np.array([1.])
    ))
    solver.add_level(lvl)

    x = solver.solve()

    # Аналитически: минимум при x1 + x2 = 1 это x1 = x2 = 0.5
    assert np.allclose(x, [0.5, 0.5], atol=1e-7)


# -------------------------------------------------------------
# ТЕСТ 4: НЕРАВЕНСТВО (ACTIVE SET ВНУТРИ HQP)
# -------------------------------------------------------------

def test_hqp_inequality_constraint():
    solver = HQPSolver(n_vars=1)

    lvl = Level(priority=0)
    lvl.add_task(QuadraticTask(np.array([[1.]]), np.array([1.])))
    lvl.add_inequality(InequalityConstraint(
        C=np.array([[1.]]),
        d=np.array([0.5])
    ))
    solver.add_level(lvl)

    x = solver.solve()

    # Минимум при ограничении x ≤ 0.5
    assert abs(x[0] - 0.5) < 1e-7


# -------------------------------------------------------------
# ТЕСТ 5: КОМБИНАЦИЯ ЗАДАЧ С NULLSPACE И НЕРАВЕНСТВАМИ
# -------------------------------------------------------------

def test_hqp_full_logic_with_constraints():
    solver = HQPSolver(n_vars=2)

    # Level 0: фиксируем x1 = 1, оставляем свободу по x2
    lvl0 = Level(priority=0)
    lvl0.add_task(QuadraticTask(
        J=np.array([[1., 0.]]),   # фиксируем только x1
        v=np.array([1.])
    ))
    solver.add_level(lvl0)

    # Level 1: хотим x → [1,10], но ограничение x2 <= 3
    lvl1 = Level(priority=1)
    lvl1.add_task(QuadraticTask(np.eye(2), np.array([1., 10.])))
    lvl1.add_inequality(InequalityConstraint(
        C=np.array([[0., 1.]]),   # x2 <= 3
        d=np.array([3.])
    ))
    solver.add_level(lvl1)

    x = solver.solve()

    # Первый уровень: x1 = 1
    assert abs(x[0] - 1) < 1e-7

    # Второй уровень: двигаем только x2 → ограничение даёт x2 = 3
    assert abs(x[1] - 3) < 1e-7

