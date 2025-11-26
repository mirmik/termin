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
&#9;&quot;&quot;&quot;<br>
&#9;Решает задачу:<br>
&#9;&#9;min  1/2 x^T H x + g^T x<br>
&#9;&#9;s.t. A x = b<br>
<br>
&#9;Академический вывод системы Шура:<br>
<br>
&#9;ККТ:<br>
&#9;&#9;[ H   A^T ] [ x ] = [ -g ]<br>
&#9;&#9;[ A    0  ] [ λ ]   [  b ]<br>
<br>
&#9;Из первой строки:<br>
&#9;&#9;x = -H^{-1}(g + A^T λ)<br>
<br>
&#9;Подставляем в A x = b:<br>
&#9;&#9;A[-H^{-1}(g + A^T λ)] = b<br>
<br>
&#9;Получаем:<br>
&#9;&#9;-A H^{-1} g - A H^{-1} A^T λ = b<br>
<br>
&#9;Система Шура:<br>
&#9;&#9;(A H^{-1} A^T) λ = -b - A H^{-1} g<br>
<br>
&#9;После нахождения λ:<br>
&#9;&#9;H x = -g - A^T λ<br>
&#9;&quot;&quot;&quot;<br>
<br>
&#9;try:<br>
&#9;&#9;# --- 1) Cholesky разложение: H = L L^T ---<br>
&#9;&#9;L, lower = cho_factor(H)<br>
<br>
&#9;&#9;# --- 2) Вычислить H^{-1} g и H^{-1} A^T ---<br>
&#9;&#9;# здесь считаем два объекта, входящие в формулы Шура:<br>
&#9;&#9;# H^{-1} g  и  H^{-1} A^T<br>
&#9;&#9;y_g = cho_solve((L, lower), g)     # = H^{-1} g<br>
&#9;&#9;Y   = cho_solve((L, lower), A.T)   # = H^{-1} A^T<br>
<br>
&#9;&#9;# --- 3) Построить систему Шура ---<br>
&#9;&#9;# S = A H^{-1} A^T<br>
&#9;&#9;S = A @ Y<br>
&#9;&#9;# r_λ = -b - A H^{-1} g<br>
&#9;&#9;r_lambda = -b - A @ y_g<br>
<br>
&#9;&#9;# --- 4) Решить систему Шура: S λ = r_λ ---<br>
&#9;&#9;λ = np.linalg.solve(S, r_lambda)<br>
<br>
&#9;&#9;# --- 5) Восстановить x: H x = -g - A^T λ ---<br>
&#9;&#9;w = -g - A.T @ λ<br>
&#9;&#9;x = cho_solve((L, lower), w)<br>
&#9;except np.linalg.LinAlgError:<br>
&#9;&#9;# H может быть лишь положительно полуопределённой.<br>
&#9;&#9;n = H.shape[0]<br>
&#9;&#9;m = A.shape[0]<br>
<br>
&#9;&#9;if m &gt; 0:<br>
&#9;&#9;&#9;zero_block = np.zeros((m, m), dtype=H.dtype)<br>
&#9;&#9;&#9;KKT = np.block([<br>
&#9;&#9;&#9;&#9;[H, A.T],<br>
&#9;&#9;&#9;&#9;[A, zero_block]<br>
&#9;&#9;&#9;])<br>
&#9;&#9;&#9;rhs = np.concatenate([-g, b])<br>
&#9;&#9;&#9;sol, *_ = np.linalg.lstsq(KKT, rhs, rcond=None)<br>
&#9;&#9;&#9;x = sol[:n]<br>
&#9;&#9;&#9;λ = sol[n:]<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;x, *_ = np.linalg.lstsq(H, -g, rcond=None)<br>
&#9;&#9;&#9;λ = np.zeros(0, dtype=H.dtype)<br>
<br>
&#9;return x, λ<br>
<br>
<br>
<br>
def solve_qp_active_set(<br>
&#9;H: np.ndarray,<br>
&#9;g: np.ndarray,<br>
&#9;A_eq: np.ndarray,<br>
&#9;b_eq: np.ndarray,<br>
&#9;C: np.ndarray,<br>
&#9;d: np.ndarray,<br>
&#9;x0: Optional[np.ndarray] = None,<br>
&#9;active0: Optional[np.ndarray] = None,<br>
&#9;max_iter: int = 50,<br>
&#9;tol: float = 1e-7,<br>
&#9;active_tol: float = 1e-6,<br>
) -&gt; Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, int]:<br>
&#9;&quot;&quot;&quot;<br>
&#9;Active-set решатель для задачи:<br>
<br>
&#9;&#9;min  1/2 x^T H x + g^T x                        | x: (n,)<br>
&#9;&#9;s.t. A_eq x = b_eq                              | A_eq: (m_eq×n), b_eq: (m_eq,)<br>
&#9;&#9;&#9;C x &lt;= d                                   | C: (m_ineq×n), d: (m_ineq,)<br>
<br>
&#9;Параметры:<br>
&#9;&#9;H, g        – квадратичный функционал.          | H: (n×n), g: (n,)<br>
&#9;&#9;A_eq, b_eq  – равенства.                        | A_eq: (m_eq×n), b_eq: (m_eq,)<br>
&#9;&#9;C, d        – неравенства.                      | C: (m_ineq×n), d: (m_ineq,)<br>
&#9;&#9;x0          – warm-start по x.                  | x0: (n,)<br>
&#9;&#9;active0     – warm-start по активному множеству.| active0: (k,)<br>
&#9;&#9;max_iter    – максимум итераций.<br>
&#9;&#9;tol         – допуск ККТ.<br>
&#9;&#9;active_tol  – допуск при восстановлении active-set из x0.<br>
<br>
&#9;Возвращает:<br>
&#9;&#9;x           – решение.                          | (n,)<br>
&#9;&#9;lam_eq      – множители равенств.               | (m_eq,)<br>
&#9;&#9;lam_ineq    – множители активных неравенств.    | (k,)<br>
&#9;&#9;active_set  – индексы активных ограничений.     | (k,)<br>
&#9;&#9;iters       – количество итераций.              | int<br>
&#9;&quot;&quot;&quot;<br>
&#9;n = H.shape[0]<br>
&#9;m_ineq = C.shape[0]<br>
<br>
&#9;# ------------------------------------------------------------<br>
&#9;# Инициализация x<br>
&#9;# ------------------------------------------------------------<br>
&#9;x = np.zeros(n) if x0 is None else x0.copy()<br>
<br>
&#9;# ------------------------------------------------------------<br>
&#9;# Инициализация active-set<br>
&#9;# ------------------------------------------------------------<br>
&#9;active: List[int] = []<br>
<br>
&#9;# 1) Если есть active0 — он главный (сохраняем порядок, убираем дубли)<br>
&#9;if active0 is not None:<br>
&#9;&#9;for idx in active0:<br>
&#9;&#9;&#9;idx = int(idx)<br>
&#9;&#9;&#9;if 0 &lt;= idx &lt; m_ineq and idx not in active:<br>
&#9;&#9;&#9;&#9;active.append(idx)<br>
<br>
&#9;# 2) Если active0 нет, но есть x0 — пробуем восстановить из C @ x0 ≈ d<br>
&#9;elif x0 is not None and m_ineq &gt; 0:<br>
&#9;&#9;viol0 = C @ x0 - d<br>
&#9;&#9;for i in range(m_ineq):<br>
&#9;&#9;&#9;if abs(viol0[i]) &lt;= active_tol:<br>
&#9;&#9;&#9;&#9;active.append(i)<br>
<br>
&#9;# 3) Иначе — начинаем с пустого active-set<br>
&#9;# (ничего делать не надо, active и так пуст)<br>
<br>
&#9;# ------------------------------------------------------------<br>
&#9;# Основной цикл коррекции active-set<br>
&#9;# ------------------------------------------------------------<br>
&#9;iters = 0<br>
<br>
&#9;for it in range(max_iter):<br>
&#9;&#9;iters = it + 1<br>
<br>
&#9;&#9;# --- 1. Формируем матрицу активных равенств ---<br>
&#9;&#9;if active:<br>
&#9;&#9;&#9;A_act = np.vstack([A_eq, C[active]])<br>
&#9;&#9;&#9;b_act = np.concatenate([b_eq, d[active]])<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;A_act = A_eq<br>
&#9;&#9;&#9;b_act = b_eq<br>
<br>
&#9;&#9;# --- 2. Решаем подзадачу равенств ---<br>
&#9;&#9;x, lam_all = solve_qp_equalities(H, g, A_act, b_act)<br>
<br>
&#9;&#9;# --- 3. Разбираем множители Лагранжа ---<br>
&#9;&#9;n_eq = A_eq.shape[0]<br>
&#9;&#9;lam_eq = lam_all[:n_eq]<br>
&#9;&#9;lam_ineq = lam_all[n_eq:]  # соответствует active[0], active[1], ...<br>
<br>
&#9;&#9;# --- 4. Ищем нарушенные неравенства ---<br>
&#9;&#9;if m_ineq &gt; 0:<br>
&#9;&#9;&#9;violations = C @ x - d<br>
&#9;&#9;&#9;candidates = [<br>
&#9;&#9;&#9;&#9;i for i in range(m_ineq)<br>
&#9;&#9;&#9;&#9;if (violations[i] &gt; tol) and (i not in active)<br>
&#9;&#9;&#9;]<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;candidates = []<br>
<br>
&#9;&#9;if candidates:<br>
&#9;&#9;&#9;# Добавляем самое сильно нарушенное (защита от дублей встроена)<br>
&#9;&#9;&#9;worst = max(candidates, key=lambda i: violations[i])<br>
&#9;&#9;&#9;active.append(worst)<br>
&#9;&#9;&#9;continue  # повторяем итерацию с новым active-set<br>
<br>
&#9;&#9;# --- 5. Проверяем λ на активных ---<br>
&#9;&#9;to_remove = []<br>
&#9;&#9;for j, idx in enumerate(active):<br>
&#9;&#9;&#9;if lam_ineq[j] &lt; -tol:<br>
&#9;&#9;&#9;&#9;to_remove.append(idx)<br>
<br>
&#9;&#9;if to_remove:<br>
&#9;&#9;&#9;# Убираем все ограничения, нарушающие условия ККТ<br>
&#9;&#9;&#9;active = [i for i in active if i not in to_remove]<br>
&#9;&#9;&#9;continue  # повторяем итерацию<br>
<br>
&#9;&#9;# --- 6. ККТ выполнены, нарушений нет, λ &gt;= 0 — готово ---<br>
&#9;&#9;break<br>
<br>
&#9;# ------------------------------------------------------------<br>
&#9;# Финал: отдаём только λ для активных ограничений в корректном порядке<br>
&#9;# ------------------------------------------------------------<br>
&#9;lam_ineq_final = lam_ineq if (m_ineq &gt; 0 and active) else np.zeros(0)<br>
&#9;active_arr = np.array(active, dtype=int)<br>
<br>
&#9;return x, lam_eq, lam_ineq_final, active_arr, iters<br>
<!-- END SCAT CODE -->
</body>
</html>
