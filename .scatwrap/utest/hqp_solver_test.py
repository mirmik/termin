<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>utest/hqp_solver_test.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
import&nbsp;numpy&nbsp;as&nbsp;np<br>
<br>
from&nbsp;termin.robot.hqsolver&nbsp;import&nbsp;(<br>
&nbsp;&nbsp;&nbsp;&nbsp;HQPSolver,<br>
&nbsp;&nbsp;&nbsp;&nbsp;Level,<br>
&nbsp;&nbsp;&nbsp;&nbsp;QuadraticTask,<br>
&nbsp;&nbsp;&nbsp;&nbsp;EqualityConstraint,<br>
&nbsp;&nbsp;&nbsp;&nbsp;InequalityConstraint<br>
)<br>
<br>
from&nbsp;termin.linalg.solve&nbsp;import&nbsp;solve_qp_active_set<br>
from&nbsp;termin.linalg.subspaces&nbsp;import&nbsp;nullspace_basis<br>
<br>
#&nbsp;-------------------------------------------------------------<br>
#&nbsp;ТЕСТ&nbsp;1:&nbsp;ПРОСТАЯ&nbsp;QP&nbsp;(ОДИН&nbsp;УРОВЕНЬ)<br>
#&nbsp;-------------------------------------------------------------<br>
<br>
def&nbsp;test_hqp_single_level_basic():<br>
&nbsp;&nbsp;&nbsp;&nbsp;solver&nbsp;=&nbsp;HQPSolver(n_vars=2)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;lvl&nbsp;=&nbsp;Level(priority=0)<br>
&nbsp;&nbsp;&nbsp;&nbsp;J&nbsp;=&nbsp;np.eye(2)<br>
&nbsp;&nbsp;&nbsp;&nbsp;v&nbsp;=&nbsp;np.array([1.,&nbsp;2.])<br>
&nbsp;&nbsp;&nbsp;&nbsp;lvl.add_task(QuadraticTask(J,&nbsp;v))<br>
&nbsp;&nbsp;&nbsp;&nbsp;solver.add_level(lvl)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;x&nbsp;=&nbsp;solver.solve()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Ожидаем&nbsp;x&nbsp;=&nbsp;v&nbsp;(минимум&nbsp;||x&nbsp;-&nbsp;v||^2)<br>
&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.allclose(x,&nbsp;[1.,&nbsp;2.],&nbsp;atol=1e-7)<br>
<br>
<br>
#&nbsp;-------------------------------------------------------------<br>
#&nbsp;ТЕСТ&nbsp;2:&nbsp;ДВА&nbsp;УРОВНЯ,&nbsp;ВТОРОЙ&nbsp;РАБОТАЕТ&nbsp;В&nbsp;NULLSPACE&nbsp;ПЕРВОГО<br>
#&nbsp;-------------------------------------------------------------<br>
<br>
def&nbsp;test_hqp_two_levels_nullspace_simple():<br>
&nbsp;&nbsp;&nbsp;&nbsp;solver&nbsp;=&nbsp;HQPSolver(n_vars=2)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Level&nbsp;0:&nbsp;тянем&nbsp;x&nbsp;→&nbsp;[1,&nbsp;0]<br>
&nbsp;&nbsp;&nbsp;&nbsp;lvl0&nbsp;=&nbsp;Level(priority=0)<br>
&nbsp;&nbsp;&nbsp;&nbsp;lvl0.add_task(QuadraticTask(np.eye(2),&nbsp;np.array([1.,&nbsp;0.])))<br>
&nbsp;&nbsp;&nbsp;&nbsp;solver.add_level(lvl0)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Level&nbsp;1:&nbsp;x&nbsp;→&nbsp;[1,&nbsp;5],&nbsp;но&nbsp;только&nbsp;в&nbsp;nullspace&nbsp;первого&nbsp;уровня<br>
&nbsp;&nbsp;&nbsp;&nbsp;lvl1&nbsp;=&nbsp;Level(priority=1)<br>
&nbsp;&nbsp;&nbsp;&nbsp;lvl1.add_task(QuadraticTask(np.eye(2),&nbsp;np.array([1.,&nbsp;5.])))<br>
&nbsp;&nbsp;&nbsp;&nbsp;solver.add_level(lvl1)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;x&nbsp;=&nbsp;solver.solve()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;abs(x[0]&nbsp;-&nbsp;1.0)&nbsp;&lt;&nbsp;1e-7&nbsp;&nbsp;&nbsp;#&nbsp;не&nbsp;нарушено&nbsp;первым&nbsp;уровнем<br>
&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;abs(x[1]&nbsp;-&nbsp;0.0)&nbsp;&lt;&nbsp;1e-7&nbsp;&nbsp;&nbsp;#&nbsp;второй&nbsp;уровень&nbsp;не&nbsp;может&nbsp;изменить&nbsp;x1<br>
<br>
#&nbsp;-------------------------------------------------------------<br>
#&nbsp;ТЕСТ&nbsp;2.2:&nbsp;ДВА&nbsp;УРОВНЯ,&nbsp;ВТОРОЙ&nbsp;РАБОТАЕТ&nbsp;В&nbsp;NULLSPACE&nbsp;ПЕРВОГО<br>
#&nbsp;-------------------------------------------------------------<br>
<br>
def&nbsp;test_hqp_two_levels_nullspace():<br>
&nbsp;&nbsp;&nbsp;&nbsp;solver&nbsp;=&nbsp;HQPSolver(n_vars=4)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Level&nbsp;0:&nbsp;Теперь&nbsp;делаем&nbsp;невырожденный&nbsp;nullspace<br>
&nbsp;&nbsp;&nbsp;&nbsp;lvl0&nbsp;=&nbsp;Level(priority=0)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;J&nbsp;=&nbsp;np.array([<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[1,0,0,0],<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[0,1,0,0],<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[0,0,1,1.1],<br>
&nbsp;&nbsp;&nbsp;&nbsp;])<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;lvl0.add_task(QuadraticTask(J,&nbsp;np.array([1.,&nbsp;0.,&nbsp;0.])))<br>
&nbsp;&nbsp;&nbsp;&nbsp;solver.add_level(lvl0)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Level&nbsp;1:&nbsp;x&nbsp;→&nbsp;[1,&nbsp;5],&nbsp;но&nbsp;только&nbsp;в&nbsp;nullspace&nbsp;первого&nbsp;уровня<br>
&nbsp;&nbsp;&nbsp;&nbsp;lvl1&nbsp;=&nbsp;Level(priority=1)<br>
&nbsp;&nbsp;&nbsp;&nbsp;lvl1.add_task(QuadraticTask(np.eye(4),&nbsp;np.array([1.,&nbsp;5.,&nbsp;-2.,&nbsp;2.])))<br>
&nbsp;&nbsp;&nbsp;&nbsp;solver.add_level(lvl1)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;x&nbsp;=&nbsp;solver.solve()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;abs(x[0]&nbsp;-&nbsp;1.0)&nbsp;&lt;&nbsp;1e-7&nbsp;&nbsp;&nbsp;#&nbsp;не&nbsp;нарушено&nbsp;первым&nbsp;уровнем<br>
&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;abs(x[1]&nbsp;-&nbsp;0.0)&nbsp;&lt;&nbsp;1e-7&nbsp;&nbsp;&nbsp;#&nbsp;второй&nbsp;уровень&nbsp;не&nbsp;может&nbsp;изменить&nbsp;x2<br>
&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;abs(x[2]&nbsp;+&nbsp;1.1&nbsp;*&nbsp;x[3])&nbsp;&lt;&nbsp;1e-7&nbsp;&nbsp;#&nbsp;сохраняем&nbsp;ограничение&nbsp;первого&nbsp;уровня<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;N&nbsp;=&nbsp;nullspace_basis(J)<br>
&nbsp;&nbsp;&nbsp;&nbsp;x0&nbsp;=&nbsp;np.array([1.,&nbsp;0.,&nbsp;0.,&nbsp;0.])<br>
&nbsp;&nbsp;&nbsp;&nbsp;x_des&nbsp;=&nbsp;np.array([1.,&nbsp;5.,&nbsp;-2.,&nbsp;2.])<br>
&nbsp;&nbsp;&nbsp;&nbsp;z&nbsp;=&nbsp;N.T&nbsp;@&nbsp;(x_des&nbsp;-&nbsp;x0)<br>
&nbsp;&nbsp;&nbsp;&nbsp;x_expected&nbsp;=&nbsp;x0&nbsp;+&nbsp;N&nbsp;@&nbsp;z<br>
&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.allclose(x,&nbsp;x_expected,&nbsp;atol=1e-7)<br>
<br>
<br>
#&nbsp;-------------------------------------------------------------<br>
#&nbsp;ТЕСТ&nbsp;3:&nbsp;РАВЕНСТВО&nbsp;НА&nbsp;УРОВНЕ&nbsp;HQP<br>
#&nbsp;-------------------------------------------------------------<br>
<br>
def&nbsp;test_hqp_equality_constraint():<br>
&nbsp;&nbsp;&nbsp;&nbsp;solver&nbsp;=&nbsp;HQPSolver(n_vars=2)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;lvl&nbsp;=&nbsp;Level(priority=0)<br>
&nbsp;&nbsp;&nbsp;&nbsp;lvl.add_task(QuadraticTask(np.eye(2),&nbsp;np.array([2.,&nbsp;2.])))<br>
&nbsp;&nbsp;&nbsp;&nbsp;lvl.add_equality(EqualityConstraint(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;A=np.array([[1.,&nbsp;1.]]),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;b=np.array([1.])<br>
&nbsp;&nbsp;&nbsp;&nbsp;))<br>
&nbsp;&nbsp;&nbsp;&nbsp;solver.add_level(lvl)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;x&nbsp;=&nbsp;solver.solve()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Аналитически:&nbsp;минимум&nbsp;при&nbsp;x1&nbsp;+&nbsp;x2&nbsp;=&nbsp;1&nbsp;это&nbsp;x1&nbsp;=&nbsp;x2&nbsp;=&nbsp;0.5<br>
&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.allclose(x,&nbsp;[0.5,&nbsp;0.5],&nbsp;atol=1e-7)<br>
<br>
<br>
#&nbsp;-------------------------------------------------------------<br>
#&nbsp;ТЕСТ&nbsp;4:&nbsp;НЕРАВЕНСТВО&nbsp;(ACTIVE&nbsp;SET&nbsp;ВНУТРИ&nbsp;HQP)<br>
#&nbsp;-------------------------------------------------------------<br>
<br>
def&nbsp;test_hqp_inequality_constraint():<br>
&nbsp;&nbsp;&nbsp;&nbsp;solver&nbsp;=&nbsp;HQPSolver(n_vars=1)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;lvl&nbsp;=&nbsp;Level(priority=0)<br>
&nbsp;&nbsp;&nbsp;&nbsp;lvl.add_task(QuadraticTask(np.array([[1.]]),&nbsp;np.array([1.])))<br>
&nbsp;&nbsp;&nbsp;&nbsp;lvl.add_inequality(InequalityConstraint(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;C=np.array([[1.]]),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;d=np.array([0.5])<br>
&nbsp;&nbsp;&nbsp;&nbsp;))<br>
&nbsp;&nbsp;&nbsp;&nbsp;solver.add_level(lvl)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;x&nbsp;=&nbsp;solver.solve()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Минимум&nbsp;при&nbsp;ограничении&nbsp;x&nbsp;≤&nbsp;0.5<br>
&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;abs(x[0]&nbsp;-&nbsp;0.5)&nbsp;&lt;&nbsp;1e-7<br>
<br>
<br>
#&nbsp;-------------------------------------------------------------<br>
#&nbsp;ТЕСТ&nbsp;5:&nbsp;КОМБИНАЦИЯ&nbsp;ЗАДАЧ&nbsp;С&nbsp;NULLSPACE&nbsp;И&nbsp;НЕРАВЕНСТВАМИ<br>
#&nbsp;-------------------------------------------------------------<br>
<br>
def&nbsp;test_hqp_full_logic_with_constraints():<br>
&nbsp;&nbsp;&nbsp;&nbsp;solver&nbsp;=&nbsp;HQPSolver(n_vars=2)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Level&nbsp;0:&nbsp;фиксируем&nbsp;x1&nbsp;=&nbsp;1,&nbsp;оставляем&nbsp;свободу&nbsp;по&nbsp;x2<br>
&nbsp;&nbsp;&nbsp;&nbsp;lvl0&nbsp;=&nbsp;Level(priority=0)<br>
&nbsp;&nbsp;&nbsp;&nbsp;lvl0.add_task(QuadraticTask(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;J=np.array([[1.,&nbsp;0.]]),&nbsp;&nbsp;&nbsp;#&nbsp;фиксируем&nbsp;только&nbsp;x1<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v=np.array([1.])<br>
&nbsp;&nbsp;&nbsp;&nbsp;))<br>
&nbsp;&nbsp;&nbsp;&nbsp;solver.add_level(lvl0)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Level&nbsp;1:&nbsp;хотим&nbsp;x&nbsp;→&nbsp;[1,10],&nbsp;но&nbsp;ограничение&nbsp;x2&nbsp;&lt;=&nbsp;3<br>
&nbsp;&nbsp;&nbsp;&nbsp;lvl1&nbsp;=&nbsp;Level(priority=1)<br>
&nbsp;&nbsp;&nbsp;&nbsp;lvl1.add_task(QuadraticTask(np.eye(2),&nbsp;np.array([1.,&nbsp;10.])))<br>
&nbsp;&nbsp;&nbsp;&nbsp;lvl1.add_inequality(InequalityConstraint(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;C=np.array([[0.,&nbsp;1.]]),&nbsp;&nbsp;&nbsp;#&nbsp;x2&nbsp;&lt;=&nbsp;3<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;d=np.array([3.])<br>
&nbsp;&nbsp;&nbsp;&nbsp;))<br>
&nbsp;&nbsp;&nbsp;&nbsp;solver.add_level(lvl1)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;x&nbsp;=&nbsp;solver.solve()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Первый&nbsp;уровень:&nbsp;x1&nbsp;=&nbsp;1<br>
&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;abs(x[0]&nbsp;-&nbsp;1)&nbsp;&lt;&nbsp;1e-7<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Второй&nbsp;уровень:&nbsp;двигаем&nbsp;только&nbsp;x2&nbsp;→&nbsp;ограничение&nbsp;даёт&nbsp;x2&nbsp;=&nbsp;3<br>
&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;abs(x[1]&nbsp;-&nbsp;3)&nbsp;&lt;&nbsp;1e-7<br>
<br>
<!-- END SCAT CODE -->
</body>
</html>
