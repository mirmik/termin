<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/robot/hqtasks.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
import numpy as np<br>
from typing import Optional<br>
<br>
from .hqsolver import QuadraticTask, EqualityConstraint, InequalityConstraint<br>
<br>
<br>
def _prepare_weight(weight: Optional[np.ndarray], rows: int) -&gt; Optional[np.ndarray]:<br>
    if weight is None:<br>
        return None<br>
    W = np.asarray(weight, dtype=float)<br>
    if W.ndim == 1:<br>
        if W.size != rows:<br>
            raise ValueError(&quot;Weight vector size must match the task dimension.&quot;)<br>
        return np.diag(W)<br>
    if W.shape != (rows, rows):<br>
        raise ValueError(&quot;Weight matrix must be square with size equal to the task dimension.&quot;)<br>
    return W<br>
<br>
<br>
class JointTrackingTask(QuadraticTask):<br>
    &quot;&quot;&quot;Следит за желаемыми суставными координатами.<br>
<br>
    Минимизируется функционал<br>
        min_x || S x - S q_ref ||_W^2,<br>
    где x — искомые обобщённые скорости/приращения, q_ref — желаемый вектор,<br>
    а S — матрица выбора (по умолчанию S = I). При W = diag(w) это простая<br>
    взвешенная подстройка отдельных координат.<br>
    &quot;&quot;&quot;<br>
<br>
    def __init__(<br>
        self,<br>
        q_ref: np.ndarray,<br>
        selection: Optional[np.ndarray] = None,<br>
        weight: Optional[np.ndarray] = None,<br>
    ):<br>
        q_ref = np.asarray(q_ref, dtype=float)<br>
        n = q_ref.size<br>
        if selection is None:<br>
            J = np.eye(n)<br>
            target = q_ref<br>
        else:<br>
            selection = np.asarray(selection, dtype=float)<br>
            if selection.shape[1] != n:<br>
                raise ValueError(&quot;Selection matrix must have the same number of columns as len(q_ref).&quot;)<br>
            J = selection<br>
            target = selection @ q_ref<br>
<br>
        W = _prepare_weight(weight, J.shape[0])<br>
        super().__init__(J, target, W)<br>
<br>
<br>
class CartesianTrackingTask(QuadraticTask):<br>
    &quot;&quot;&quot;Типовая задача: совместить линейную/угловую скорость с целью.<br>
<br>
    Функционал:<br>
        min_x || J_cart x - v_des ||_W^2,<br>
    где J_cart — пространственный Якобиан, v_des = v_ref + K e — желаемая<br>
    скорость/скользящий вектор. Вызов принимает уже сформированные (J_cart, v_des).<br>
    &quot;&quot;&quot;<br>
<br>
    def __init__(<br>
        self,<br>
        jacobian: np.ndarray,<br>
        desired_twist: np.ndarray,<br>
        weight: Optional[np.ndarray] = None,<br>
    ):<br>
        jacobian = np.asarray(jacobian, dtype=float)<br>
        desired_twist = np.asarray(desired_twist, dtype=float)<br>
        if jacobian.shape[0] != desired_twist.size:<br>
            raise ValueError(&quot;Jacobian rows must match the size of desired_twist.&quot;)<br>
        W = _prepare_weight(weight, jacobian.shape[0])<br>
        super().__init__(jacobian, desired_twist, W)<br>
<br>
<br>
class JointEqualityConstraint(EqualityConstraint):<br>
    &quot;&quot;&quot;Фиксирует отдельные суставы: S x = S q_target.<br>
<br>
    Это линейное равенство с матрицей S (по умолчанию I).<br>
    &quot;&quot;&quot;<br>
<br>
    def __init__(self, q_target: np.ndarray, selection: Optional[np.ndarray] = None):<br>
        q_target = np.asarray(q_target, dtype=float)<br>
        n = q_target.size<br>
        if selection is None:<br>
            A = np.eye(n)<br>
            b = q_target<br>
        else:<br>
            selection = np.asarray(selection, dtype=float)<br>
            if selection.shape[1] != n:<br>
                raise ValueError(&quot;Selection matrix must have the same number of columns as len(q_target).&quot;)<br>
            A = selection<br>
            b = selection @ q_target<br>
<br>
        super().__init__(A, b)<br>
<br>
<br>
class CartesianEqualityConstraint(EqualityConstraint):<br>
    &quot;&quot;&quot;Жёсткая задача J x = rhs для контактов или привязки инструмента.&quot;&quot;&quot;<br>
<br>
    def __init__(self, jacobian: np.ndarray, rhs: np.ndarray):<br>
        super().__init__(jacobian, rhs)<br>
<br>
<br>
class JointBoundsConstraint(InequalityConstraint):<br>
    &quot;&quot;&quot;Задаёт ограничения вида lower ≤ x ≤ upper (возможно односторонние).<br>
<br>
    Преобразуется к стандартной форме C x ≤ d:<br>
        x ≤ upper  →  [ I] x ≤ upper<br>
       -x ≤ -lower → [-I] x ≤ -lower.<br>
    &quot;&quot;&quot;<br>
<br>
    def __init__(self, lower: Optional[np.ndarray] = None, upper: Optional[np.ndarray] = None):<br>
        if lower is None and upper is None:<br>
            raise ValueError(&quot;At least one of lower/upper bounds must be provided.&quot;)<br>
