<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/linalg/solve.py</title>
</head>
<body>
<pre><code>
import numpy as np
from scipy.linalg import cho_factor, cho_solve
from typing import Optional, Tuple, List

def solve_qp_equalities(H, g, A, b):
    &quot;&quot;&quot;
    Решает задачу:
        min  1/2 x^T H x + g^T x
        s.t. A x = b

    Академический вывод системы Шура:

      ККТ:
        [ H   A^T ] [ x ] = [ -g ]
        [ A    0  ] [ λ ]   [  b ]

      Из первой строки:
        x = -H^{-1}(g + A^T λ)

      Подставляем в A x = b:
        A[-H^{-1}(g + A^T λ)] = b

      Получаем:
        -A H^{-1} g - A H^{-1} A^T λ = b

      Система Шура:
        (A H^{-1} A^T) λ = -b - A H^{-1} g

      После нахождения λ:
        H x = -g - A^T λ
    &quot;&quot;&quot;

    try:
        # --- 1) Cholesky разложение: H = L L^T ---
        L, lower = cho_factor(H)

        # --- 2) Вычислить H^{-1} g и H^{-1} A^T ---
        # здесь считаем два объекта, входящие в формулы Шура:
        # H^{-1} g  и  H^{-1} A^T
        y_g = cho_solve((L, lower), g)     # = H^{-1} g
        Y   = cho_solve((L, lower), A.T)   # = H^{-1} A^T

        # --- 3) Построить систему Шура ---
        # S = A H^{-1} A^T
        S = A @ Y
        # r_λ = -b - A H^{-1} g
        r_lambda = -b - A @ y_g

        # --- 4) Решить систему Шура: S λ = r_λ ---
        λ = np.linalg.solve(S, r_lambda)

        # --- 5) Восстановить x: H x = -g - A^T λ ---
        w = -g - A.T @ λ
        x = cho_solve((L, lower), w)
    except np.linalg.LinAlgError:
        # H может быть лишь положительно полуопределённой.
        n = H.shape[0]
        m = A.shape[0]

        if m &gt; 0:
            zero_block = np.zeros((m, m), dtype=H.dtype)
            KKT = np.block([
                [H, A.T],
                [A, zero_block]
            ])
            rhs = np.concatenate([-g, b])
            sol, *_ = np.linalg.lstsq(KKT, rhs, rcond=None)
            x = sol[:n]
            λ = sol[n:]
        else:
            x, *_ = np.linalg.lstsq(H, -g, rcond=None)
            λ = np.zeros(0, dtype=H.dtype)

    return x, λ



def solve_qp_active_set(
    H: np.ndarray,
    g: np.ndarray,
    A_eq: np.ndarray,
    b_eq: np.ndarray,
    C: np.ndarray,
    d: np.ndarray,
    x0: Optional[np.ndarray] = None,
    active0: Optional[np.ndarray] = None,
    max_iter: int = 50,
    tol: float = 1e-7,
    active_tol: float = 1e-6,
) -&gt; Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, int]:
    &quot;&quot;&quot;
    Active-set решатель для задачи:

        min  1/2 x^T H x + g^T x                        | x: (n,)
        s.t. A_eq x = b_eq                              | A_eq: (m_eq×n), b_eq: (m_eq,)
             C x &lt;= d                                   | C: (m_ineq×n), d: (m_ineq,)

    Параметры:
        H, g        – квадратичный функционал.          | H: (n×n), g: (n,)
        A_eq, b_eq  – равенства.                        | A_eq: (m_eq×n), b_eq: (m_eq,)
        C, d        – неравенства.                      | C: (m_ineq×n), d: (m_ineq,)
        x0          – warm-start по x.                  | x0: (n,)
        active0     – warm-start по активному множеству.| active0: (k,)
        max_iter    – максимум итераций.
        tol         – допуск ККТ.
        active_tol  – допуск при восстановлении active-set из x0.

    Возвращает:
        x           – решение.                          | (n,)
        lam_eq      – множители равенств.               | (m_eq,)
        lam_ineq    – множители активных неравенств.    | (k,)
        active_set  – индексы активных ограничений.     | (k,)
        iters       – количество итераций.              | int
    &quot;&quot;&quot;
    n = H.shape[0]
    m_ineq = C.shape[0]

    # ------------------------------------------------------------
    # Инициализация x
    # ------------------------------------------------------------
    x = np.zeros(n) if x0 is None else x0.copy()

    # ------------------------------------------------------------
    # Инициализация active-set
    # ------------------------------------------------------------
    active: List[int] = []

    # 1) Если есть active0 — он главный (сохраняем порядок, убираем дубли)
    if active0 is not None:
        for idx in active0:
            idx = int(idx)
            if 0 &lt;= idx &lt; m_ineq and idx not in active:
                active.append(idx)

    # 2) Если active0 нет, но есть x0 — пробуем восстановить из C @ x0 ≈ d
    elif x0 is not None and m_ineq &gt; 0:
        viol0 = C @ x0 - d
        for i in range(m_ineq):
            if abs(viol0[i]) &lt;= active_tol:
                active.append(i)

    # 3) Иначе — начинаем с пустого active-set
    # (ничего делать не надо, active и так пуст)

    # ------------------------------------------------------------
    # Основной цикл коррекции active-set
    # ------------------------------------------------------------
    iters = 0

    for it in range(max_iter):
        iters = it + 1

        # --- 1. Формируем матрицу активных равенств ---
        if active:
            A_act = np.vstack([A_eq, C[active]])
            b_act = np.concatenate([b_eq, d[active]])
        else:
            A_act = A_eq
            b_act = b_eq

        # --- 2. Решаем подзадачу равенств ---
        x, lam_all = solve_qp_equalities(H, g, A_act, b_act)

        # --- 3. Разбираем множители Лагранжа ---
        n_eq = A_eq.shape[0]
        lam_eq = lam_all[:n_eq]
        lam_ineq = lam_all[n_eq:]  # соответствует active[0], active[1], ...

        # --- 4. Ищем нарушенные неравенства ---
        if m_ineq &gt; 0:
            violations = C @ x - d
            candidates = [
                i for i in range(m_ineq)
                if (violations[i] &gt; tol) and (i not in active)
            ]
        else:
            candidates = []

        if candidates:
            # Добавляем самое сильно нарушенное (защита от дублей встроена)
            worst = max(candidates, key=lambda i: violations[i])
            active.append(worst)
            continue  # повторяем итерацию с новым active-set

        # --- 5. Проверяем λ на активных ---
        to_remove = []
        for j, idx in enumerate(active):
            if lam_ineq[j] &lt; -tol:
                to_remove.append(idx)

        if to_remove:
            # Убираем все ограничения, нарушающие условия ККТ
            active = [i for i in active if i not in to_remove]
            continue  # повторяем итерацию

        # --- 6. ККТ выполнены, нарушений нет, λ &gt;= 0 — готово ---
        break

    # ------------------------------------------------------------
    # Финал: отдаём только λ для активных ограничений в корректном порядке
    # ------------------------------------------------------------
    lam_ineq_final = lam_ineq if (m_ineq &gt; 0 and active) else np.zeros(0)
    active_arr = np.array(active, dtype=int)

    return x, lam_eq, lam_ineq_final, active_arr, iters

</code></pre>
</body>
</html>
