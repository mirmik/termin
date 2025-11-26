<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/fem/README.md</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
#&nbsp;FEM&nbsp;Module<br>
<br>
Модуль&nbsp;метода&nbsp;конечных&nbsp;элементов&nbsp;(Finite&nbsp;Element&nbsp;Method)&nbsp;для&nbsp;мультифизического&nbsp;моделирования.<br>
<br>
##&nbsp;Обзор<br>
<br>
Модуль&nbsp;предоставляет&nbsp;единую&nbsp;платформу&nbsp;для&nbsp;решения&nbsp;различных&nbsp;физических&nbsp;задач&nbsp;через&nbsp;сборку&nbsp;и&nbsp;решение&nbsp;систем&nbsp;линейных&nbsp;уравнений&nbsp;вида&nbsp;**A·x&nbsp;=&nbsp;b**.&nbsp;Поддерживает&nbsp;как&nbsp;статический,&nbsp;так&nbsp;и&nbsp;динамический&nbsp;анализ&nbsp;с&nbsp;использованием&nbsp;неявной&nbsp;схемы&nbsp;Эйлера.<br>
<br>
##&nbsp;Архитектура<br>
<br>
###&nbsp;Базовые&nbsp;классы&nbsp;(`assembler.py`)<br>
<br>
-&nbsp;**Variable**&nbsp;-&nbsp;представляет&nbsp;степени&nbsp;свободы&nbsp;системы&nbsp;(DOF)<br>
-&nbsp;**Contribution**&nbsp;-&nbsp;базовый&nbsp;класс&nbsp;для&nbsp;элементов,&nbsp;вносящих&nbsp;вклад&nbsp;в&nbsp;систему<br>
-&nbsp;**MatrixAssembler**&nbsp;-&nbsp;сборщик&nbsp;глобальной&nbsp;матрицы&nbsp;из&nbsp;вкладов&nbsp;элементов<br>
<br>
Каждый&nbsp;элемент&nbsp;наследуется&nbsp;от&nbsp;`Contribution`&nbsp;и&nbsp;реализует&nbsp;методы:<br>
-&nbsp;`get_variables()`&nbsp;-&nbsp;возвращает&nbsp;список&nbsp;используемых&nbsp;переменных<br>
-&nbsp;`contribute_to_mass(A,&nbsp;index_map)`&nbsp;-&nbsp;добавляет&nbsp;вклад&nbsp;в&nbsp;матрицу&nbsp;жесткости<br>
-&nbsp;`contribute_to_b(b,&nbsp;index_map)`&nbsp;-&nbsp;добавляет&nbsp;вклад&nbsp;в&nbsp;вектор&nbsp;нагрузки<br>
<br>
##&nbsp;Модули<br>
<br>
###&nbsp;1.&nbsp;Механика&nbsp;(`mechanic.py`)<br>
<br>
Конечные&nbsp;элементы&nbsp;для&nbsp;структурной&nbsp;механики:<br>
<br>
####&nbsp;BarElement<br>
Стержневой&nbsp;элемент&nbsp;(ферма)&nbsp;для&nbsp;1D&nbsp;и&nbsp;2D&nbsp;задач.<br>
```python<br>
from&nbsp;termin.fem&nbsp;import&nbsp;Variable,&nbsp;BarElement,&nbsp;MatrixAssembler<br>
<br>
u1&nbsp;=&nbsp;Variable(&quot;u1&quot;,&nbsp;2)&nbsp;&nbsp;#&nbsp;перемещение&nbsp;узла&nbsp;1&nbsp;(x,&nbsp;y)<br>
u2&nbsp;=&nbsp;Variable(&quot;u2&quot;,&nbsp;2)&nbsp;&nbsp;#&nbsp;перемещение&nbsp;узла&nbsp;2&nbsp;(x,&nbsp;y)<br>
<br>
bar&nbsp;=&nbsp;BarElement(<br>
&nbsp;&nbsp;&nbsp;&nbsp;u1,&nbsp;u2,<br>
&nbsp;&nbsp;&nbsp;&nbsp;E=200e9,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;модуль&nbsp;Юнга&nbsp;[Па]<br>
&nbsp;&nbsp;&nbsp;&nbsp;A=0.01,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;площадь&nbsp;сечения&nbsp;[м²]<br>
&nbsp;&nbsp;&nbsp;&nbsp;L=1.0,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;длина&nbsp;[м]<br>
&nbsp;&nbsp;&nbsp;&nbsp;angle=0.0&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;угол&nbsp;наклона&nbsp;[рад]<br>
)<br>
```<br>
<br>
####&nbsp;BeamElement2D<br>
Балочный&nbsp;элемент&nbsp;Эйлера-Бернулли&nbsp;для&nbsp;изгиба.<br>
```python<br>
beam&nbsp;=&nbsp;BeamElement2D(<br>
&nbsp;&nbsp;&nbsp;&nbsp;u1,&nbsp;u2,<br>
&nbsp;&nbsp;&nbsp;&nbsp;E=200e9,&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;модуль&nbsp;Юнга<br>
&nbsp;&nbsp;&nbsp;&nbsp;I=1e-4,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;момент&nbsp;инерции<br>
&nbsp;&nbsp;&nbsp;&nbsp;L=2.0&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;длина<br>
)<br>
```<br>
<br>
####&nbsp;Triangle3Node<br>
Треугольный&nbsp;элемент&nbsp;для&nbsp;плоского&nbsp;напряженного&nbsp;состояния.<br>
```python<br>
triangle&nbsp;=&nbsp;Triangle3Node(<br>
&nbsp;&nbsp;&nbsp;&nbsp;u1,&nbsp;u2,&nbsp;u3,<br>
&nbsp;&nbsp;&nbsp;&nbsp;E=200e9,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;модуль&nbsp;Юнга<br>
&nbsp;&nbsp;&nbsp;&nbsp;nu=0.3,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;коэффициент&nbsp;Пуассона<br>
&nbsp;&nbsp;&nbsp;&nbsp;thickness=0.01&nbsp;&nbsp;#&nbsp;толщина<br>
)<br>
```<br>
<br>
###&nbsp;2.&nbsp;Электрические&nbsp;цепи&nbsp;(`electrical.py`)<br>
<br>
Элементы&nbsp;для&nbsp;анализа&nbsp;электрических&nbsp;цепей:<br>
<br>
####&nbsp;Resistor<br>
Резистор&nbsp;с&nbsp;проводимостью&nbsp;G&nbsp;=&nbsp;1/R.<br>
```python<br>
from&nbsp;termin.fem&nbsp;import&nbsp;Resistor,&nbsp;VoltageSource,&nbsp;Ground<br>
<br>
v_plus&nbsp;=&nbsp;Variable(&quot;V+&quot;,&nbsp;1)<br>
v_gnd&nbsp;=&nbsp;Variable(&quot;GND&quot;,&nbsp;1)<br>
<br>
resistor&nbsp;=&nbsp;Resistor(v_plus,&nbsp;v_gnd,&nbsp;R=1000.0)&nbsp;&nbsp;#&nbsp;1&nbsp;кОм<br>
source&nbsp;=&nbsp;VoltageSource(v_plus,&nbsp;v_gnd,&nbsp;V=5.0)&nbsp;&nbsp;#&nbsp;5В<br>
ground&nbsp;=&nbsp;Ground(v_gnd)<br>
```<br>
<br>
####&nbsp;Capacitor&nbsp;/&nbsp;Inductor<br>
Динамические&nbsp;элементы&nbsp;с&nbsp;неявным&nbsp;интегрированием.<br>
```python<br>
capacitor&nbsp;=&nbsp;Capacitor(<br>
&nbsp;&nbsp;&nbsp;&nbsp;v_plus,&nbsp;v_minus,<br>
&nbsp;&nbsp;&nbsp;&nbsp;C=1e-6,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;ёмкость&nbsp;[Ф]<br>
&nbsp;&nbsp;&nbsp;&nbsp;dt=0.001,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;шаг&nbsp;времени&nbsp;[с]<br>
&nbsp;&nbsp;&nbsp;&nbsp;V_old=0.0&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;напряжение&nbsp;на&nbsp;предыдущем&nbsp;шаге<br>
)<br>
<br>
inductor&nbsp;=&nbsp;Inductor(<br>
&nbsp;&nbsp;&nbsp;&nbsp;v_plus,&nbsp;v_minus,<br>
&nbsp;&nbsp;&nbsp;&nbsp;L=1e-3,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;индуктивность&nbsp;[Гн]<br>
&nbsp;&nbsp;&nbsp;&nbsp;dt=0.001,<br>
&nbsp;&nbsp;&nbsp;&nbsp;I_old=0.0&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;ток&nbsp;на&nbsp;предыдущем&nbsp;шаге<br>
)<br>
```<br>
<br>
###&nbsp;3.&nbsp;Многотельная&nbsp;динамика&nbsp;(`multibody.py`)<br>
<br>
Элементы&nbsp;для&nbsp;моделирования&nbsp;вращательного&nbsp;и&nbsp;поступательного&nbsp;движения:<br>
<br>
####&nbsp;RotationalInertia<br>
Вращательная&nbsp;инерция&nbsp;с&nbsp;демпфированием:&nbsp;J·dω/dt&nbsp;=&nbsp;Σ&nbsp;τ&nbsp;-&nbsp;B·ω<br>
```python<br>
from&nbsp;termin.fem&nbsp;import&nbsp;RotationalInertia,&nbsp;TorqueSource<br>
<br>
omega&nbsp;=&nbsp;Variable(&quot;omega&quot;,&nbsp;1)&nbsp;&nbsp;#&nbsp;угловая&nbsp;скорость<br>
<br>
inertia&nbsp;=&nbsp;RotationalInertia(<br>
&nbsp;&nbsp;&nbsp;&nbsp;omega,<br>
&nbsp;&nbsp;&nbsp;&nbsp;J=0.1,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;момент&nbsp;инерции&nbsp;[кг·м²]<br>
&nbsp;&nbsp;&nbsp;&nbsp;B=0.05,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;демпфирование&nbsp;[Н·м·с]<br>
&nbsp;&nbsp;&nbsp;&nbsp;dt=0.001,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;шаг&nbsp;времени<br>
&nbsp;&nbsp;&nbsp;&nbsp;omega_old=0.0&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;предыдущая&nbsp;скорость<br>
)<br>
<br>
torque&nbsp;=&nbsp;TorqueSource(omega,&nbsp;torque=10.0)&nbsp;&nbsp;#&nbsp;приложенный&nbsp;момент<br>
```<br>
<br>
####&nbsp;RotationalSpring&nbsp;/&nbsp;RotationalDamper<br>
Упругие&nbsp;и&nbsp;демпфирующие&nbsp;связи&nbsp;между&nbsp;вращающимися&nbsp;телами.<br>
```python<br>
spring&nbsp;=&nbsp;RotationalSpring(omega1,&nbsp;omega2,&nbsp;K=100.0)&nbsp;&nbsp;#&nbsp;жесткость<br>
damper&nbsp;=&nbsp;RotationalDamper(omega1,&nbsp;omega2,&nbsp;B=1.0)&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;демпфирование<br>
```<br>
<br>
####&nbsp;LinearMass<br>
Поступательное&nbsp;движение:&nbsp;m·dv/dt&nbsp;=&nbsp;Σ&nbsp;F&nbsp;-&nbsp;B·v<br>
```python<br>
velocity&nbsp;=&nbsp;Variable(&quot;v&quot;,&nbsp;1)<br>
<br>
mass&nbsp;=&nbsp;LinearMass(<br>
&nbsp;&nbsp;&nbsp;&nbsp;velocity,<br>
&nbsp;&nbsp;&nbsp;&nbsp;m=1.0,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;масса&nbsp;[кг]<br>
&nbsp;&nbsp;&nbsp;&nbsp;B=0.1,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;сопротивление&nbsp;[Н·с/м]<br>
&nbsp;&nbsp;&nbsp;&nbsp;dt=0.001,<br>
&nbsp;&nbsp;&nbsp;&nbsp;v_old=0.0<br>
)<br>
```<br>
<br>
###&nbsp;4.&nbsp;Электромеханика&nbsp;(`electromechanical.py`)<br>
<br>
Элементы,&nbsp;связывающие&nbsp;электрическую&nbsp;и&nbsp;механическую&nbsp;подсистемы:<br>
<br>
####&nbsp;DCMotor<br>
Двигатель&nbsp;постоянного&nbsp;тока&nbsp;с&nbsp;электромеханической&nbsp;связью.<br>
```python<br>
from&nbsp;termin.fem&nbsp;import&nbsp;DCMotor<br>
<br>
v_plus&nbsp;=&nbsp;Variable(&quot;V+&quot;,&nbsp;1)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;напряжение&nbsp;питания<br>
v_gnd&nbsp;=&nbsp;Variable(&quot;GND&quot;,&nbsp;1)<br>
omega&nbsp;=&nbsp;Variable(&quot;omega&quot;,&nbsp;1)&nbsp;&nbsp;&nbsp;#&nbsp;угловая&nbsp;скорость&nbsp;вала<br>
<br>
motor&nbsp;=&nbsp;DCMotor(<br>
&nbsp;&nbsp;&nbsp;&nbsp;v_plus,&nbsp;v_gnd,&nbsp;omega,<br>
&nbsp;&nbsp;&nbsp;&nbsp;R=1.0,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;сопротивление&nbsp;обмотки&nbsp;[Ом]<br>
&nbsp;&nbsp;&nbsp;&nbsp;L=0.01,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;индуктивность&nbsp;обмотки&nbsp;[Гн]<br>
&nbsp;&nbsp;&nbsp;&nbsp;K_e=0.1,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;константа&nbsp;ЭДС&nbsp;[В/(рад/с)]<br>
&nbsp;&nbsp;&nbsp;&nbsp;K_t=0.1,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;константа&nbsp;момента&nbsp;[Н·м/А]<br>
&nbsp;&nbsp;&nbsp;&nbsp;dt=0.001&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;шаг&nbsp;времени&nbsp;(для&nbsp;динамики)<br>
)<br>
```<br>
<br>
Уравнения&nbsp;двигателя:<br>
-&nbsp;Электрическое:&nbsp;V&nbsp;=&nbsp;R·I&nbsp;+&nbsp;L·dI/dt&nbsp;+&nbsp;K_e·ω<br>
-&nbsp;Механическое:&nbsp;τ_motor&nbsp;=&nbsp;K_t·I<br>
<br>
##&nbsp;Динамический&nbsp;анализ<br>
<br>
Для&nbsp;задач&nbsp;с&nbsp;производными&nbsp;по&nbsp;времени&nbsp;используется&nbsp;неявная&nbsp;схема&nbsp;Эйлера.<br>
<br>
**Типичный&nbsp;цикл:**<br>
1.&nbsp;Решение&nbsp;системы&nbsp;на&nbsp;текущем&nbsp;шаге<br>
2.&nbsp;Обновление&nbsp;состояний&nbsp;элементов<br>
3.&nbsp;Переход&nbsp;к&nbsp;следующему&nbsp;шагу&nbsp;времени<br>
<br>
##&nbsp;Численные&nbsp;методы<br>
<br>
-&nbsp;**Метод&nbsp;штрафов**&nbsp;(penalty&nbsp;method)&nbsp;с&nbsp;коэффициентом&nbsp;1e10&nbsp;для&nbsp;граничных&nbsp;условий<br>
-&nbsp;**Неявная&nbsp;схема&nbsp;Эйлера**&nbsp;для&nbsp;интегрирования&nbsp;по&nbsp;времени<br>
-&nbsp;**Эффективные&nbsp;коэффициенты**:<br>
&nbsp;&nbsp;-&nbsp;Конденсатор:&nbsp;G_eff&nbsp;=&nbsp;C/dt<br>
&nbsp;&nbsp;-&nbsp;Индуктивность:&nbsp;G_eff&nbsp;=&nbsp;dt/L<br>
&nbsp;&nbsp;-&nbsp;Инерция:&nbsp;C_eff&nbsp;=&nbsp;J/dt&nbsp;+&nbsp;B<br>
<br>
##&nbsp;Тесты<br>
<br>
Тесты&nbsp;находятся&nbsp;в&nbsp;`utest/fem/`:<br>
-&nbsp;`fem_test.py`&nbsp;-&nbsp;тесты&nbsp;базового&nbsp;assembler&nbsp;(20&nbsp;тестов)<br>
-&nbsp;`mechanic_test.py`&nbsp;-&nbsp;тесты&nbsp;механических&nbsp;элементов&nbsp;(10&nbsp;тестов)<br>
-&nbsp;`electrical_test.py`&nbsp;-&nbsp;тесты&nbsp;электрических&nbsp;цепей&nbsp;(15&nbsp;тестов)<br>
-&nbsp;`multibody_test.py`&nbsp;-&nbsp;тесты&nbsp;многотельной&nbsp;динамики&nbsp;(4&nbsp;теста)<br>
-&nbsp;`electromechanical_test.py`&nbsp;-&nbsp;тесты&nbsp;электромеханики&nbsp;(4&nbsp;теста)<br>
<br>
Всего:&nbsp;**53&nbsp;теста**<br>
<br>
##&nbsp;Зависимости<br>
<br>
-&nbsp;**numpy**&nbsp;-&nbsp;матричные&nbsp;операции&nbsp;и&nbsp;линейная&nbsp;алгебра<br>
<!-- END SCAT CODE -->
</body>
</html>
