<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/robot/hqsolver.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
import numpy as np<br>
from typing import List, Optional, Tuple<br>
from termin.linalg.solve import solve_qp_active_set<br>
from termin.linalg.subspaces import nullspace_basis_qr<br>
<br>
<br>
# ========= ТИПЫ ЗАДАЧ ================================================<br>
<br>
class QuadraticTask:<br>
&#9;&quot;&quot;&quot;<br>
&#9;Задача вида:<br>
&#9;&#9;min || J x - v ||_W^2<br>
<br>
&#9;Дает:<br>
&#9;&#9;H = J^T W J<br>
&#9;&#9;g = -J^T W v<br>
&#9;&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self, J: np.ndarray, v: np.ndarray, W: Optional[np.ndarray] = None):<br>
&#9;&#9;self.J = J.copy()<br>
&#9;&#9;self.v = v.copy()<br>
&#9;&#9;self.W = np.eye(J.shape[0]) if W is None else W.copy()<br>
<br>
&#9;def build_H_g(self) -&gt; Tuple[np.ndarray, np.ndarray]:<br>
&#9;&#9;H = self.J.T @ self.W @ self.J<br>
&#9;&#9;g = -self.J.T @ self.W @ self.v<br>
&#9;&#9;return H, g<br>
<br>
<br>
class EqualityConstraint:<br>
&#9;&quot;&quot;&quot;<br>
&#9;Жёсткое равенство A x = b<br>
&#9;&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self, A: np.ndarray, b: np.ndarray):<br>
&#9;&#9;self.A = A.copy()<br>
&#9;&#9;self.b = b.copy()<br>
<br>
<br>
class InequalityConstraint:<br>
&#9;&quot;&quot;&quot;<br>
&#9;Неравенство C x &lt;= d<br>
&#9;&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self, C: np.ndarray, d: np.ndarray):<br>
&#9;&#9;self.C = C.copy()<br>
&#9;&#9;self.d = d.copy()<br>
<br>
<br>
# ========= УРОВЕНЬ HQP ===============================================<br>
<br>
class Level:<br>
&#9;def __init__(self, priority: int):<br>
&#9;&#9;self.priority = priority<br>
&#9;&#9;self.tasks: List[QuadraticTask] = []<br>
&#9;&#9;self.equalities: List[EqualityConstraint] = []<br>
&#9;&#9;self.inequalities: List[InequalityConstraint] = []<br>
<br>
&#9;def add_task(self, task: QuadraticTask):<br>
&#9;&#9;self.tasks.append(task)<br>
<br>
&#9;def add_equality(self, eq: EqualityConstraint):<br>
&#9;&#9;self.equalities.append(eq)<br>
<br>
&#9;def add_inequality(self, ineq: InequalityConstraint):<br>
&#9;&#9;self.inequalities.append(ineq)<br>
<br>
&#9;def build_qp(self, n_vars: int):<br>
&#9;&#9;&quot;&quot;&quot; Формируем агрегированную задачу уровня:<br>
<br>
&#9;&#9;&#9;min_x ½ <br>
&#9;&#9;&#9;&#9;x^T H x + g^T x  <br>
&#9;&#9;&#9;<br>
&#9;&#9;&#9;при <br>
&#9;&#9;&#9;&#9;A_eq x = b_eq,  C x ≤ d,<br>
&#9;&#9;&#9;где <br>
&#9;&#9;&#9;&#9;H = Σ_i J_i^T W_i J_i и g = Σ_i (-J_i^T W_i v_i). <br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;H = np.zeros((n_vars, n_vars))<br>
&#9;&#9;g = np.zeros(n_vars)<br>
&#9;&#9;if self.tasks:<br>
&#9;&#9;&#9;J_stack = np.vstack([t.J for t in self.tasks])<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;J_stack = np.zeros((0, n_vars))<br>
<br>
&#9;&#9;for t in self.tasks:<br>
&#9;&#9;&#9;H_t, g_t = t.build_H_g()<br>
&#9;&#9;&#9;H += H_t<br>
&#9;&#9;&#9;g += g_t<br>
<br>
&#9;&#9;if self.equalities:<br>
&#9;&#9;&#9;A_eq = np.vstack([e.A for e in self.equalities])<br>
&#9;&#9;&#9;b_eq = np.concatenate([e.b for e in self.equalities])<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;A_eq = np.zeros((0, n_vars))<br>
&#9;&#9;&#9;b_eq = np.zeros(0)<br>
<br>
&#9;&#9;if self.inequalities:<br>
&#9;&#9;&#9;C = np.vstack([c.C for c in self.inequalities])<br>
&#9;&#9;&#9;d = np.concatenate([c.d for c in self.inequalities])<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;C = np.zeros((0, n_vars))<br>
&#9;&#9;&#9;d = np.zeros(0)<br>
<br>
&#9;&#9;return H, g, A_eq, b_eq, C, d, J_stack<br>
<br>
<br>
# ========= ИЕРАРХИЧЕСКИЙ РЕШАТЕЛЬ ===================================<br>
<br>
class HQPSolver:<br>
&#9;def __init__(self, n_vars: int):<br>
&#9;&#9;self.n_vars = n_vars<br>
&#9;&#9;self.levels: List[Level] = []<br>
<br>
&#9;def add_level(self, level: Level):<br>
&#9;&#9;self.levels.append(level)<br>
&#9;&#9;self.levels.sort(key=lambda L: L.priority)<br>
<br>
&#9;@staticmethod<br>
&#9;def _transform_qp_to_nullspace(H, g, A_eq, b_eq, C, d, x_base, N):<br>
&#9;&#9;H_z = N.T @ H @ N<br>
&#9;&#9;g_z = N.T @ (H @ x_base + g)<br>
<br>
&#9;&#9;if A_eq.size &gt; 0:<br>
&#9;&#9;&#9;A_eq_z = A_eq @ N<br>
&#9;&#9;&#9;b_eq_z = b_eq - A_eq @ x_base<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;A_eq_z = np.zeros((0, N.shape[1]))<br>
&#9;&#9;&#9;b_eq_z = np.zeros(0)<br>
<br>
&#9;&#9;if C.size &gt; 0:<br>
&#9;&#9;&#9;C_z = C @ N<br>
&#9;&#9;&#9;d_z = d - C @ x_base<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;C_z = np.zeros((0, N.shape[1]))<br>
&#9;&#9;&#9;d_z = np.zeros(0)<br>
<br>
&#9;&#9;return H_z, g_z, A_eq_z, b_eq_z, C_z, d_z<br>
<br>
&#9;def solve(self, x0: Optional[np.ndarray] = None) -&gt; np.ndarray:<br>
&#9;&#9;n = self.n_vars<br>
&#9;&#9;x = np.zeros(n) if x0 is None else x0.copy()<br>
&#9;&#9;N = np.eye(n)  # Базис допустимых направлений после предыдущих уровней (изначально всё пространство)<br>
<br>
&#9;&#9;for level in self.levels:<br>
&#9;&#9;&#9;H, g, A_eq, b_eq, C, d, J_stack = level.build_qp(n)<br>
<br>
&#9;&#9;&#9;if N.shape[1] == 0:<br>
&#9;&#9;&#9;&#9;break  # Нет свободных степеней: последующие уровни ничего не добавят<br>
<br>
&#9;&#9;&#9;# Проецируем текущий QP в координаты z, живущие в столбцовом пространстве N.<br>
&#9;&#9;&#9;H_z, g_z, A_eq_z, b_eq_z, C_z, d_z = self._transform_qp_to_nullspace(<br>
&#9;&#9;&#9;&#9;H, g, A_eq, b_eq, C, d, x, N<br>
&#9;&#9;&#9;)<br>
<br>
&#9;&#9;&#9;# Решаем QP текущего уровня в координатах z.<br>
&#9;&#9;&#9;z, lam_eq, lam_ineq, active_set, iters = solve_qp_active_set(<br>
&#9;&#9;&#9;&#9;H_z, g_z, A_eq_z, b_eq_z, C_z, d_z,<br>
&#9;&#9;&#9;&#9;x0=None, active0=None<br>
&#9;&#9;&#9;)<br>
<br>
&#9;&#9;&#9;# Возвращаемся в исходное пространство: x ← x + N z.<br>
&#9;&#9;&#9;x = x + N @ z<br>
<br>
&#9;&#9;&#9;grad = H @ x + g  # Градиент уровня нужен, чтобы закрепить найденное решение при переходе выше.<br>
<br>
&#9;&#9;&#9;# Формируем совокупный якобиан ограничений текущего уровня,<br>
&#9;&#9;&#9;# действующих внутри текущего nullspace.<br>
&#9;&#9;&#9;J_prior_blocks = []<br>
&#9;&#9;&#9;if A_eq.size &gt; 0:<br>
&#9;&#9;&#9;&#9;J_prior_blocks.append(A_eq)<br>
&#9;&#9;&#9;if J_stack.size &gt; 0:<br>
&#9;&#9;&#9;&#9;J_prior_blocks.append(J_stack)<br>
&#9;&#9;&#9;if np.linalg.norm(grad) &gt; 1e-12:<br>
&#9;&#9;&#9;&#9;J_prior_blocks.append(grad[None, :])<br>
&#9;&#9;&#9;if J_prior_blocks:<br>
&#9;&#9;&#9;&#9;J_prior = np.vstack(J_prior_blocks)<br>
&#9;&#9;&#9;else:<br>
&#9;&#9;&#9;&#9;J_prior = np.zeros((0, n))<br>
<br>
&#9;&#9;&#9;if J_prior.size &gt; 0 and N.shape[1] &gt; 0:<br>
&#9;&#9;&#9;&#9;A_red = J_prior @ N<br>
&#9;&#9;&#9;&#9;# Столбцы nullspace_basis_qr(A_red) образуют базис ker(A_red) = V⊥,<br>
&#9;&#9;&#9;&#9;# где V = rowspace(A_red) — ограничения текущего уровня внутри подпространства N.<br>
&#9;&#9;&#9;&#9;N_red = nullspace_basis_qr(A_red)<br>
&#9;&#9;&#9;&#9;# Обновляем глобальный базис допустимых направлений: следующий уровень живёт в подпространстве N @ N_red.<br>
&#9;&#9;&#9;&#9;N = N @ N_red<br>
<br>
&#9;&#9;return x<br>
<!-- END SCAT CODE -->
</body>
</html>
