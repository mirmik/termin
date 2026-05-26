import numpy as np
from termin.linalg.solve import solve_qp_active_set


def solve_eq(H, g, A_eq, b_eq):
    """Простенькая подстановка — решаем через active-set без неравенств."""
    return solve_qp_active_set(H, g, A_eq, b_eq, C=np.zeros((0, H.shape[0])), d=np.zeros(0))


# ------------------------------------------------------------------------
# 1. Простейшая QP без неравенств
# ------------------------------------------------------------------------
def test_basic_equality_qp():
    H = np.array([[2., 0.],
                  [0., 2.]])
    g = np.array([-2., -6.])

    A = np.array([[1., 1.]])
    b = np.array([1.])

    # Аналитическое решение: x = [0, 1]
    x, lam_eq, lam_ineq, active, iters = solve_eq(H, g, A, b)

    assert np.allclose(H@x + A.T @ lam_eq + g, 0)
    assert np.allclose(x, np.array([-0.5, 1.5]), atol=1e-7)
    assert active.size == 0
    assert lam_ineq.size == 0
    assert iters == 1  # без неравенств всегда 1 итерация


# ------------------------------------------------------------------------
# 2. Одно неравенство становится активным
#     min (x1 - 1)^2
#     s.t. x1 <= 0.5
#     optimum: x1 = 0.5
# ------------------------------------------------------------------------
def test_single_inequality_becomes_active():
    H = np.array([[2.]])     # cost = (x-1)^2 → H=2, g=-2
    g = np.array([-2.])

    A_eq = np.zeros((0, 1))
    b_eq = np.zeros(0)

    C = np.array([[1.]])  # x <= 0.5
    d = np.array([0.5])

    x, lam_eq, lam_ineq, active, iters = solve_qp_active_set(H, g, A_eq, b_eq, C, d)

    assert np.allclose(H@x + A_eq.T @ lam_eq + C[active].T @ lam_ineq + g, 0)
    assert np.allclose(x, np.array([0.5]), atol=1e-7)
    assert active.tolist() == [0]
    assert lam_ineq.size == 1
    assert lam_ineq[0] >= 0  # ККТ
    assert iters == 2  # 1 итерация без активного, 2-я с активным


# ------------------------------------------------------------------------
# 3. Warm-start по активному набору
#    Мы заранее говорим решателю, что ограничение активно,
#    и он должен решить всё за 1 итерацию.
# ------------------------------------------------------------------------
def test_active_set_warm_start():
    H = np.array([[2.]])
    g = np.array([-2.])

    A_eq = np.zeros((0, 1))
    b_eq = np.zeros(0)

    C = np.array([[1.]])  # x <= 0.5
    d = np.array([0.5])

    active0 = np.array([0])  # warm-start

    x, lam_eq, lam_ineq, active, iters = solve_qp_active_set(
        H, g, A_eq, b_eq,
        C=C, d=d,
        active0=active0
    )

    assert np.allclose(H@x + A_eq.T @ lam_eq + C[active].T @ lam_ineq + g, 0)
    assert np.allclose(x, np.array([0.5]), atol=1e-7)
    assert active.tolist() == [0]
    assert iters == 1  # ВАЖНО: warm-start должен сходиться сразу


# ------------------------------------------------------------------------
# 4. λ < 0 → удаление активного ограничения
#    Изначально x0 находится ровно на границе, active0 = {0}.
#    Но задача не требует активного ограничения.
# ------------------------------------------------------------------------
def test_removing_incorrect_active_constraint():
    H = np.array([[2.]])
    g = np.array([0.])  # минимум при x = 0

    A_eq = np.zeros((0, 1))
    b_eq = np.zeros(0)

    C = np.array([[1.]])  # x <= 0.5
    d = np.array([0.5])

    # x0 на границе, решатель может подумать "оно активно"
    x0 = np.array([0.5])
    active0 = np.array([0])

    x, lam_eq, lam_ineq, active, iters = solve_qp_active_set(
        H, g, A_eq, b_eq,
        C, d,
        x0=x0, active0=active0
    )

    assert np.allclose(H@x + A_eq.T @ lam_eq + C[active].T @ lam_ineq + g, 0)
    # Оптимум при x=0, ограничение НЕ активно
    assert np.allclose(x, np.array([0.0]))
    assert active.size == 0
    assert lam_ineq.size == 0
    assert iters == 2  # 1-я итерация с активным, 2-я без


# ------------------------------------------------------------------------
# 5. Два нарушенных ограничения → выбираем "худший"
# ------------------------------------------------------------------------
def test_two_violations_pick_worst():
    H = np.eye(2)
    g = np.array([0., 0.])

    A_eq = np.zeros((0, 2))
    b_eq = np.zeros(0)

    # Ограничения:
    # x1 <= -1     (нарушение = x1 - (-1))
    # x1 <=  0
    C = np.array([[1., 0.],
                  [1., 0.]])
    d = np.array([-1., 0.])

    # x0 сильно нарушает оба
    x0 = np.array([1., 0.])

    x, lam_eq, lam_ineq, active, iters = solve_qp_active_set(
        H, g, A_eq, b_eq,
        C, d,
        x0=x0
    )

    assert np.allclose(H@x + A_eq.T @ lam_eq + C[active].T @ lam_ineq + g, 0)
    # "худшее" нарушение — для первого ограничения (1 - (-1) = 2)
    assert active[0] == 0
    assert iters == 2  # 1-я итерация с одним активным, 2-я без нарушений


# ------------------------------------------------------------------------
# 6. Активное ограничение остаётся активным при λ >= 0
# ------------------------------------------------------------------------
def test_active_constraint_stays_active():
    H = np.array([[2.]])
    g = np.array([-2.])

    A_eq = np.zeros((0, 1))
    b_eq = np.zeros(0)

    C = np.array([[1.]])
    d = np.array([0.5])

    # x0 ≈ 0.5, ограничение активно и λ > 0
    x0 = np.array([0.5])
    active0 = np.array([0])

    x, lam_eq, lam_ineq, active, iters = solve_qp_active_set(
        H, g, A_eq, b_eq, C, d,
        x0=x0, active0=active0
    )

    assert np.allclose(H@x + A_eq.T @ lam_eq + C[active].T @ lam_ineq + g, 0)
    assert active.tolist() == [0]  # не должно исчезнуть
    assert lam_ineq[0] >= 0
    assert np.allclose(x, np.array([0.5]))
    assert iters == 1  # должно сойтись сразу
