<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>utest/active_set_test.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
import&nbsp;numpy&nbsp;as&nbsp;np<br>
from&nbsp;termin.linalg.solve&nbsp;import&nbsp;solve_qp_active_set<br>
<br>
<br>
def&nbsp;solve_eq(H,&nbsp;g,&nbsp;A_eq,&nbsp;b_eq):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Простенькая&nbsp;подстановка&nbsp;—&nbsp;решаем&nbsp;через&nbsp;active-set&nbsp;без&nbsp;неравенств.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;solve_qp_active_set(H,&nbsp;g,&nbsp;A_eq,&nbsp;b_eq,&nbsp;C=np.zeros((0,&nbsp;H.shape[0])),&nbsp;d=np.zeros(0))<br>
<br>
<br>
#&nbsp;------------------------------------------------------------------------<br>
#&nbsp;1.&nbsp;Простейшая&nbsp;QP&nbsp;без&nbsp;неравенств<br>
#&nbsp;------------------------------------------------------------------------<br>
def&nbsp;test_basic_equality_qp():<br>
&nbsp;&nbsp;&nbsp;&nbsp;H&nbsp;=&nbsp;np.array([[2.,&nbsp;0.],<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[0.,&nbsp;2.]])<br>
&nbsp;&nbsp;&nbsp;&nbsp;g&nbsp;=&nbsp;np.array([-2.,&nbsp;-6.])<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;A&nbsp;=&nbsp;np.array([[1.,&nbsp;1.]])<br>
&nbsp;&nbsp;&nbsp;&nbsp;b&nbsp;=&nbsp;np.array([1.])<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Аналитическое&nbsp;решение:&nbsp;x&nbsp;=&nbsp;[0,&nbsp;1]<br>
&nbsp;&nbsp;&nbsp;&nbsp;x,&nbsp;lam_eq,&nbsp;lam_ineq,&nbsp;active,&nbsp;iters&nbsp;=&nbsp;solve_eq(H,&nbsp;g,&nbsp;A,&nbsp;b)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.allclose(H@x&nbsp;+&nbsp;A.T&nbsp;@&nbsp;lam_eq&nbsp;+&nbsp;g,&nbsp;0)<br>
&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.allclose(x,&nbsp;np.array([-0.5,&nbsp;1.5]),&nbsp;atol=1e-7)<br>
&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;active.size&nbsp;==&nbsp;0<br>
&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;lam_ineq.size&nbsp;==&nbsp;0<br>
&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;iters&nbsp;==&nbsp;1&nbsp;&nbsp;#&nbsp;без&nbsp;неравенств&nbsp;всегда&nbsp;1&nbsp;итерация<br>
<br>
<br>
#&nbsp;------------------------------------------------------------------------<br>
#&nbsp;2.&nbsp;Одно&nbsp;неравенство&nbsp;становится&nbsp;активным<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;min&nbsp;(x1&nbsp;-&nbsp;1)^2<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;s.t.&nbsp;x1&nbsp;&lt;=&nbsp;0.5<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;optimum:&nbsp;x1&nbsp;=&nbsp;0.5<br>
#&nbsp;------------------------------------------------------------------------<br>
def&nbsp;test_single_inequality_becomes_active():<br>
&nbsp;&nbsp;&nbsp;&nbsp;H&nbsp;=&nbsp;np.array([[2.]])&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;cost&nbsp;=&nbsp;(x-1)^2&nbsp;→&nbsp;H=2,&nbsp;g=-2<br>
&nbsp;&nbsp;&nbsp;&nbsp;g&nbsp;=&nbsp;np.array([-2.])<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;A_eq&nbsp;=&nbsp;np.zeros((0,&nbsp;1))<br>
&nbsp;&nbsp;&nbsp;&nbsp;b_eq&nbsp;=&nbsp;np.zeros(0)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;C&nbsp;=&nbsp;np.array([[1.]])&nbsp;&nbsp;#&nbsp;x&nbsp;&lt;=&nbsp;0.5<br>
&nbsp;&nbsp;&nbsp;&nbsp;d&nbsp;=&nbsp;np.array([0.5])<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;x,&nbsp;lam_eq,&nbsp;lam_ineq,&nbsp;active,&nbsp;iters&nbsp;=&nbsp;solve_qp_active_set(H,&nbsp;g,&nbsp;A_eq,&nbsp;b_eq,&nbsp;C,&nbsp;d)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.allclose(H@x&nbsp;+&nbsp;A_eq.T&nbsp;@&nbsp;lam_eq&nbsp;+&nbsp;C[active].T&nbsp;@&nbsp;lam_ineq&nbsp;+&nbsp;g,&nbsp;0)<br>
&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.allclose(x,&nbsp;np.array([0.5]),&nbsp;atol=1e-7)<br>
&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;active.tolist()&nbsp;==&nbsp;[0]<br>
&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;lam_ineq.size&nbsp;==&nbsp;1<br>
&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;lam_ineq[0]&nbsp;&gt;=&nbsp;0&nbsp;&nbsp;#&nbsp;ККТ<br>
&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;iters&nbsp;==&nbsp;2&nbsp;&nbsp;#&nbsp;1&nbsp;итерация&nbsp;без&nbsp;активного,&nbsp;2-я&nbsp;с&nbsp;активным<br>
<br>
<br>
#&nbsp;------------------------------------------------------------------------<br>
#&nbsp;3.&nbsp;Warm-start&nbsp;по&nbsp;активному&nbsp;набору<br>
#&nbsp;&nbsp;&nbsp;&nbsp;Мы&nbsp;заранее&nbsp;говорим&nbsp;решателю,&nbsp;что&nbsp;ограничение&nbsp;активно,<br>
#&nbsp;&nbsp;&nbsp;&nbsp;и&nbsp;он&nbsp;должен&nbsp;решить&nbsp;всё&nbsp;за&nbsp;1&nbsp;итерацию.<br>
#&nbsp;------------------------------------------------------------------------<br>
def&nbsp;test_active_set_warm_start():<br>
&nbsp;&nbsp;&nbsp;&nbsp;H&nbsp;=&nbsp;np.array([[2.]])<br>
&nbsp;&nbsp;&nbsp;&nbsp;g&nbsp;=&nbsp;np.array([-2.])<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;A_eq&nbsp;=&nbsp;np.zeros((0,&nbsp;1))<br>
&nbsp;&nbsp;&nbsp;&nbsp;b_eq&nbsp;=&nbsp;np.zeros(0)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;C&nbsp;=&nbsp;np.array([[1.]])&nbsp;&nbsp;#&nbsp;x&nbsp;&lt;=&nbsp;0.5<br>
&nbsp;&nbsp;&nbsp;&nbsp;d&nbsp;=&nbsp;np.array([0.5])<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;active0&nbsp;=&nbsp;np.array([0])&nbsp;&nbsp;#&nbsp;warm-start<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;x,&nbsp;lam_eq,&nbsp;lam_ineq,&nbsp;active,&nbsp;iters&nbsp;=&nbsp;solve_qp_active_set(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H,&nbsp;g,&nbsp;A_eq,&nbsp;b_eq,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;C=C,&nbsp;d=d,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;active0=active0<br>
&nbsp;&nbsp;&nbsp;&nbsp;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.allclose(H@x&nbsp;+&nbsp;A_eq.T&nbsp;@&nbsp;lam_eq&nbsp;+&nbsp;C[active].T&nbsp;@&nbsp;lam_ineq&nbsp;+&nbsp;g,&nbsp;0)<br>
&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.allclose(x,&nbsp;np.array([0.5]),&nbsp;atol=1e-7)<br>
&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;active.tolist()&nbsp;==&nbsp;[0]<br>
&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;iters&nbsp;==&nbsp;1&nbsp;&nbsp;#&nbsp;ВАЖНО:&nbsp;warm-start&nbsp;должен&nbsp;сходиться&nbsp;сразу<br>
<br>
<br>
#&nbsp;------------------------------------------------------------------------<br>
#&nbsp;4.&nbsp;λ&nbsp;&lt;&nbsp;0&nbsp;→&nbsp;удаление&nbsp;активного&nbsp;ограничения<br>
#&nbsp;&nbsp;&nbsp;&nbsp;Изначально&nbsp;x0&nbsp;находится&nbsp;ровно&nbsp;на&nbsp;границе,&nbsp;active0&nbsp;=&nbsp;{0}.<br>
#&nbsp;&nbsp;&nbsp;&nbsp;Но&nbsp;задача&nbsp;не&nbsp;требует&nbsp;активного&nbsp;ограничения.<br>
#&nbsp;------------------------------------------------------------------------<br>
def&nbsp;test_removing_incorrect_active_constraint():<br>
&nbsp;&nbsp;&nbsp;&nbsp;H&nbsp;=&nbsp;np.array([[2.]])<br>
&nbsp;&nbsp;&nbsp;&nbsp;g&nbsp;=&nbsp;np.array([0.])&nbsp;&nbsp;#&nbsp;минимум&nbsp;при&nbsp;x&nbsp;=&nbsp;0<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;A_eq&nbsp;=&nbsp;np.zeros((0,&nbsp;1))<br>
&nbsp;&nbsp;&nbsp;&nbsp;b_eq&nbsp;=&nbsp;np.zeros(0)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;C&nbsp;=&nbsp;np.array([[1.]])&nbsp;&nbsp;#&nbsp;x&nbsp;&lt;=&nbsp;0.5<br>
&nbsp;&nbsp;&nbsp;&nbsp;d&nbsp;=&nbsp;np.array([0.5])<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;x0&nbsp;на&nbsp;границе,&nbsp;решатель&nbsp;может&nbsp;подумать&nbsp;&quot;оно&nbsp;активно&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;x0&nbsp;=&nbsp;np.array([0.5])<br>
&nbsp;&nbsp;&nbsp;&nbsp;active0&nbsp;=&nbsp;np.array([0])<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;x,&nbsp;lam_eq,&nbsp;lam_ineq,&nbsp;active,&nbsp;iters&nbsp;=&nbsp;solve_qp_active_set(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H,&nbsp;g,&nbsp;A_eq,&nbsp;b_eq,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;C,&nbsp;d,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;x0=x0,&nbsp;active0=active0<br>
&nbsp;&nbsp;&nbsp;&nbsp;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.allclose(H@x&nbsp;+&nbsp;A_eq.T&nbsp;@&nbsp;lam_eq&nbsp;+&nbsp;C[active].T&nbsp;@&nbsp;lam_ineq&nbsp;+&nbsp;g,&nbsp;0)<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Оптимум&nbsp;при&nbsp;x=0,&nbsp;ограничение&nbsp;НЕ&nbsp;активно<br>
&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.allclose(x,&nbsp;np.array([0.0]))<br>
&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;active.size&nbsp;==&nbsp;0<br>
&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;lam_ineq.size&nbsp;==&nbsp;0<br>
&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;iters&nbsp;==&nbsp;2&nbsp;&nbsp;#&nbsp;1-я&nbsp;итерация&nbsp;с&nbsp;активным,&nbsp;2-я&nbsp;без<br>
<br>
<br>
#&nbsp;------------------------------------------------------------------------<br>
#&nbsp;5.&nbsp;Два&nbsp;нарушенных&nbsp;ограничения&nbsp;→&nbsp;выбираем&nbsp;&quot;худший&quot;<br>
#&nbsp;------------------------------------------------------------------------<br>
def&nbsp;test_two_violations_pick_worst():<br>
&nbsp;&nbsp;&nbsp;&nbsp;H&nbsp;=&nbsp;np.eye(2)<br>
&nbsp;&nbsp;&nbsp;&nbsp;g&nbsp;=&nbsp;np.array([0.,&nbsp;0.])<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;A_eq&nbsp;=&nbsp;np.zeros((0,&nbsp;2))<br>
&nbsp;&nbsp;&nbsp;&nbsp;b_eq&nbsp;=&nbsp;np.zeros(0)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Ограничения:<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;x1&nbsp;&lt;=&nbsp;-1&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;(нарушение&nbsp;=&nbsp;x1&nbsp;-&nbsp;(-1))<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;x1&nbsp;&lt;=&nbsp;&nbsp;0<br>
&nbsp;&nbsp;&nbsp;&nbsp;C&nbsp;=&nbsp;np.array([[1.,&nbsp;0.],<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[1.,&nbsp;0.]])<br>
&nbsp;&nbsp;&nbsp;&nbsp;d&nbsp;=&nbsp;np.array([-1.,&nbsp;0.])<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;x0&nbsp;сильно&nbsp;нарушает&nbsp;оба<br>
&nbsp;&nbsp;&nbsp;&nbsp;x0&nbsp;=&nbsp;np.array([1.,&nbsp;0.])<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;x,&nbsp;lam_eq,&nbsp;lam_ineq,&nbsp;active,&nbsp;iters&nbsp;=&nbsp;solve_qp_active_set(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H,&nbsp;g,&nbsp;A_eq,&nbsp;b_eq,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;C,&nbsp;d,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;x0=x0<br>
&nbsp;&nbsp;&nbsp;&nbsp;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.allclose(H@x&nbsp;+&nbsp;A_eq.T&nbsp;@&nbsp;lam_eq&nbsp;+&nbsp;C[active].T&nbsp;@&nbsp;lam_ineq&nbsp;+&nbsp;g,&nbsp;0)<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;&quot;худшее&quot;&nbsp;нарушение&nbsp;—&nbsp;для&nbsp;первого&nbsp;ограничения&nbsp;(1&nbsp;-&nbsp;(-1)&nbsp;=&nbsp;2)<br>
&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;active[0]&nbsp;==&nbsp;0<br>
&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;iters&nbsp;==&nbsp;2&nbsp;&nbsp;#&nbsp;1-я&nbsp;итерация&nbsp;с&nbsp;одним&nbsp;активным,&nbsp;2-я&nbsp;без&nbsp;нарушений<br>
<br>
<br>
#&nbsp;------------------------------------------------------------------------<br>
#&nbsp;6.&nbsp;Активное&nbsp;ограничение&nbsp;остаётся&nbsp;активным&nbsp;при&nbsp;λ&nbsp;&gt;=&nbsp;0<br>
#&nbsp;------------------------------------------------------------------------<br>
def&nbsp;test_active_constraint_stays_active():<br>
&nbsp;&nbsp;&nbsp;&nbsp;H&nbsp;=&nbsp;np.array([[2.]])<br>
&nbsp;&nbsp;&nbsp;&nbsp;g&nbsp;=&nbsp;np.array([-2.])<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;A_eq&nbsp;=&nbsp;np.zeros((0,&nbsp;1))<br>
&nbsp;&nbsp;&nbsp;&nbsp;b_eq&nbsp;=&nbsp;np.zeros(0)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;C&nbsp;=&nbsp;np.array([[1.]])<br>
&nbsp;&nbsp;&nbsp;&nbsp;d&nbsp;=&nbsp;np.array([0.5])<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;x0&nbsp;≈&nbsp;0.5,&nbsp;ограничение&nbsp;активно&nbsp;и&nbsp;λ&nbsp;&gt;&nbsp;0<br>
&nbsp;&nbsp;&nbsp;&nbsp;x0&nbsp;=&nbsp;np.array([0.5])<br>
&nbsp;&nbsp;&nbsp;&nbsp;active0&nbsp;=&nbsp;np.array([0])<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;x,&nbsp;lam_eq,&nbsp;lam_ineq,&nbsp;active,&nbsp;iters&nbsp;=&nbsp;solve_qp_active_set(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H,&nbsp;g,&nbsp;A_eq,&nbsp;b_eq,&nbsp;C,&nbsp;d,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;x0=x0,&nbsp;active0=active0<br>
&nbsp;&nbsp;&nbsp;&nbsp;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.allclose(H@x&nbsp;+&nbsp;A_eq.T&nbsp;@&nbsp;lam_eq&nbsp;+&nbsp;C[active].T&nbsp;@&nbsp;lam_ineq&nbsp;+&nbsp;g,&nbsp;0)<br>
&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;active.tolist()&nbsp;==&nbsp;[0]&nbsp;&nbsp;#&nbsp;не&nbsp;должно&nbsp;исчезнуть<br>
&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;lam_ineq[0]&nbsp;&gt;=&nbsp;0<br>
&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.allclose(x,&nbsp;np.array([0.5]))<br>
&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;iters&nbsp;==&nbsp;1&nbsp;&nbsp;#&nbsp;должно&nbsp;сойтись&nbsp;сразу<br>
<!-- END SCAT CODE -->
</body>
</html>
