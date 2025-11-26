<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/robot/hqtasks.py</title>
</head>
<body>
<pre><code>
import numpy as np
from typing import Optional

from .hqsolver import QuadraticTask, EqualityConstraint, InequalityConstraint


def _prepare_weight(weight: Optional[np.ndarray], rows: int) -&gt; Optional[np.ndarray]:
    if weight is None:
        return None
    W = np.asarray(weight, dtype=float)
    if W.ndim == 1:
        if W.size != rows:
            raise ValueError(&quot;Weight vector size must match the task dimension.&quot;)
        return np.diag(W)
    if W.shape != (rows, rows):
        raise ValueError(&quot;Weight matrix must be square with size equal to the task dimension.&quot;)
    return W


class JointTrackingTask(QuadraticTask):
    &quot;&quot;&quot;Следит за желаемыми суставными координатами.

    Минимизируется функционал
        min_x || S x - S q_ref ||_W^2,
    где x — искомые обобщённые скорости/приращения, q_ref — желаемый вектор,
    а S — матрица выбора (по умолчанию S = I). При W = diag(w) это простая
    взвешенная подстройка отдельных координат.
    &quot;&quot;&quot;

    def __init__(
        self,
        q_ref: np.ndarray,
        selection: Optional[np.ndarray] = None,
        weight: Optional[np.ndarray] = None,
    ):
        q_ref = np.asarray(q_ref, dtype=float)
        n = q_ref.size
        if selection is None:
            J = np.eye(n)
            target = q_ref
        else:
            selection = np.asarray(selection, dtype=float)
            if selection.shape[1] != n:
                raise ValueError(&quot;Selection matrix must have the same number of columns as len(q_ref).&quot;)
            J = selection
            target = selection @ q_ref

        W = _prepare_weight(weight, J.shape[0])
        super().__init__(J, target, W)


class CartesianTrackingTask(QuadraticTask):
    &quot;&quot;&quot;Типовая задача: совместить линейную/угловую скорость с целью.

    Функционал:
        min_x || J_cart x - v_des ||_W^2,
    где J_cart — пространственный Якобиан, v_des = v_ref + K e — желаемая
    скорость/скользящий вектор. Вызов принимает уже сформированные (J_cart, v_des).
    &quot;&quot;&quot;

    def __init__(
        self,
        jacobian: np.ndarray,
        desired_twist: np.ndarray,
        weight: Optional[np.ndarray] = None,
    ):
        jacobian = np.asarray(jacobian, dtype=float)
        desired_twist = np.asarray(desired_twist, dtype=float)
        if jacobian.shape[0] != desired_twist.size:
            raise ValueError(&quot;Jacobian rows must match the size of desired_twist.&quot;)
        W = _prepare_weight(weight, jacobian.shape[0])
        super().__init__(jacobian, desired_twist, W)


class JointEqualityConstraint(EqualityConstraint):
    &quot;&quot;&quot;Фиксирует отдельные суставы: S x = S q_target.

    Это линейное равенство с матрицей S (по умолчанию I).
    &quot;&quot;&quot;

    def __init__(self, q_target: np.ndarray, selection: Optional[np.ndarray] = None):
        q_target = np.asarray(q_target, dtype=float)
        n = q_target.size
        if selection is None:
            A = np.eye(n)
            b = q_target
        else:
            selection = np.asarray(selection, dtype=float)
            if selection.shape[1] != n:
                raise ValueError(&quot;Selection matrix must have the same number of columns as len(q_target).&quot;)
            A = selection
            b = selection @ q_target

        super().__init__(A, b)


class CartesianEqualityConstraint(EqualityConstraint):
    &quot;&quot;&quot;Жёсткая задача J x = rhs для контактов или привязки инструмента.&quot;&quot;&quot;

    def __init__(self, jacobian: np.ndarray, rhs: np.ndarray):
        super().__init__(jacobian, rhs)


