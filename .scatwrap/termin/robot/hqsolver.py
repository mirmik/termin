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
    &quot;&quot;&quot;<br>
    Задача вида:<br>
        min || J x - v ||_W^2<br>
<br>
    Дает:<br>
        H = J^T W J<br>
        g = -J^T W v<br>
    &quot;&quot;&quot;<br>
<br>
    def __init__(self, J: np.ndarray, v: np.ndarray, W: Optional[np.ndarray] = None):<br>
        self.J = J.copy()<br>
        self.v = v.copy()<br>
        self.W = np.eye(J.shape[0]) if W is None else W.copy()<br>
<br>
    def build_H_g(self) -&gt; Tuple[np.ndarray, np.ndarray]:<br>
        H = self.J.T @ self.W @ self.J<br>
        g = -self.J.T @ self.W @ self.v<br>
        return H, g<br>
<br>
<br>
class EqualityConstraint:<br>
    &quot;&quot;&quot;<br>
    Жёсткое равенство A x = b<br>
    &quot;&quot;&quot;<br>
<br>
    def __init__(self, A: np.ndarray, b: np.ndarray):<br>
        self.A = A.copy()<br>
        self.b = b.copy()<br>
<br>
<br>
class InequalityConstraint:<br>
    &quot;&quot;&quot;<br>
    Неравенство C x &lt;= d<br>
    &quot;&quot;&quot;<br>
<br>
    def __init__(self, C: np.ndarray, d: np.ndarray):<br>
        self.C = C.copy()<br>
        self.d = d.copy()<br>
<br>
<br>
# ========= УРОВЕНЬ HQP ===============================================<br>
<br>
class Level:<br>
    def __init__(self, priority: int):<br>
        self.priority = priority<br>
        self.tasks: List[QuadraticTask] = []<br>
        self.equalities: List[EqualityConstraint] = []<br>
        self.inequalities: List[InequalityConstraint] = []<br>
<br>
    def add_task(self, task: QuadraticTask):<br>
        self.tasks.append(task)<br>
<br>
    def add_equality(self, eq: EqualityConstraint):<br>
        self.equalities.append(eq)<br>
<br>
    def add_inequality(self, ineq: InequalityConstraint):<br>
        self.inequalities.append(ineq)<br>
<br>
    def build_qp(self, n_vars: int):<br>
        &quot;&quot;&quot; Формируем агрегированную задачу уровня:<br>
<br>
            min_x ½ <br>
                x^T H x + g^T x  <br>
            <br>
            при <br>
                A_eq x = b_eq,  C x ≤ d,<br>
            где <br>
                H = Σ_i J_i^T W_i J_i и g = Σ_i (-J_i^T W_i v_i). <br>
         &quot;&quot;&quot;<br>
        H = np.zeros((n_vars, n_vars))<br>
        g = np.zeros(n_vars)<br>
        if self.tasks:<br>
            J_stack = np.vstack([t.J for t in self.tasks])<br>
        else:<br>
            J_stack = np.zeros((0, n_vars))<br>
<br>
        for t in self.tasks:<br>
            H_t, g_t = t.build_H_g()<br>
            H += H_t<br>
            g += g_t<br>
<br>
        if self.equalities:<br>
            A_eq = np.vstack([e.A for e in self.equalities])<br>
            b_eq = np.concatenate([e.b for e in self.equalities])<br>
        else:<br>
            A_eq = np.zeros((0, n_vars))<br>
            b_eq = np.zeros(0)<br>
<br>
        if self.inequalities:<br>
            C = np.vstack([c.C for c in self.inequalities])<br>
            d = np.concatenate([c.d for c in self.inequalities])<br>
        else:<br>
            C = np.zeros((0, n_vars))<br>
            d = np.zeros(0)<br>
<br>
        return H, g, A_eq, b_eq, C, d, J_stack<br>
