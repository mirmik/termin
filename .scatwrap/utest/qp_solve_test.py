<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>utest/qp_solve_test.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
import&nbsp;numpy&nbsp;as&nbsp;np<br>
from&nbsp;termin.linalg.solve&nbsp;import&nbsp;solve_qp_equalities<br>
<br>
#&nbsp;Генератор&nbsp;SPD&nbsp;матрицы<br>
def&nbsp;make_spd(n):<br>
&nbsp;&nbsp;&nbsp;&nbsp;M&nbsp;=&nbsp;np.random.randn(n,&nbsp;n)<br>
&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;M.T&nbsp;@&nbsp;M&nbsp;+&nbsp;np.eye(n)&nbsp;*&nbsp;1e-3&nbsp;&nbsp;#&nbsp;слегка&nbsp;регуляризуем<br>
<br>
<br>
def&nbsp;test_known_solution():<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;Тест&nbsp;1:&nbsp;аналитически&nbsp;известное&nbsp;решение.<br>
&nbsp;&nbsp;&nbsp;&nbsp;QP:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;min&nbsp;1/2&nbsp;x^T&nbsp;H&nbsp;x&nbsp;+&nbsp;g^T&nbsp;x<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;s.t.&nbsp;x1&nbsp;+&nbsp;x2&nbsp;=&nbsp;1<br>
&nbsp;&nbsp;&nbsp;&nbsp;Выбираем&nbsp;H&nbsp;и&nbsp;g&nbsp;так,&nbsp;чтобы&nbsp;решение&nbsp;можно&nbsp;было&nbsp;получить&nbsp;вручную.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;H&nbsp;=&nbsp;np.array([[2.,&nbsp;0.],<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[0.,&nbsp;2.]])<br>
&nbsp;&nbsp;&nbsp;&nbsp;g&nbsp;=&nbsp;np.array([-2.,&nbsp;-6.])&nbsp;&nbsp;&nbsp;#&nbsp;градиент<br>
&nbsp;&nbsp;&nbsp;&nbsp;A&nbsp;=&nbsp;np.array([[1.,&nbsp;1.]])<br>
&nbsp;&nbsp;&nbsp;&nbsp;b&nbsp;=&nbsp;np.array([1.])<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;x_expected&nbsp;=&nbsp;np.array([-0.5,&nbsp;1.5])<br>
&nbsp;&nbsp;&nbsp;&nbsp;x,&nbsp;lam&nbsp;=&nbsp;solve_qp_equalities(H,&nbsp;g,&nbsp;A,&nbsp;b)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.allclose(x,&nbsp;x_expected,&nbsp;atol=1e-7)<br>
<br>
<br>
def&nbsp;test_kkt_residual_small():<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;Тест&nbsp;2:&nbsp;Случайные&nbsp;SPD&nbsp;H&nbsp;и&nbsp;случайные&nbsp;A,&nbsp;b.<br>
&nbsp;&nbsp;&nbsp;&nbsp;Проверяем&nbsp;точность&nbsp;ККТ:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Hx&nbsp;+&nbsp;A^T&nbsp;λ&nbsp;+&nbsp;g&nbsp;=&nbsp;0<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Ax&nbsp;-&nbsp;b&nbsp;=&nbsp;0<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;np.random.seed(0)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;n&nbsp;=&nbsp;5<br>
&nbsp;&nbsp;&nbsp;&nbsp;m&nbsp;=&nbsp;2<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;H&nbsp;=&nbsp;make_spd(n)<br>
&nbsp;&nbsp;&nbsp;&nbsp;g&nbsp;=&nbsp;np.random.randn(n)<br>
&nbsp;&nbsp;&nbsp;&nbsp;A&nbsp;=&nbsp;np.random.randn(m,&nbsp;n)<br>
&nbsp;&nbsp;&nbsp;&nbsp;b&nbsp;=&nbsp;np.random.randn(m)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;x,&nbsp;lam&nbsp;=&nbsp;solve_qp_equalities(H,&nbsp;g,&nbsp;A,&nbsp;b)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Проверяем&nbsp;ККТ&nbsp;с&nbsp;разумной&nbsp;точностью<br>
&nbsp;&nbsp;&nbsp;&nbsp;kkt1&nbsp;=&nbsp;H&nbsp;@&nbsp;x&nbsp;+&nbsp;A.T&nbsp;@&nbsp;lam&nbsp;+&nbsp;g&nbsp;&nbsp;&nbsp;#&nbsp;должно&nbsp;быть&nbsp;≈&nbsp;0<br>
&nbsp;&nbsp;&nbsp;&nbsp;kkt2&nbsp;=&nbsp;A&nbsp;@&nbsp;x&nbsp;-&nbsp;b&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;должно&nbsp;быть&nbsp;≈&nbsp;0<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.linalg.norm(kkt1)&nbsp;&lt;&nbsp;1e-7<br>
&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.linalg.norm(kkt2)&nbsp;&lt;&nbsp;1e-7<br>
<br>
<br>
def&nbsp;test_random_stress():<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;Тест&nbsp;3:&nbsp;много&nbsp;случайных&nbsp;задач.<br>
&nbsp;&nbsp;&nbsp;&nbsp;Единственная&nbsp;проверка&nbsp;—&nbsp;выполнение&nbsp;ККТ.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;for&nbsp;_&nbsp;in&nbsp;range(50):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;n&nbsp;=&nbsp;6<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;m&nbsp;=&nbsp;3<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H&nbsp;=&nbsp;make_spd(n)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;g&nbsp;=&nbsp;np.random.randn(n)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;A&nbsp;=&nbsp;np.random.randn(m,&nbsp;n)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;b&nbsp;=&nbsp;np.random.randn(m)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;x,&nbsp;lam&nbsp;=&nbsp;solve_qp_equalities(H,&nbsp;g,&nbsp;A,&nbsp;b)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;ККТ&nbsp;проверки<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.linalg.norm(H&nbsp;@&nbsp;x&nbsp;+&nbsp;A.T&nbsp;@&nbsp;lam&nbsp;+&nbsp;g)&nbsp;&lt;&nbsp;1e-7<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.linalg.norm(A&nbsp;@&nbsp;x&nbsp;-&nbsp;b)&nbsp;&lt;&nbsp;1e-7<br>
<!-- END SCAT CODE -->
</body>
</html>
