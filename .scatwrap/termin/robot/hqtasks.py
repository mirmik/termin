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
&#9;if weight is None:<br>
&#9;&#9;return None<br>
&#9;W = np.asarray(weight, dtype=float)<br>
&#9;if W.ndim == 1:<br>
&#9;&#9;if W.size != rows:<br>
&#9;&#9;&#9;raise ValueError(&quot;Weight vector size must match the task dimension.&quot;)<br>
&#9;&#9;return np.diag(W)<br>
&#9;if W.shape != (rows, rows):<br>
&#9;&#9;raise ValueError(&quot;Weight matrix must be square with size equal to the task dimension.&quot;)<br>
&#9;return W<br>
<br>
<br>
class JointTrackingTask(QuadraticTask):<br>
&#9;&quot;&quot;&quot;Следит за желаемыми суставными координатами.<br>
<br>
&#9;Минимизируется функционал<br>
&#9;&#9;min_x || S x - S q_ref ||_W^2,<br>
&#9;где x — искомые обобщённые скорости/приращения, q_ref — желаемый вектор,<br>
&#9;а S — матрица выбора (по умолчанию S = I). При W = diag(w) это простая<br>
&#9;взвешенная подстройка отдельных координат.<br>
&#9;&quot;&quot;&quot;<br>
<br>
&#9;def __init__(<br>
&#9;&#9;self,<br>
&#9;&#9;q_ref: np.ndarray,<br>
&#9;&#9;selection: Optional[np.ndarray] = None,<br>
&#9;&#9;weight: Optional[np.ndarray] = None,<br>
&#9;):<br>
&#9;&#9;q_ref = np.asarray(q_ref, dtype=float)<br>
&#9;&#9;n = q_ref.size<br>
&#9;&#9;if selection is None:<br>
&#9;&#9;&#9;J = np.eye(n)<br>
&#9;&#9;&#9;target = q_ref<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;selection = np.asarray(selection, dtype=float)<br>
&#9;&#9;&#9;if selection.shape[1] != n:<br>
&#9;&#9;&#9;&#9;raise ValueError(&quot;Selection matrix must have the same number of columns as len(q_ref).&quot;)<br>
&#9;&#9;&#9;J = selection<br>
&#9;&#9;&#9;target = selection @ q_ref<br>
<br>
&#9;&#9;W = _prepare_weight(weight, J.shape[0])<br>
&#9;&#9;super().__init__(J, target, W)<br>
<br>
<br>
class CartesianTrackingTask(QuadraticTask):<br>
&#9;&quot;&quot;&quot;Типовая задача: совместить линейную/угловую скорость с целью.<br>
<br>
&#9;Функционал:<br>
&#9;&#9;min_x || J_cart x - v_des ||_W^2,<br>
&#9;где J_cart — пространственный Якобиан, v_des = v_ref + K e — желаемая<br>
&#9;скорость/скользящий вектор. Вызов принимает уже сформированные (J_cart, v_des).<br>
&#9;&quot;&quot;&quot;<br>
<br>
&#9;def __init__(<br>
&#9;&#9;self,<br>
&#9;&#9;jacobian: np.ndarray,<br>
&#9;&#9;desired_twist: np.ndarray,<br>
&#9;&#9;weight: Optional[np.ndarray] = None,<br>
&#9;):<br>
&#9;&#9;jacobian = np.asarray(jacobian, dtype=float)<br>
&#9;&#9;desired_twist = np.asarray(desired_twist, dtype=float)<br>
&#9;&#9;if jacobian.shape[0] != desired_twist.size:<br>
&#9;&#9;&#9;raise ValueError(&quot;Jacobian rows must match the size of desired_twist.&quot;)<br>
&#9;&#9;W = _prepare_weight(weight, jacobian.shape[0])<br>
&#9;&#9;super().__init__(jacobian, desired_twist, W)<br>
<br>
<br>
class JointEqualityConstraint(EqualityConstraint):<br>
&#9;&quot;&quot;&quot;Фиксирует отдельные суставы: S x = S q_target.<br>
<br>
&#9;Это линейное равенство с матрицей S (по умолчанию I).<br>
&#9;&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self, q_target: np.ndarray, selection: Optional[np.ndarray] = None):<br>
&#9;&#9;q_target = np.asarray(q_target, dtype=float)<br>
&#9;&#9;n = q_target.size<br>
&#9;&#9;if selection is None:<br>
&#9;&#9;&#9;A = np.eye(n)<br>
&#9;&#9;&#9;b = q_target<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;selection = np.asarray(selection, dtype=float)<br>
&#9;&#9;&#9;if selection.shape[1] != n:<br>
&#9;&#9;&#9;&#9;raise ValueError(&quot;Selection matrix must have the same number of columns as len(q_target).&quot;)<br>
&#9;&#9;&#9;A = selection<br>
&#9;&#9;&#9;b = selection @ q_target<br>
<br>
&#9;&#9;super().__init__(A, b)<br>
<br>
<br>
class CartesianEqualityConstraint(EqualityConstraint):<br>
&#9;&quot;&quot;&quot;Жёсткая задача J x = rhs для контактов или привязки инструмента.&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self, jacobian: np.ndarray, rhs: np.ndarray):<br>
&#9;&#9;super().__init__(jacobian, rhs)<br>
<br>
<br>
class JointBoundsConstraint(InequalityConstraint):<br>
&#9;&quot;&quot;&quot;Задаёт ограничения вида lower ≤ x ≤ upper (возможно односторонние).<br>
<br>
&#9;Преобразуется к стандартной форме C x ≤ d:<br>
&#9;&#9;x ≤ upper  →  [ I] x ≤ upper<br>
&#9;-x ≤ -lower → [-I] x ≤ -lower.<br>
&#9;&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self, lower: Optional[np.ndarray] = None, upper: Optional[np.ndarray] = None):<br>
&#9;&#9;if lower is None and upper is None:<br>
&#9;&#9;&#9;raise ValueError(&quot;At least one of lower/upper bounds must be provided.&quot;)<br>
<br>
&#9;&#9;rows = []<br>
&#9;&#9;rhs_parts = []<br>
<br>
&#9;&#9;n: Optional[int] = None<br>
<br>
&#9;&#9;if upper is not None:<br>
&#9;&#9;&#9;upper = np.asarray(upper, dtype=float)<br>
&#9;&#9;&#9;n = upper.size<br>
&#9;&#9;&#9;rows.append(np.eye(n))<br>
&#9;&#9;&#9;rhs_parts.append(upper)<br>
<br>
&#9;&#9;if lower is not None:<br>
&#9;&#9;&#9;lower = np.asarray(lower, dtype=float)<br>
&#9;&#9;&#9;if n is None:<br>
&#9;&#9;&#9;&#9;n = lower.size<br>
&#9;&#9;&#9;if lower.size != n:<br>
&#9;&#9;&#9;&#9;raise ValueError(&quot;Lower/upper bounds must have the same length.&quot;)<br>
&#9;&#9;&#9;rows.append(-np.eye(n))<br>
&#9;&#9;&#9;rhs_parts.append(-lower)<br>
<br>
&#9;&#9;assert n is not None<br>
&#9;&#9;C = np.vstack(rows)<br>
&#9;&#9;d = np.concatenate(rhs_parts)<br>
&#9;&#9;super().__init__(C, d)<br>
<br>
<br>
class JointVelocityDampingTask(QuadraticTask):<br>
&#9;&quot;&quot;&quot;Сглаживает управление, минимизируя норму суставных скоростей.&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self, n_dofs: int, weight: Optional[np.ndarray] = None):<br>
&#9;&#9;if n_dofs &lt;= 0:<br>
&#9;&#9;&#9;raise ValueError(&quot;n_dofs must be positive.&quot;)<br>
&#9;&#9;J = np.eye(n_dofs)<br>
&#9;&#9;v = np.zeros(n_dofs)<br>
&#9;&#9;W = _prepare_weight(weight, n_dofs)<br>
&#9;&#9;super().__init__(J, v, W)<br>
<br>
<br>
class JointPositionBoundsConstraint(InequalityConstraint):<br>
&#9;&quot;&quot;&quot;Гарантирует, что q + dt * dq останется в [lower, upper].&quot;&quot;&quot;<br>
<br>
&#9;def __init__(<br>
&#9;&#9;self,<br>
&#9;&#9;q_current: np.ndarray,<br>
&#9;&#9;lower: Optional[np.ndarray] = None,<br>
&#9;&#9;upper: Optional[np.ndarray] = None,<br>
&#9;&#9;dt: float = 1.0,<br>
&#9;):<br>
<br>
&#9;&#9;if dt &lt;= 0.0:<br>
&#9;&#9;&#9;raise ValueError(&quot;dt must be positive.&quot;)<br>
&#9;&#9;q_current = np.asarray(q_current, dtype=float)<br>
&#9;&#9;n = q_current.size<br>
&#9;&#9;if lower is None and upper is None:<br>
&#9;&#9;&#9;raise ValueError(&quot;At least one of lower/upper bounds must be provided.&quot;)<br>
<br>
&#9;&#9;rows = []<br>
&#9;&#9;rhs = []<br>
<br>
&#9;&#9;if upper is not None:<br>
&#9;&#9;&#9;upper = np.asarray(upper, dtype=float)<br>
&#9;&#9;&#9;if upper.size != n:<br>
&#9;&#9;&#9;&#9;raise ValueError(&quot;upper must have same length as q_current.&quot;)<br>
&#9;&#9;&#9;rows.append(np.eye(n) * dt)<br>
&#9;&#9;&#9;rhs.append(upper - q_current)<br>
<br>
&#9;&#9;if lower is not None:<br>
&#9;&#9;&#9;lower = np.asarray(lower, dtype=float)<br>
&#9;&#9;&#9;if lower.size != n:<br>
&#9;&#9;&#9;&#9;raise ValueError(&quot;lower must have same length as q_current.&quot;)<br>
&#9;&#9;&#9;rows.append(-np.eye(n) * dt)<br>
&#9;&#9;&#9;rhs.append(q_current - lower)<br>
<br>
&#9;&#9;C = np.vstack(rows)<br>
&#9;&#9;d = np.concatenate(rhs)<br>
&#9;&#9;super().__init__(C, d)<br>
<br>
<br>
def build_joint_soft_limit_task(<br>
&#9;q_current: np.ndarray,<br>
&#9;lower: Optional[np.ndarray],<br>
&#9;upper: Optional[np.ndarray],<br>
&#9;margin: float,<br>
&#9;gain: float,<br>
) -&gt; Optional[QuadraticTask]:<br>
&#9;&quot;&quot;&quot;Возвращает QuadraticTask, отталкивающий суставы от мягких зон.&quot;&quot;&quot;<br>
<br>
&#9;if margin &lt;= 0 or gain &lt;= 0:<br>
&#9;&#9;return None<br>
<br>
&#9;q_current = np.asarray(q_current, dtype=float)<br>
&#9;n = q_current.size<br>
<br>
&#9;upper_arr = np.asarray(upper, dtype=float) if upper is not None else None<br>
&#9;lower_arr = np.asarray(lower, dtype=float) if lower is not None else None<br>
<br>
&#9;rows = []<br>
&#9;targets = []<br>
<br>
&#9;def _push(amount: float) -&gt; float:<br>
&#9;&#9;phase = min(max(amount / margin, 0.0), 1.0)<br>
&#9;&#9;return gain * phase<br>
<br>
&#9;for idx in range(n):<br>
&#9;&#9;coord = q_current[idx]<br>
&#9;&#9;desired = 0.0<br>
&#9;&#9;active = False<br>
<br>
&#9;&#9;if upper_arr is not None:<br>
&#9;&#9;&#9;boundary = upper_arr[idx]<br>
&#9;&#9;&#9;trigger = boundary - margin<br>
&#9;&#9;&#9;if coord &gt; trigger:<br>
&#9;&#9;&#9;&#9;desired -= _push(coord - trigger)<br>
&#9;&#9;&#9;&#9;active = True<br>
<br>
&#9;&#9;if lower_arr is not None:<br>
&#9;&#9;&#9;boundary = lower_arr[idx]<br>
&#9;&#9;&#9;trigger = boundary + margin<br>
&#9;&#9;&#9;if coord &lt; trigger:<br>
&#9;&#9;&#9;&#9;desired += _push(trigger - coord)<br>
&#9;&#9;&#9;&#9;active = True<br>
<br>
&#9;&#9;if active:<br>
&#9;&#9;&#9;row = np.zeros(n)<br>
&#9;&#9;&#9;row[idx] = 1.0<br>
&#9;&#9;&#9;rows.append(row)<br>
&#9;&#9;&#9;targets.append(desired)<br>
<br>
&#9;if not rows:<br>
&#9;&#9;return None<br>
<br>
&#9;J = np.vstack(rows)<br>
&#9;v = np.array(targets, dtype=float)<br>
&#9;return QuadraticTask(J, v)<br>
<!-- END SCAT CODE -->
</body>
</html>
