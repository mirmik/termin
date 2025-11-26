<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/fem/README.md</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
# FEM Module<br>
<br>
Модуль метода конечных элементов (Finite Element Method) для мультифизического моделирования.<br>
<br>
## Обзор<br>
<br>
Модуль предоставляет единую платформу для решения различных физических задач через сборку и решение систем линейных уравнений вида **A·x = b**. Поддерживает как статический, так и динамический анализ с использованием неявной схемы Эйлера.<br>
<br>
## Архитектура<br>
<br>
### Базовые классы (`assembler.py`)<br>
<br>
- **Variable** - представляет степени свободы системы (DOF)<br>
- **Contribution** - базовый класс для элементов, вносящих вклад в систему<br>
- **MatrixAssembler** - сборщик глобальной матрицы из вкладов элементов<br>
<br>
Каждый элемент наследуется от `Contribution` и реализует методы:<br>
- `get_variables()` - возвращает список используемых переменных<br>
- `contribute_to_mass(A, index_map)` - добавляет вклад в матрицу жесткости<br>
- `contribute_to_b(b, index_map)` - добавляет вклад в вектор нагрузки<br>
<br>
## Модули<br>
<br>
### 1. Механика (`mechanic.py`)<br>
<br>
Конечные элементы для структурной механики:<br>
<br>
#### BarElement<br>
Стержневой элемент (ферма) для 1D и 2D задач.<br>
```python<br>
from termin.fem import Variable, BarElement, MatrixAssembler<br>
<br>
u1 = Variable(&quot;u1&quot;, 2)  # перемещение узла 1 (x, y)<br>
u2 = Variable(&quot;u2&quot;, 2)  # перемещение узла 2 (x, y)<br>
<br>
bar = BarElement(<br>
&#9;u1, u2,<br>
&#9;E=200e9,           # модуль Юнга [Па]<br>
&#9;A=0.01,            # площадь сечения [м²]<br>
&#9;L=1.0,             # длина [м]<br>
&#9;angle=0.0          # угол наклона [рад]<br>
)<br>
```<br>
<br>
#### BeamElement2D<br>
Балочный элемент Эйлера-Бернулли для изгиба.<br>
```python<br>
beam = BeamElement2D(<br>
&#9;u1, u2,<br>
&#9;E=200e9,    # модуль Юнга<br>
&#9;I=1e-4,     # момент инерции<br>
&#9;L=2.0       # длина<br>
)<br>
```<br>
<br>
#### Triangle3Node<br>
Треугольный элемент для плоского напряженного состояния.<br>
```python<br>
triangle = Triangle3Node(<br>
&#9;u1, u2, u3,<br>
&#9;E=200e9,        # модуль Юнга<br>
&#9;nu=0.3,         # коэффициент Пуассона<br>
&#9;thickness=0.01  # толщина<br>
)<br>
```<br>
<br>
### 2. Электрические цепи (`electrical.py`)<br>
<br>
Элементы для анализа электрических цепей:<br>
<br>
#### Resistor<br>
Резистор с проводимостью G = 1/R.<br>
```python<br>
from termin.fem import Resistor, VoltageSource, Ground<br>
<br>
v_plus = Variable(&quot;V+&quot;, 1)<br>
v_gnd = Variable(&quot;GND&quot;, 1)<br>
<br>
resistor = Resistor(v_plus, v_gnd, R=1000.0)  # 1 кОм<br>
source = VoltageSource(v_plus, v_gnd, V=5.0)  # 5В<br>
ground = Ground(v_gnd)<br>
```<br>
<br>
#### Capacitor / Inductor<br>
Динамические элементы с неявным интегрированием.<br>
```python<br>
capacitor = Capacitor(<br>
&#9;v_plus, v_minus,<br>
&#9;C=1e-6,           # ёмкость [Ф]<br>
&#9;dt=0.001,         # шаг времени [с]<br>
&#9;V_old=0.0         # напряжение на предыдущем шаге<br>
)<br>
<br>
inductor = Inductor(<br>
&#9;v_plus, v_minus,<br>
&#9;L=1e-3,           # индуктивность [Гн]<br>
&#9;dt=0.001,<br>
&#9;I_old=0.0         # ток на предыдущем шаге<br>
)<br>
```<br>
<br>
### 3. Многотельная динамика (`multibody.py`)<br>
<br>
Элементы для моделирования вращательного и поступательного движения:<br>
<br>
#### RotationalInertia<br>
Вращательная инерция с демпфированием: J·dω/dt = Σ τ - B·ω<br>
```python<br>
from termin.fem import RotationalInertia, TorqueSource<br>
<br>
omega = Variable(&quot;omega&quot;, 1)  # угловая скорость<br>
<br>
inertia = RotationalInertia(<br>
&#9;omega,<br>
&#9;J=0.1,              # момент инерции [кг·м²]<br>
&#9;B=0.05,             # демпфирование [Н·м·с]<br>
&#9;dt=0.001,           # шаг времени<br>
&#9;omega_old=0.0       # предыдущая скорость<br>
)<br>
<br>
torque = TorqueSource(omega, torque=10.0)  # приложенный момент<br>
```<br>
<br>
#### RotationalSpring / RotationalDamper<br>
Упругие и демпфирующие связи между вращающимися телами.<br>
```python<br>
spring = RotationalSpring(omega1, omega2, K=100.0)  # жесткость<br>
damper = RotationalDamper(omega1, omega2, B=1.0)    # демпфирование<br>
```<br>
<br>
#### LinearMass<br>
Поступательное движение: m·dv/dt = Σ F - B·v<br>
```python<br>
velocity = Variable(&quot;v&quot;, 1)<br>
<br>
mass = LinearMass(<br>
&#9;velocity,<br>
&#9;m=1.0,              # масса [кг]<br>
&#9;B=0.1,              # сопротивление [Н·с/м]<br>
&#9;dt=0.001,<br>
&#9;v_old=0.0<br>
)<br>
```<br>
<br>
### 4. Электромеханика (`electromechanical.py`)<br>
<br>
Элементы, связывающие электрическую и механическую подсистемы:<br>
<br>
#### DCMotor<br>
Двигатель постоянного тока с электромеханической связью.<br>
```python<br>
from termin.fem import DCMotor<br>
<br>
v_plus = Variable(&quot;V+&quot;, 1)     # напряжение питания<br>
v_gnd = Variable(&quot;GND&quot;, 1)<br>
omega = Variable(&quot;omega&quot;, 1)   # угловая скорость вала<br>
<br>
motor = DCMotor(<br>
&#9;v_plus, v_gnd, omega,<br>
&#9;R=1.0,              # сопротивление обмотки [Ом]<br>
&#9;L=0.01,             # индуктивность обмотки [Гн]<br>
&#9;K_e=0.1,            # константа ЭДС [В/(рад/с)]<br>
&#9;K_t=0.1,            # константа момента [Н·м/А]<br>
&#9;dt=0.001            # шаг времени (для динамики)<br>
)<br>
```<br>
<br>
Уравнения двигателя:<br>
- Электрическое: V = R·I + L·dI/dt + K_e·ω<br>
- Механическое: τ_motor = K_t·I<br>
<br>
## Динамический анализ<br>
<br>
Для задач с производными по времени используется неявная схема Эйлера.<br>
<br>
**Типичный цикл:**<br>
1. Решение системы на текущем шаге<br>
2. Обновление состояний элементов<br>
3. Переход к следующему шагу времени<br>
<br>
## Численные методы<br>
<br>
- **Метод штрафов** (penalty method) с коэффициентом 1e10 для граничных условий<br>
- **Неявная схема Эйлера** для интегрирования по времени<br>
- **Эффективные коэффициенты**:<br>
- Конденсатор: G_eff = C/dt<br>
- Индуктивность: G_eff = dt/L<br>
- Инерция: C_eff = J/dt + B<br>
<br>
## Тесты<br>
<br>
Тесты находятся в `utest/fem/`:<br>
- `fem_test.py` - тесты базового assembler (20 тестов)<br>
- `mechanic_test.py` - тесты механических элементов (10 тестов)<br>
- `electrical_test.py` - тесты электрических цепей (15 тестов)<br>
- `multibody_test.py` - тесты многотельной динамики (4 теста)<br>
- `electromechanical_test.py` - тесты электромеханики (4 теста)<br>
<br>
Всего: **53 теста**<br>
<br>
## Зависимости<br>
<br>
- **numpy** - матричные операции и линейная алгебра<br>
<!-- END SCAT CODE -->
</body>
</html>
