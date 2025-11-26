<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/linalg/solve.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
import numpy as np<br>
from scipy.linalg import cho_factor, cho_solve<br>
from typing import Optional, Tuple, List<br>
<br>
def solve_qp_equalities(H, g, A, b):<br>
    &quot;&quot;&quot;<br>
    Решает задачу:<br>
        min  1/2 x^T H x + g^T x<br>
        s.t. A x = b<br>
<br>
    Академический вывод системы Шура:<br>
<br>
      ККТ:<br>
        [ H   A^T ] [ x ] = [ -g ]<br>
        [ A    0  ] [ λ ]   [  b ]<br>
<br>
      Из первой строки:<br>
        x = -H^{-1}(g + A^T λ)<br>
<br>
      Подставляем в A x = b:<br>
        A[-H^{-1}(g + A^T λ)] = b<br>
<br>
      Получаем:<br>
        -A H^{-1} g - A H^{-1} A^T λ = b<br>
<br>
      Система Шура:<br>
        (A H^{-1} A^T) λ = -b - A H^{-1} g<br>
<br>
      После нахождения λ:<br>
        H x = -g - A^T λ<br>
    &quot;&quot;&quot;<br>
<br>
    try:<br>
        # --- 1) Cholesky разложение: H = L L^T ---<br>
        L, lower = cho_factor(H)<br>
<br>
        # --- 2) Вычислить H^{-1} g и H^{-1} A^T ---<br>
        # здесь считаем два объекта, входящие в формулы Шура:<br>
        # H^{-1} g  и  H^{-1} A^T<br>
        y_g = cho_solve((L, lower), g)     # = H^{-1} g<br>
        Y   = cho_solve((L, lower), A.T)   # = H^{-1} A^T<br>
<br>
        # --- 3) Построить систему Шура ---<br>
        # S = A H^{-1} A^T<br>
        S = A @ Y<br>
        # r_λ = -b - A H^{-1} g<br>
        r_lambda = -b - A @ y_g<br>
<br>
        # --- 4) Решить систему Шура: S λ = r_λ ---<br>
        λ = np.linalg.solve(S, r_lambda)<br>
<br>
        # --- 5) Восстановить x: H x = -g - A^T λ ---<br>
        w = -g - A.T @ λ<br>
        x = cho_solve((L, lower), w)<br>
    except np.linalg.LinAlgError:<br>
        # H может быть лишь положительно полуопределённой.<br>
        n = H.shape[0]<br>
        m = A.shape[0]<br>
<br>
        if m &gt; 0:<br>
            zero_block = np.zeros((m, m), dtype=H.dtype)<br>
            KKT = np.block([<br>
                [H, A.T],<br>
                [A, zero_block]<br>
            ])<br>
            rhs = np.concatenate([-g, b])<br>
            sol, *_ = np.linalg.lstsq(KKT, rhs, rcond=None)<br>
            x = sol[:n]<br>
            λ = sol[n:]<br>
        else:<br>
            x, *_ = np.linalg.lstsq(H, -g, rcond=None)<br>
            λ = np.zeros(0, dtype=H.dtype)<br>
<br>
    return x, λ<br>
<br>
<br>
<br>
def solve_qp_active_set(<br>
    H: np.ndarray,<br>
    g: np.ndarray,<br>
    A_eq: np.ndarray,<br>
    b_eq: np.ndarray,<br>
    C: np.ndarray,<br>
    d: np.ndarray,<br>
    x0: Optional[np.ndarray] = None,<br>
    active0: Optional[np.ndarray] = None,<br>
    max_iter: int = 50,<br>
    tol: float = 1e-7,<br>
    active_tol: float = 1e-6,<br>
) -&gt; Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, int]:<br>
    &quot;&quot;&quot;<br>
    Active-set решатель для задачи:<br>
<br>
        min  1/2 x^T H x + g^T x                        | x: (n,)<br>
        s.t. A_eq x = b_eq                              | A_eq: (m_eq×n), b_eq: (m_eq,)<br>
             C x &lt;= d                                   | C: (m_ineq×n), d: (m_ineq,)<br>
<br>
    Параметры:<br>
        H, g        – квадратичный функционал.          | H: (n×n), g: (n,)<br>
        A_eq, b_eq  – равенства.                        | A_eq: (m_eq×n), b_eq: (m_eq,)<br>
        C, d        – неравенства.                      | C: (m_ineq×n), d: (m_ineq,)<br>
        x0          – warm-start по x.                  | x0: (n,)<br>
        active0     – warm-start по активному множеству.| active0: (k,)<br>
        max_iter    – максимум итераций.<br>
        tol         – допуск ККТ.<br>
        active_tol  – допуск при восстановлении active-set из x0.<br>
