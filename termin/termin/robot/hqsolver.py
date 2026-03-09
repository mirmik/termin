import numpy as np
from typing import List, Optional, Tuple
from termin.linalg.solve import solve_qp_active_set
from termin.linalg.subspaces import nullspace_basis_qr


# ========= ТИПЫ ЗАДАЧ ================================================

class QuadraticTask:
    """
    Задача вида:
        min || J x - v ||_W^2

    Дает:
        H = J^T W J
        g = -J^T W v
    """

    def __init__(self, J: np.ndarray, v: np.ndarray, W: Optional[np.ndarray] = None):
        self.J = J.copy()
        self.v = v.copy()
        self.W = np.eye(J.shape[0]) if W is None else W.copy()

    def build_H_g(self) -> Tuple[np.ndarray, np.ndarray]:
        H = self.J.T @ self.W @ self.J
        g = -self.J.T @ self.W @ self.v
        return H, g


class EqualityConstraint:
    """
    Жёсткое равенство A x = b
    """

    def __init__(self, A: np.ndarray, b: np.ndarray):
        self.A = A.copy()
        self.b = b.copy()


class InequalityConstraint:
    """
    Неравенство C x <= d
    """

    def __init__(self, C: np.ndarray, d: np.ndarray):
        self.C = C.copy()
        self.d = d.copy()


# ========= УРОВЕНЬ HQP ===============================================

class Level:
    def __init__(self, priority: int):
        self.priority = priority
        self.tasks: List[QuadraticTask] = []
        self.equalities: List[EqualityConstraint] = []
        self.inequalities: List[InequalityConstraint] = []

    def add_task(self, task: QuadraticTask):
        self.tasks.append(task)

    def add_equality(self, eq: EqualityConstraint):
        self.equalities.append(eq)

    def add_inequality(self, ineq: InequalityConstraint):
        self.inequalities.append(ineq)

    def build_qp(self, n_vars: int):
        """ Формируем агрегированную задачу уровня:

            min_x ½ 
                x^T H x + g^T x  
            
            при 
                A_eq x = b_eq,  C x ≤ d,
            где 
                H = Σ_i J_i^T W_i J_i и g = Σ_i (-J_i^T W_i v_i). 
         """
        H = np.zeros((n_vars, n_vars))
        g = np.zeros(n_vars)
        if self.tasks:
            J_stack = np.vstack([t.J for t in self.tasks])
        else:
            J_stack = np.zeros((0, n_vars))

        for t in self.tasks:
            H_t, g_t = t.build_H_g()
            H += H_t
            g += g_t

        if self.equalities:
            A_eq = np.vstack([e.A for e in self.equalities])
            b_eq = np.concatenate([e.b for e in self.equalities])
        else:
            A_eq = np.zeros((0, n_vars))
            b_eq = np.zeros(0)

        if self.inequalities:
            C = np.vstack([c.C for c in self.inequalities])
            d = np.concatenate([c.d for c in self.inequalities])
        else:
            C = np.zeros((0, n_vars))
            d = np.zeros(0)

        return H, g, A_eq, b_eq, C, d, J_stack


# ========= ИЕРАРХИЧЕСКИЙ РЕШАТЕЛЬ ===================================

class HQPSolver:
    def __init__(self, n_vars: int):
        self.n_vars = n_vars
        self.levels: List[Level] = []

    def add_level(self, level: Level):
        self.levels.append(level)
        self.levels.sort(key=lambda L: L.priority)

    @staticmethod
    def _transform_qp_to_nullspace(H, g, A_eq, b_eq, C, d, x_base, N):
        H_z = N.T @ H @ N
        g_z = N.T @ (H @ x_base + g)

        if A_eq.size > 0:
            A_eq_z = A_eq @ N
            b_eq_z = b_eq - A_eq @ x_base
        else:
            A_eq_z = np.zeros((0, N.shape[1]))
            b_eq_z = np.zeros(0)

        if C.size > 0:
            C_z = C @ N
            d_z = d - C @ x_base
        else:
            C_z = np.zeros((0, N.shape[1]))
            d_z = np.zeros(0)

        return H_z, g_z, A_eq_z, b_eq_z, C_z, d_z

    def solve(self, x0: Optional[np.ndarray] = None) -> np.ndarray:
        n = self.n_vars
        x = np.zeros(n) if x0 is None else x0.copy()
        N = np.eye(n)  # Базис допустимых направлений после предыдущих уровней (изначально всё пространство)

        for level in self.levels:
            H, g, A_eq, b_eq, C, d, J_stack = level.build_qp(n)

            if N.shape[1] == 0:
                break  # Нет свободных степеней: последующие уровни ничего не добавят

            # Проецируем текущий QP в координаты z, живущие в столбцовом пространстве N.
            H_z, g_z, A_eq_z, b_eq_z, C_z, d_z = self._transform_qp_to_nullspace(
                H, g, A_eq, b_eq, C, d, x, N
            )

            # Решаем QP текущего уровня в координатах z.
            z, lam_eq, lam_ineq, active_set, iters = solve_qp_active_set(
                H_z, g_z, A_eq_z, b_eq_z, C_z, d_z,
                x0=None, active0=None
            )

            # Возвращаемся в исходное пространство: x ← x + N z.
            x = x + N @ z

            grad = H @ x + g  # Градиент уровня нужен, чтобы закрепить найденное решение при переходе выше.

            # Формируем совокупный якобиан ограничений текущего уровня,
            # действующих внутри текущего nullspace.
            J_prior_blocks = []
            if A_eq.size > 0:
                J_prior_blocks.append(A_eq)
            if J_stack.size > 0:
                J_prior_blocks.append(J_stack)
            if np.linalg.norm(grad) > 1e-12:
                J_prior_blocks.append(grad[None, :])
            if J_prior_blocks:
                J_prior = np.vstack(J_prior_blocks)
            else:
                J_prior = np.zeros((0, n))

            if J_prior.size > 0 and N.shape[1] > 0:
                A_red = J_prior @ N
                # Столбцы nullspace_basis_qr(A_red) образуют базис ker(A_red) = V⊥,
                # где V = rowspace(A_red) — ограничения текущего уровня внутри подпространства N.
                N_red = nullspace_basis_qr(A_red)
                # Обновляем глобальный базис допустимых направлений: следующий уровень живёт в подпространстве N @ N_red.
                N = N @ N_red

        return x