<br>
        rows = []<br>
        rhs_parts = []<br>
<br>
        n: Optional[int] = None<br>
<br>
        if upper is not None:<br>
            upper = np.asarray(upper, dtype=float)<br>
            n = upper.size<br>
            rows.append(np.eye(n))<br>
            rhs_parts.append(upper)<br>
<br>
        if lower is not None:<br>
            lower = np.asarray(lower, dtype=float)<br>
            if n is None:<br>
                n = lower.size<br>
            if lower.size != n:<br>
                raise ValueError(&quot;Lower/upper bounds must have the same length.&quot;)<br>
            rows.append(-np.eye(n))<br>
            rhs_parts.append(-lower)<br>
<br>
        assert n is not None<br>
        C = np.vstack(rows)<br>
        d = np.concatenate(rhs_parts)<br>
        super().__init__(C, d)<br>
<br>
<br>
class JointVelocityDampingTask(QuadraticTask):<br>
    &quot;&quot;&quot;Сглаживает управление, минимизируя норму суставных скоростей.&quot;&quot;&quot;<br>
<br>
    def __init__(self, n_dofs: int, weight: Optional[np.ndarray] = None):<br>
        if n_dofs &lt;= 0:<br>
            raise ValueError(&quot;n_dofs must be positive.&quot;)<br>
        J = np.eye(n_dofs)<br>
        v = np.zeros(n_dofs)<br>
        W = _prepare_weight(weight, n_dofs)<br>
        super().__init__(J, v, W)<br>
<br>
<br>
class JointPositionBoundsConstraint(InequalityConstraint):<br>
    &quot;&quot;&quot;Гарантирует, что q + dt * dq останется в [lower, upper].&quot;&quot;&quot;<br>
<br>
    def __init__(<br>
        self,<br>
        q_current: np.ndarray,<br>
        lower: Optional[np.ndarray] = None,<br>
        upper: Optional[np.ndarray] = None,<br>
        dt: float = 1.0,<br>
    ):<br>
<br>
        if dt &lt;= 0.0:<br>
            raise ValueError(&quot;dt must be positive.&quot;)<br>
        q_current = np.asarray(q_current, dtype=float)<br>
        n = q_current.size<br>
        if lower is None and upper is None:<br>
            raise ValueError(&quot;At least one of lower/upper bounds must be provided.&quot;)<br>
<br>
        rows = []<br>
        rhs = []<br>
<br>
        if upper is not None:<br>
            upper = np.asarray(upper, dtype=float)<br>
            if upper.size != n:<br>
                raise ValueError(&quot;upper must have same length as q_current.&quot;)<br>
            rows.append(np.eye(n) * dt)<br>
            rhs.append(upper - q_current)<br>
<br>
        if lower is not None:<br>
            lower = np.asarray(lower, dtype=float)<br>
            if lower.size != n:<br>
                raise ValueError(&quot;lower must have same length as q_current.&quot;)<br>
            rows.append(-np.eye(n) * dt)<br>
            rhs.append(q_current - lower)<br>
<br>
        C = np.vstack(rows)<br>
        d = np.concatenate(rhs)<br>
        super().__init__(C, d)<br>
<br>
<br>
def build_joint_soft_limit_task(<br>
    q_current: np.ndarray,<br>
    lower: Optional[np.ndarray],<br>
    upper: Optional[np.ndarray],<br>
    margin: float,<br>
    gain: float,<br>
) -&gt; Optional[QuadraticTask]:<br>
    &quot;&quot;&quot;Возвращает QuadraticTask, отталкивающий суставы от мягких зон.&quot;&quot;&quot;<br>
<br>
    if margin &lt;= 0 or gain &lt;= 0:<br>
        return None<br>
<br>
    q_current = np.asarray(q_current, dtype=float)<br>
    n = q_current.size<br>
<br>
    upper_arr = np.asarray(upper, dtype=float) if upper is not None else None<br>
    lower_arr = np.asarray(lower, dtype=float) if lower is not None else None<br>
<br>
    rows = []<br>
    targets = []<br>
<br>
    def _push(amount: float) -&gt; float:<br>
        phase = min(max(amount / margin, 0.0), 1.0)<br>
        return gain * phase<br>
<br>
    for idx in range(n):<br>
        coord = q_current[idx]<br>
        desired = 0.0<br>
        active = False<br>
<br>
        if upper_arr is not None:<br>
            boundary = upper_arr[idx]<br>
            trigger = boundary - margin<br>
            if coord &gt; trigger:<br>
                desired -= _push(coord - trigger)<br>
                active = True<br>
<br>
        if lower_arr is not None:<br>
            boundary = lower_arr[idx]<br>
            trigger = boundary + margin<br>
            if coord &lt; trigger:<br>
                desired += _push(trigger - coord)<br>
                active = True<br>
<br>
        if active:<br>
            row = np.zeros(n)<br>
            row[idx] = 1.0<br>
            rows.append(row)<br>
            targets.append(desired)<br>
<br>
    if not rows:<br>
        return None<br>
<br>
    J = np.vstack(rows)<br>
    v = np.array(targets, dtype=float)<br>
    return QuadraticTask(J, v)<br>
<!-- END SCAT CODE -->
</body>
</html>