<br>
    Возвращает:<br>
        x           – решение.                          | (n,)<br>
        lam_eq      – множители равенств.               | (m_eq,)<br>
        lam_ineq    – множители активных неравенств.    | (k,)<br>
        active_set  – индексы активных ограничений.     | (k,)<br>
        iters       – количество итераций.              | int<br>
    &quot;&quot;&quot;<br>
    n = H.shape[0]<br>
    m_ineq = C.shape[0]<br>
<br>
    # ------------------------------------------------------------<br>
    # Инициализация x<br>
    # ------------------------------------------------------------<br>
    x = np.zeros(n) if x0 is None else x0.copy()<br>
<br>
    # ------------------------------------------------------------<br>
    # Инициализация active-set<br>
    # ------------------------------------------------------------<br>
    active: List[int] = []<br>
<br>
    # 1) Если есть active0 — он главный (сохраняем порядок, убираем дубли)<br>
    if active0 is not None:<br>
        for idx in active0:<br>
            idx = int(idx)<br>
            if 0 &lt;= idx &lt; m_ineq and idx not in active:<br>
                active.append(idx)<br>
<br>
    # 2) Если active0 нет, но есть x0 — пробуем восстановить из C @ x0 ≈ d<br>
    elif x0 is not None and m_ineq &gt; 0:<br>
        viol0 = C @ x0 - d<br>
        for i in range(m_ineq):<br>
            if abs(viol0[i]) &lt;= active_tol:<br>
                active.append(i)<br>
<br>
    # 3) Иначе — начинаем с пустого active-set<br>
    # (ничего делать не надо, active и так пуст)<br>
<br>
    # ------------------------------------------------------------<br>
    # Основной цикл коррекции active-set<br>
    # ------------------------------------------------------------<br>
    iters = 0<br>
<br>
    for it in range(max_iter):<br>
        iters = it + 1<br>
<br>
        # --- 1. Формируем матрицу активных равенств ---<br>
        if active:<br>
            A_act = np.vstack([A_eq, C[active]])<br>
            b_act = np.concatenate([b_eq, d[active]])<br>
        else:<br>
            A_act = A_eq<br>
            b_act = b_eq<br>
<br>
        # --- 2. Решаем подзадачу равенств ---<br>
        x, lam_all = solve_qp_equalities(H, g, A_act, b_act)<br>
<br>
        # --- 3. Разбираем множители Лагранжа ---<br>
        n_eq = A_eq.shape[0]<br>
        lam_eq = lam_all[:n_eq]<br>
        lam_ineq = lam_all[n_eq:]  # соответствует active[0], active[1], ...<br>
<br>
        # --- 4. Ищем нарушенные неравенства ---<br>
        if m_ineq &gt; 0:<br>
            violations = C @ x - d<br>
            candidates = [<br>
                i for i in range(m_ineq)<br>
                if (violations[i] &gt; tol) and (i not in active)<br>
            ]<br>
        else:<br>
            candidates = []<br>
<br>
        if candidates:<br>
            # Добавляем самое сильно нарушенное (защита от дублей встроена)<br>
            worst = max(candidates, key=lambda i: violations[i])<br>
            active.append(worst)<br>
            continue  # повторяем итерацию с новым active-set<br>
<br>
        # --- 5. Проверяем λ на активных ---<br>
        to_remove = []<br>
        for j, idx in enumerate(active):<br>
            if lam_ineq[j] &lt; -tol:<br>
                to_remove.append(idx)<br>
<br>
        if to_remove:<br>
            # Убираем все ограничения, нарушающие условия ККТ<br>
            active = [i for i in active if i not in to_remove]<br>
            continue  # повторяем итерацию<br>
<br>
        # --- 6. ККТ выполнены, нарушений нет, λ &gt;= 0 — готово ---<br>
        break<br>
<br>
    # ------------------------------------------------------------<br>
    # Финал: отдаём только λ для активных ограничений в корректном порядке<br>
    # ------------------------------------------------------------<br>
    lam_ineq_final = lam_ineq if (m_ineq &gt; 0 and active) else np.zeros(0)<br>
    active_arr = np.array(active, dtype=int)<br>
<br>
    return x, lam_eq, lam_ineq_final, active_arr, iters<br>
<!-- END SCAT CODE -->
</body>
</html>