<br>
<br>
# ========= ИЕРАРХИЧЕСКИЙ РЕШАТЕЛЬ ===================================<br>
<br>
class HQPSolver:<br>
    def __init__(self, n_vars: int):<br>
        self.n_vars = n_vars<br>
        self.levels: List[Level] = []<br>
<br>
    def add_level(self, level: Level):<br>
        self.levels.append(level)<br>
        self.levels.sort(key=lambda L: L.priority)<br>
<br>
    @staticmethod<br>
    def _transform_qp_to_nullspace(H, g, A_eq, b_eq, C, d, x_base, N):<br>
        H_z = N.T @ H @ N<br>
        g_z = N.T @ (H @ x_base + g)<br>
<br>
        if A_eq.size &gt; 0:<br>
            A_eq_z = A_eq @ N<br>
            b_eq_z = b_eq - A_eq @ x_base<br>
        else:<br>
            A_eq_z = np.zeros((0, N.shape[1]))<br>
            b_eq_z = np.zeros(0)<br>
<br>
        if C.size &gt; 0:<br>
            C_z = C @ N<br>
            d_z = d - C @ x_base<br>
        else:<br>
            C_z = np.zeros((0, N.shape[1]))<br>
            d_z = np.zeros(0)<br>
<br>
        return H_z, g_z, A_eq_z, b_eq_z, C_z, d_z<br>
<br>
    def solve(self, x0: Optional[np.ndarray] = None) -&gt; np.ndarray:<br>
        n = self.n_vars<br>
        x = np.zeros(n) if x0 is None else x0.copy()<br>
        N = np.eye(n)  # Базис допустимых направлений после предыдущих уровней (изначально всё пространство)<br>
<br>
        for level in self.levels:<br>
            H, g, A_eq, b_eq, C, d, J_stack = level.build_qp(n)<br>
<br>
            if N.shape[1] == 0:<br>
                break  # Нет свободных степеней: последующие уровни ничего не добавят<br>
<br>
            # Проецируем текущий QP в координаты z, живущие в столбцовом пространстве N.<br>
            H_z, g_z, A_eq_z, b_eq_z, C_z, d_z = self._transform_qp_to_nullspace(<br>
                H, g, A_eq, b_eq, C, d, x, N<br>
            )<br>
<br>
            # Решаем QP текущего уровня в координатах z.<br>
            z, lam_eq, lam_ineq, active_set, iters = solve_qp_active_set(<br>
                H_z, g_z, A_eq_z, b_eq_z, C_z, d_z,<br>
                x0=None, active0=None<br>
            )<br>
<br>
            # Возвращаемся в исходное пространство: x ← x + N z.<br>
            x = x + N @ z<br>
<br>
            grad = H @ x + g  # Градиент уровня нужен, чтобы закрепить найденное решение при переходе выше.<br>
<br>
            # Формируем совокупный якобиан ограничений текущего уровня,<br>
            # действующих внутри текущего nullspace.<br>
            J_prior_blocks = []<br>
            if A_eq.size &gt; 0:<br>
                J_prior_blocks.append(A_eq)<br>
            if J_stack.size &gt; 0:<br>
                J_prior_blocks.append(J_stack)<br>
            if np.linalg.norm(grad) &gt; 1e-12:<br>
                J_prior_blocks.append(grad[None, :])<br>
            if J_prior_blocks:<br>
                J_prior = np.vstack(J_prior_blocks)<br>
            else:<br>
                J_prior = np.zeros((0, n))<br>
<br>
            if J_prior.size &gt; 0 and N.shape[1] &gt; 0:<br>
                A_red = J_prior @ N<br>
                # Столбцы nullspace_basis_qr(A_red) образуют базис ker(A_red) = V⊥,<br>
                # где V = rowspace(A_red) — ограничения текущего уровня внутри подпространства N.<br>
                N_red = nullspace_basis_qr(A_red)<br>
                # Обновляем глобальный базис допустимых направлений: следующий уровень живёт в подпространстве N @ N_red.<br>
                N = N @ N_red<br>
<br>
        return x<br>
<!-- END SCAT CODE -->
</body>
</html>
