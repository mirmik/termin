<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/fem/README.md</title>
</head>
<body>
<pre><code>
# FEM Module

Модуль метода конечных элементов (Finite Element Method) для мультифизического моделирования.

## Обзор

Модуль предоставляет единую платформу для решения различных физических задач через сборку и решение систем линейных уравнений вида **A·x = b**. Поддерживает как статический, так и динамический анализ с использованием неявной схемы Эйлера.

## Архитектура

### Базовые классы (`assembler.py`)

- **Variable** - представляет степени свободы системы (DOF)
- **Contribution** - базовый класс для элементов, вносящих вклад в систему
- **MatrixAssembler** - сборщик глобальной матрицы из вкладов элементов

Каждый элемент наследуется от `Contribution` и реализует методы:
- `get_variables()` - возвращает список используемых переменных
- `contribute_to_mass(A, index_map)` - добавляет вклад в матрицу жесткости
- `contribute_to_b(b, index_map)` - добавляет вклад в вектор нагрузки

## Модули

### 1. Механика (`mechanic.py`)

Конечные элементы для структурной механики:

#### BarElement
Стержневой элемент (ферма) для 1D и 2D задач.
```python
from termin.fem import Variable, BarElement, MatrixAssembler

u1 = Variable(&quot;u1&quot;, 2)  # перемещение узла 1 (x, y)
u2 = Variable(&quot;u2&quot;, 2)  # перемещение узла 2 (x, y)

bar = BarElement(
    u1, u2,
    E=200e9,           # модуль Юнга [Па]
    A=0.01,            # площадь сечения [м²]
    L=1.0,             # длина [м]
    angle=0.0          # угол наклона [рад]
)
```

#### BeamElement2D
Балочный элемент Эйлера-Бернулли для изгиба.
```python
beam = BeamElement2D(
    u1, u2,
    E=200e9,    # модуль Юнга
    I=1e-4,     # момент инерции
    L=2.0       # длина
)
```

#### Triangle3Node
Треугольный элемент для плоского напряженного состояния.
```python
triangle = Triangle3Node(
    u1, u2, u3,
    E=200e9,        # модуль Юнга
    nu=0.3,         # коэффициент Пуассона
    thickness=0.01  # толщина
)
```

### 2. Электрические цепи (`electrical.py`)

Элементы для анализа электрических цепей:

#### Resistor
Резистор с проводимостью G = 1/R.
```python
from termin.fem import Resistor, VoltageSource, Ground

v_plus = Variable(&quot;V+&quot;, 1)
v_gnd = Variable(&quot;GND&quot;, 1)

resistor = Resistor(v_plus, v_gnd, R=1000.0)  # 1 кОм
source = VoltageSource(v_plus, v_gnd, V=5.0)  # 5В
ground = Ground(v_gnd)
```

#### Capacitor / Inductor
Динамические элементы с неявным интегрированием.
```python
capacitor = Capacitor(
    v_plus, v_minus,
    C=1e-6,           # ёмкость [Ф]
    dt=0.001,         # шаг времени [с]
    V_old=0.0         # напряжение на предыдущем шаге
)

inductor = Inductor(
    v_plus, v_minus,
    L=1e-3,           # индуктивность [Гн]
    dt=0.001,
    I_old=0.0         # ток на предыдущем шаге
)
```

### 3. Многотельная динамика (`multibody.py`)

Элементы для моделирования вращательного и поступательного движения:

#### RotationalInertia
Вращательная инерция с демпфированием: J·dω/dt = Σ τ - B·ω
```python
from termin.fem import RotationalInertia, TorqueSource

omega = Variable(&quot;omega&quot;, 1)  # угловая скорость

inertia = RotationalInertia(
    omega,
    J=0.1,              # момент инерции [кг·м²]
    B=0.05,             # демпфирование [Н·м·с]
    dt=0.001,           # шаг времени
    omega_old=0.0       # предыдущая скорость
)

torque = TorqueSource(omega, torque=10.0)  # приложенный момент
```

#### RotationalSpring / RotationalDamper
Упругие и демпфирующие связи между вращающимися телами.
```python
spring = RotationalSpring(omega1, omega2, K=100.0)  # жесткость
damper = RotationalDamper(omega1, omega2, B=1.0)    # демпфирование
```

#### LinearMass
Поступательное движение: m·dv/dt = Σ F - B·v
```python
velocity = Variable(&quot;v&quot;, 1)

mass = LinearMass(
    velocity,
    m=1.0,              # масса [кг]
    B=0.1,              # сопротивление [Н·с/м]
    dt=0.001,
    v_old=0.0
)
```

### 4. Электромеханика (`electromechanical.py`)

Элементы, связывающие электрическую и механическую подсистемы:

#### DCMotor
Двигатель постоянного тока с электромеханической связью.
```python
from termin.fem import DCMotor

v_plus = Variable(&quot;V+&quot;, 1)     # напряжение питания
v_gnd = Variable(&quot;GND&quot;, 1)
omega = Variable(&quot;omega&quot;, 1)   # угловая скорость вала

motor = DCMotor(
    v_plus, v_gnd, omega,
    R=1.0,              # сопротивление обмотки [Ом]
    L=0.01,             # индуктивность обмотки [Гн]
    K_e=0.1,            # константа ЭДС [В/(рад/с)]
    K_t=0.1,            # константа момента [Н·м/А]
    dt=0.001            # шаг времени (для динамики)
)
```

Уравнения двигателя:
- Электрическое: V = R·I + L·dI/dt + K_e·ω
- Механическое: τ_motor = K_t·I

## Динамический анализ

Для задач с производными по времени используется неявная схема Эйлера.

**Типичный цикл:**
1. Решение системы на текущем шаге
2. Обновление состояний элементов
3. Переход к следующему шагу времени

## Численные методы

- **Метод штрафов** (penalty method) с коэффициентом 1e10 для граничных условий
- **Неявная схема Эйлера** для интегрирования по времени
- **Эффективные коэффициенты**:
  - Конденсатор: G_eff = C/dt
  - Индуктивность: G_eff = dt/L
  - Инерция: C_eff = J/dt + B

## Тесты

Тесты находятся в `utest/fem/`:
- `fem_test.py` - тесты базового assembler (20 тестов)
- `mechanic_test.py` - тесты механических элементов (10 тестов)
- `electrical_test.py` - тесты электрических цепей (15 тестов)
- `multibody_test.py` - тесты многотельной динамики (4 теста)
- `electromechanical_test.py` - тесты электромеханики (4 теста)

Всего: **53 теста**

## Зависимости

- **numpy** - матричные операции и линейная алгебра

</code></pre>
</body>
</html>
