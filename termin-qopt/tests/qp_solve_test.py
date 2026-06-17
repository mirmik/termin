import numpy as np
from termin.linalg.solve import solve_qp_equalities


# Генератор SPD матрицы
def make_spd(rng, n):
    M = rng.normal(size=(n, n))
    return M.T @ M + np.eye(n) * 1e-3  # слегка регуляризуем


def test_known_solution():
    """
    Тест 1: аналитически известное решение.
    QP:
        min 1/2 x^T H x + g^T x
        s.t. x1 + x2 = 1
    Выбираем H и g так, чтобы решение можно было получить вручную.
    """
    H = np.array([[2., 0.],
                  [0., 2.]])
    g = np.array([-2., -6.])   # градиент
    A = np.array([[1., 1.]])
    b = np.array([1.])

    x_expected = np.array([-0.5, 1.5])
    x, lam = solve_qp_equalities(H, g, A, b)

    assert np.allclose(x, x_expected, atol=1e-7)


def test_random_stress():
    """
    Много детерминированно сгенерированных задач.
    Единственная проверка — выполнение ККТ.
    """
    rng = np.random.default_rng(0)

    for _ in range(50):
        n = 6
        m = 3

        H = make_spd(rng, n)
        g = rng.normal(size=n)
        A = rng.normal(size=(m, n))
        b = rng.normal(size=m)

        x, lam = solve_qp_equalities(H, g, A, b)

        # ККТ проверки
        assert np.linalg.norm(H @ x + A.T @ lam + g) < 1e-7
        assert np.linalg.norm(A @ x - b) < 1e-7