class JointBoundsConstraint(InequalityConstraint):
    &quot;&quot;&quot;Задаёт ограничения вида lower ≤ x ≤ upper (возможно односторонние).

    Преобразуется к стандартной форме C x ≤ d:
        x ≤ upper  →  [ I] x ≤ upper
       -x ≤ -lower → [-I] x ≤ -lower.
    &quot;&quot;&quot;

    def __init__(self, lower: Optional[np.ndarray] = None, upper: Optional[np.ndarray] = None):
        if lower is None and upper is None:
            raise ValueError(&quot;At least one of lower/upper bounds must be provided.&quot;)

        rows = []
        rhs_parts = []

        n: Optional[int] = None

        if upper is not None:
            upper = np.asarray(upper, dtype=float)
            n = upper.size
            rows.append(np.eye(n))
            rhs_parts.append(upper)

        if lower is not None:
            lower = np.asarray(lower, dtype=float)
            if n is None:
                n = lower.size
            if lower.size != n:
                raise ValueError(&quot;Lower/upper bounds must have the same length.&quot;)
            rows.append(-np.eye(n))
            rhs_parts.append(-lower)

        assert n is not None
        C = np.vstack(rows)
        d = np.concatenate(rhs_parts)
        super().__init__(C, d)


class JointVelocityDampingTask(QuadraticTask):
    &quot;&quot;&quot;Сглаживает управление, минимизируя норму суставных скоростей.&quot;&quot;&quot;

    def __init__(self, n_dofs: int, weight: Optional[np.ndarray] = None):
        if n_dofs &lt;= 0:
            raise ValueError(&quot;n_dofs must be positive.&quot;)
        J = np.eye(n_dofs)
        v = np.zeros(n_dofs)
        W = _prepare_weight(weight, n_dofs)
        super().__init__(J, v, W)


class JointPositionBoundsConstraint(InequalityConstraint):
    &quot;&quot;&quot;Гарантирует, что q + dt * dq останется в [lower, upper].&quot;&quot;&quot;

    def __init__(
        self,
        q_current: np.ndarray,
        lower: Optional[np.ndarray] = None,
        upper: Optional[np.ndarray] = None,
        dt: float = 1.0,
    ):

        if dt &lt;= 0.0:
            raise ValueError(&quot;dt must be positive.&quot;)
        q_current = np.asarray(q_current, dtype=float)
        n = q_current.size
        if lower is None and upper is None:
            raise ValueError(&quot;At least one of lower/upper bounds must be provided.&quot;)

        rows = []
        rhs = []

        if upper is not None:
            upper = np.asarray(upper, dtype=float)
            if upper.size != n:
                raise ValueError(&quot;upper must have same length as q_current.&quot;)
            rows.append(np.eye(n) * dt)
            rhs.append(upper - q_current)

        if lower is not None:
            lower = np.asarray(lower, dtype=float)
            if lower.size != n:
                raise ValueError(&quot;lower must have same length as q_current.&quot;)
            rows.append(-np.eye(n) * dt)
            rhs.append(q_current - lower)

        C = np.vstack(rows)
        d = np.concatenate(rhs)
        super().__init__(C, d)


def build_joint_soft_limit_task(
    q_current: np.ndarray,
    lower: Optional[np.ndarray],
    upper: Optional[np.ndarray],
    margin: float,
    gain: float,
) -&gt; Optional[QuadraticTask]:
    &quot;&quot;&quot;Возвращает QuadraticTask, отталкивающий суставы от мягких зон.&quot;&quot;&quot;

    if margin &lt;= 0 or gain &lt;= 0:
        return None

    q_current = np.asarray(q_current, dtype=float)
    n = q_current.size

    upper_arr = np.asarray(upper, dtype=float) if upper is not None else None
    lower_arr = np.asarray(lower, dtype=float) if lower is not None else None

    rows = []
    targets = []

    def _push(amount: float) -&gt; float:
        phase = min(max(amount / margin, 0.0), 1.0)
        return gain * phase

    for idx in range(n):
        coord = q_current[idx]
        desired = 0.0
        active = False

        if upper_arr is not None:
            boundary = upper_arr[idx]
            trigger = boundary - margin
            if coord &gt; trigger:
                desired -= _push(coord - trigger)
                active = True

        if lower_arr is not None:
            boundary = lower_arr[idx]
            trigger = boundary + margin
            if coord &lt; trigger:
                desired += _push(trigger - coord)
                active = True

        if active:
            row = np.zeros(n)
            row[idx] = 1.0
            rows.append(row)
            targets.append(desired)

    if not rows:
        return None

    J = np.vstack(rows)
    v = np.array(targets, dtype=float)
    return QuadraticTask(J, v)

</code></pre>
</body>
</html>
