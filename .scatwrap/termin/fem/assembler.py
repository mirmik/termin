<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/fem/assembler.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
#!/usr/bin/env python3<br>
&quot;&quot;&quot;<br>
Универсальная система сборки матриц для МКЭ и других задач.<br>
<br>
Основная идея: <br>
- Система уравнений собирается из вкладов (contributions)<br>
- Каждый вклад знает, какие переменные он затрагивает<br>
- Итоговая система: A*x = b<br>
&quot;&quot;&quot;<br>
<br>
import numpy as np<br>
from typing import List, Dict, Tuple, Optional<br>
import numpy<br>
from termin.geombase.pose3 import Pose3<br>
<br>
import termin.linalg.subspaces<br>
<br>
<br>
class Variable:<br>
&#9;&quot;&quot;&quot;<br>
&#9;Переменная (неизвестная величина) в системе уравнений.<br>
&#9;<br>
&#9;Может представлять:<br>
&#9;- Перемещение узла в механике<br>
&#9;- Напряжение в узле электрической цепи<br>
&#9;- Температуру в узле тепловой задачи<br>
&#9;- И т.д.<br>
&#9;&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self, name: str, size: int = 1, tag = None):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;name: Имя переменной (для отладки)<br>
&#9;&#9;&#9;size: Размерность<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;<br>
&#9;&#9;self.size = size<br>
&#9;&#9;self.global_indices = []  # будет заполнено при сборке<br>
&#9;&#9;self.tag = tag  # произвольный тег для пользователя<br>
&#9;&#9;self._assembler = None  # ссылка на assembler, в котором зарегистрирована переменная<br>
&#9;&#9;self.value = np.zeros(size)         # текущее значение переменной (обновляется после решения)<br>
<br>
&#9;&#9;self.name_list = []<br>
&#9;&#9;if size == 1:<br>
&#9;&#9;&#9;self.name_list.append(name)<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;lst = [&quot;x&quot;, &quot;y&quot;, &quot;z&quot;, &quot;a&quot;, &quot;b&quot;, &quot;c&quot;, &quot;w&quot;]<br>
&#9;&#9;&#9;for i in range(size):<br>
&#9;&#9;&#9;&#9;vname = name + &quot;_&quot; + lst[i]<br>
&#9;&#9;&#9;&#9;self.name_list.append(vname)<br>
<br>
&#9;&#9;print(self.name_list, self.size)<br>
<br>
&#9;def __str__(self):<br>
&#9;&#9;return f&quot;{self.name_list}&quot;<br>
<br>
&#9;def __repr__(self):<br>
&#9;&#9;return f&quot;{self.name_list} (size={self.size})&quot;<br>
<br>
&#9;def names(self) -&gt; List[str]:<br>
&#9;&#9;&quot;&quot;&quot;Вернуть список имен компонент переменной&quot;&quot;&quot;<br>
&#9;&#9;return self.name_list<br>
<br>
&#9;def set_value(self, value: np.ndarray):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Установить значение переменной<br>
&#9;&#9;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;value: Значение для установки<br>
&#9;&#9;&quot;&quot;&quot;<br>
<br>
&#9;&#9;if isinstance(value, list):<br>
&#9;&#9;&#9;self.value = np.array(value)<br>
&#9;&#9;elif isinstance(value, (int, float)):<br>
&#9;&#9;&#9;self.value = np.array([value])<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;if value.shape != (self.size,):<br>
&#9;&#9;&#9;&#9;raise ValueError(f&quot;Размер входного значения {value.shape} не соответствует размеру переменной {self.size}&quot;)<br>
&#9;&#9;&#9;self.value = value <br>
&#9;&#9;&#9;<br>
&#9;<br>
<br>
<br>
<br>
class Contribution:<br>
&#9;&quot;&quot;&quot;<br>
&#9;Базовый класс для вклада в систему уравнений.<br>
&#9;<br>
&#9;Вклад - это что-то, что добавляет элементы в матрицу A и/или вектор b.<br>
&#9;Примеры:<br>
&#9;- Уравнение стержня в механике<br>
&#9;- Резистор в электрической цепи<br>
&#9;- Граничное условие<br>
&#9;- Уравнение связи между переменными<br>
&#9;&quot;&quot;&quot;<br>
&#9;<br>
&#9;def __init__(self, variables: List[Variable], domain = &quot;mechanic&quot;, assembler=None):<br>
&#9;&#9;self.variables = variables<br>
&#9;&#9;self._assembler = assembler  # ссылка на assembler, в котором зарегистрирован вклад<br>
&#9;&#9;self.assembler = assembler<br>
&#9;&#9;self.domain = domain<br>
&#9;&#9;if assembler is not None:<br>
&#9;&#9;&#9;assembler.add_contribution(self)<br>
&#9;&#9;self._rank = self._evaluate_rank()<br>
<br>
&#9;&#9;if self.domain is None:<br>
&#9;&#9;&#9;raise ValueError(f&quot;Domain must be specified for {type(self)}&quot;)<br>
<br>
&#9;def _evaluate_rank(self) -&gt; int:<br>
&#9;&#9;&quot;&quot;&quot;Возвращает размерность вклада (число уравнений, которые он добавляет)&quot;&quot;&quot;<br>
&#9;&#9;total_size = sum(var.size for var in self.variables)<br>
&#9;&#9;return total_size<br>
<br>
&#9;def get_variables(self) -&gt; List[Variable]:<br>
&#9;&#9;&quot;&quot;&quot;Возвращает список переменных, которые затрагивает этот вклад&quot;&quot;&quot;<br>
&#9;&#9;return self.variables<br>
<br>
&#9;def contribute_to_matrices(self, matrices, index_map: Dict[Variable, List[int]]):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Добавить вклад в матрицы<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;pass  <br>
&#9;<br>
&#9;def contribute_to_mass(self, A: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Добавить вклад в матрицу A<br>
&#9;&#9;Уравнение: A*x_d2 + B*x_d + C*x = b<br>
&#9;&#9;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;A: Глобальная матрица (изменяется in-place)<br>
&#9;&#9;&#9;index_map: Отображение Variable -&gt; список глобальных индексов<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;return np.zeros((self._rank, self._rank))<br>
&#9;<br>
&#9;def contribute_to_stiffness(self, K: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Добавить вклад в матрицу K<br>
&#9;&#9;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;A: Глобальная матрица (изменяется in-place)<br>
&#9;&#9;&#9;index_map: Отображение Variable -&gt; список глобальных индексов<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;return np.zeros((self._rank, self._rank))<br>
<br>
&#9;def contribute_to_damping(self, C: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Добавить вклад в матрицу C<br>
&#9;&#9;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;A: Глобальная матрица (изменяется in-place)<br>
&#9;&#9;&#9;index_map: Отображение Variable -&gt; список глобальных индексов<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;return np.zeros((self._rank, self._rank))<br>
&#9;<br>
&#9;def contribute_to_load(self, b: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Добавить вклад в вектор правой части b<br>
&#9;&#9;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;b: Глобальный вектор (изменяется in-place)<br>
&#9;&#9;&#9;index_map: Отображение Variable -&gt; список глобальных индексов<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;return np.zeros(self._rank)<br>
<br>
&#9;def finish_timestep(self, dt: float):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Завершить шаг по времени (обновить внутренние состояния, если нужно)<br>
&#9;&#9;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;dt: Шаг по времени<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;pass<br>
<br>
<br>
class Constraint:<br>
&#9;&quot;&quot;&quot;<br>
&#9;Базовый класс для голономных связей (constraints).<br>
&#9;<br>
&#9;Связь ограничивает движение системы: C·x = d<br>
&#9;<br>
&#9;В отличие от Contribution (который добавляет вклад в A и b),<br>
&#9;Constraint реализуется через множители Лагранжа и добавляет<br>
&#9;строки в расширенную систему.<br>
&#9;<br>
&#9;Примеры:<br>
&#9;- Фиксация точки в пространстве<br>
&#9;- Шарнирное соединение тел<br>
&#9;- Равенство переменных<br>
&#9;- Кинематические ограничения<br>
&#9;&quot;&quot;&quot;<br>
&#9;<br>
&#9;def __init__(self, variables: List[Variable], <br>
&#9;&#9;&#9;&#9;holonomic_lambdas: List[Variable], <br>
&#9;&#9;&#9;&#9;nonholonomic_lambdas: List[Variable], <br>
&#9;&#9;&#9;&#9;assembler=None):<br>
&#9;&#9;self.variables = variables<br>
&#9;&#9;self.holonomic_lambdas = holonomic_lambdas  # переменные для множителей Лагранжа<br>
&#9;&#9;self.nonholonomic_lambdas = nonholonomic_lambdas  # переменные для множителей Лагранжа<br>
&#9;&#9;self._assembler = assembler  # ссылка на assembler, в котором зарегистрирована связь<br>
&#9;&#9;if assembler is not None:<br>
&#9;&#9;&#9;assembler.add_constraint(self)<br>
&#9;&#9;self._rank = self._evaluate_rank()<br>
<br>
&#9;&#9;self._rank_holonomic = sum(var.size for var in self.holonomic_lambdas)<br>
&#9;&#9;self._rank_nonholonomic = sum(var.size for var in self.nonholonomic_lambdas)<br>
<br>
&#9;def _evaluate_rank(self) -&gt; int:<br>
&#9;&#9;return sum(var.size for var in self.variables)<br>
<br>
&#9;def get_variables(self) -&gt; List[Variable]:<br>
&#9;&#9;&quot;&quot;&quot;Возвращает список переменных, участвующих в связи&quot;&quot;&quot;<br>
&#9;&#9;return self.variables<br>
<br>
&#9;def get_holonomic_lambdas(self) -&gt; List[Variable]:<br>
&#9;&#9;&quot;&quot;&quot;Возвращает список переменных-множителей Лагранжа&quot;&quot;&quot;<br>
&#9;&#9;return self.holonomic_lambdas<br>
<br>
&#9;def get_nonholonomic_lambdas(self) -&gt; List[Variable]:<br>
&#9;&#9;&quot;&quot;&quot;Возвращает список переменных-множителей Лагранжа для неоголономных связей&quot;&quot;&quot;<br>
&#9;&#9;return self.nonholonomic_lambdas<br>
&#9;<br>
&#9;def get_n_holonomic(self) -&gt; int:<br>
&#9;&#9;&quot;&quot;&quot;Возвращает количество голономных уравнений связи&quot;&quot;&quot;<br>
&#9;&#9;return self._rank_holonomic<br>
<br>
&#9;def get_n_nonholonomic(self) -&gt; int:<br>
&#9;&#9;&quot;&quot;&quot;Возвращает количество неоголономных уравнений связи&quot;&quot;&quot;<br>
&#9;&#9;return self._rank_nonholonomic<br>
<br>
&#9;def contribute_to_holonomic(self, H: np.ndarray, <br>
&#9;&#9;&#9;&#9;&#9;index_map: Dict[Variable, List[int]]):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Добавить вклад в матрицу связей<br>
&#9;&#9;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;H: Матрица связей (n_constraints_total × n_dofs)<br>
&#9;&#9;&#9;index_map: Отображение Variable -&gt; список глобальных индексов<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;return np.zeros((self.get_n_holonomic(), H.shape[1]))<br>
&#9;<br>
&#9;def contribute_to_nonholonomic(self, N: np.ndarray,                                    <br>
&#9;&#9;&#9;&#9;&#9;&#9;&#9;&#9;&#9;vars_index_map: Dict[Variable, List[int]],<br>
&#9;&#9;&#9;&#9;&#9;&#9;&#9;&#9;&#9;lambdas_index_map: Dict[Variable, List[int]]):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Добавить вклад в матрицу связей для неограниченных связей<br>
<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;N: Матрица связей (n_constraints_total × n_dofs)<br>
&#9;&#9;&#9;index_map: Отображение Variable -&gt; список глобальных индексов<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;return np.zeros((self.get_n_nonholonomic(), N.shape[1]))<br>
<br>
&#9;def contribute_to_holonomic_load(self, d: np.ndarray,  holonomic_index_map: Dict[Variable, List[int]]):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Добавить вклад в правую часть связей d<br>
&#9;&#9;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;d: Вектор правой части связей<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;return np.zeros(self.get_n_holonomic())<br>
<br>
&#9;def contribute_to_nonholonomic_load(self, d: np.ndarray,  lambdas_index_map: Dict[Variable, List[int]]):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Добавить вклад в правую часть связей d для неограниченных связей<br>
<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;d: Вектор правой части связей<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;return np.zeros(self.get_n_nonholonomic())<br>
&#9;<br>
<br>
<br>
<br>
class MatrixAssembler:<br>
&#9;&quot;&quot;&quot;<br>
&#9;Сборщик матриц из вкладов.<br>
&#9;<br>
&#9;Основной класс системы - собирает глобальную матрицу A и вектор b<br>
&#9;из множества локальных вкладов.<br>
&#9;&quot;&quot;&quot;<br>
&#9;<br>
&#9;def __init__(self):<br>
&#9;&#9;self._dirty_index_map = True<br>
&#9;&#9;self.variables: List[Variable] = []<br>
&#9;&#9;self.contributions: List[Contribution] = []<br>
&#9;&#9;self.constraints: List[Constraint] = []  # Связи через множители Лагранжа<br>
<br>
&#9;&#9;self._full_index_map : Optional[Dict[Variable, List[int]]] = None<br>
&#9;&#9;self._variables_index_map: Optional[Dict[Variable, List[int]]] = None<br>
&#9;&#9;self._holonomic_index_map: Optional[Dict[Variable, List[int]]] = None<br>
&#9;&#9;self._nonholonomic_index_map: Optional[Dict[Variable, List[int]]] = None<br>
<br>
&#9;&#9;self._holonomic_constraint_vars: List[Variable] = []  # Переменные для множителей Лагранжа<br>
&#9;&#9;self._nonholonomic_constraint_vars: List[Variable] = []  # Переменные для множителей Лагранжа для неоголономных связей<br>
<br>
&#9;&#9;self._q = None  # Вектор состояний<br>
&#9;&#9;self._q_dot = None  # Вектор скоростей состояний<br>
&#9;&#9;self._q_ext_ddot = None  # Вектор ускорений состояний (расширенный)<br>
&#9;&#9;self._q_ddot = None  # Вектор ускорений состояний<br>
&#9;&#9;self._lambdas_holonomic = None  # Множители Лагранжа для голономных связей<br>
&#9;&#9;self._lambdas_nonholonomic = None  # Множители Лагранжа для неограниченных связей<br>
<br>
&#9;&#9;self._variables_by_tag: Dict = {}  # Словарь переменных по тегам для быстрого доступа<br>
&#9;&#9;<br>
&#9;def add_variable(self, name: str, size: int = 1) -&gt; Variable:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Добавить переменную в систему<br>
&#9;&#9;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;name: Имя переменной<br>
&#9;&#9;&#9;size: Размерность (1 для скаляра, 2/3 для вектора)<br>
&#9;&#9;&#9;<br>
&#9;&#9;Returns:<br>
&#9;&#9;&#9;Созданная переменная<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;var = Variable(name, size)<br>
&#9;&#9;self._register_variable(var)<br>
&#9;&#9;return var<br>
&#9;<br>
&#9;def add_holonomic_constraint_variable(self, name: str, size: int = 1) -&gt; Variable:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Добавить переменную-множитель Лагранжа в систему<br>
&#9;&#9;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;name: Имя переменной<br>
&#9;&#9;&#9;size: Размерность (1 для скаляра, 2/3 для вектора)<br>
&#9;&#9;&#9;<br>
&#9;&#9;Returns:<br>
&#9;&#9;&#9;Созданная переменная<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;var = Variable(name, size)<br>
&#9;&#9;self._register_holonomic_constraint_variable(var)<br>
&#9;&#9;return var<br>
&#9;<br>
&#9;def add_nonholonomic_constraint_variable(self, name: str, size: int = 1) -&gt; Variable:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Добавить переменную-множитель Лагранжа для неоголономных связей в систему<br>
&#9;&#9;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;name: Имя переменной<br>
&#9;&#9;&#9;size: Размерность (1 для скаляра, 2/3 для вектора)<br>
&#9;&#9;&#9;<br>
&#9;&#9;Returns:<br>
&#9;&#9;&#9;Созданная переменная<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;var = Variable(name, size)<br>
&#9;&#9;self._register_nonholonomic_constraint_variable(var)<br>
&#9;&#9;return var<br>
&#9;<br>
&#9;def _register_variable(self, var: Variable):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Зарегистрировать переменную в assembler, если она еще не зарегистрирована<br>
&#9;&#9;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;var: Переменная для регистрации<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;if var._assembler is None:<br>
&#9;&#9;&#9;var._assembler = self<br>
&#9;&#9;&#9;self.variables.append(var)<br>
&#9;&#9;&#9;self._dirty_index_map = True<br>
&#9;&#9;&#9;if var.tag not in self._variables_by_tag:<br>
&#9;&#9;&#9;&#9;self._variables_by_tag[var.tag] = []<br>
&#9;&#9;&#9;self._variables_by_tag[var.tag].append(var)<br>
&#9;&#9;elif var._assembler is not self:<br>
&#9;&#9;&#9;raise ValueError(f&quot;Переменная {var.name} уже зарегистрирована в другом assembler&quot;)<br>
<br>
&#9;def total_variables_by_tag(self, tag) -&gt; int:<br>
&#9;&#9;&quot;&quot;&quot;Вернуть количество переменных с заданным тегом&quot;&quot;&quot;<br>
&#9;&#9;if tag in self._variables_by_tag:<br>
&#9;&#9;&#9;return sum(var.size for var in self._variables_by_tag[tag])<br>
&#9;&#9;return 0<br>
&#9;&#9;<br>
&#9;def _register_holonomic_constraint_variable(self, var: Variable):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Зарегистрировать переменную-множитель Лагранжа в assembler, если она еще не зарегистрирована<br>
&#9;&#9;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;var: Переменная для регистрации<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;if var._assembler is None:<br>
&#9;&#9;&#9;var._assembler = self<br>
&#9;&#9;&#9;self._holonomic_constraint_vars.append(var)<br>
&#9;&#9;&#9;self._dirty_index_map = True<br>
&#9;&#9;elif var._assembler is not self:<br>
&#9;&#9;&#9;raise ValueError(f&quot;Переменная {var.name} уже зарегистрирована в другом assembler&quot;)<br>
&#9;&#9;<br>
&#9;def _register_nonholonomic_constraint_variable(self, var: Variable):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Зарегистрировать переменную-множитель Лагранжа в assembler, если она еще не зарегистрирована<br>
&#9;&#9;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;var: Переменная для регистрации<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;if var._assembler is None:<br>
&#9;&#9;&#9;var._assembler = self<br>
&#9;&#9;&#9;self._nonholonomic_constraint_vars.append(var)<br>
&#9;&#9;&#9;self._dirty_index_map = True<br>
&#9;&#9;elif var._assembler is not self:<br>
&#9;&#9;&#9;raise ValueError(f&quot;Переменная {var.name} уже зарегистрирована в другом assembler&quot;)<br>
&#9;<br>
&#9;def add_contribution(self, contribution: Contribution):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Добавить вклад в систему<br>
&#9;&#9;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;contribution: Вклад (уравнение, граничное условие, и т.д.)<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;# Проверяем и регистрируем все переменные, используемые вкладом<br>
&#9;&#9;for var in contribution.get_variables():<br>
&#9;&#9;&#9;self._register_variable(var)<br>
&#9;&#9;<br>
&#9;&#9;contribution._assembler = self  # регистрируем assembler<br>
&#9;&#9;self.contributions.append(contribution)<br>
&#9;<br>
&#9;def add_constraint(self, constraint: Constraint):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Добавить связь в систему<br>
&#9;&#9;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;constraint: Связь (кинематическое ограничение, и т.д.)<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;# Проверяем и регистрируем все переменные, используемые связью<br>
&#9;&#9;for lvar in constraint.get_holonomic_lambdas():<br>
&#9;&#9;&#9;self._register_holonomic_constraint_variable(lvar)<br>
<br>
&#9;&#9;for nvar in constraint.get_nonholonomic_lambdas():<br>
&#9;&#9;&#9;self._register_nonholonomic_constraint_variable(nvar)<br>
<br>
&#9;&#9;constraint._assembler = self  # регистрируем assembler<br>
&#9;&#9;self.constraints.append(constraint)<br>
<br>
&#9;def _build_index_map(self, variables) -&gt; Dict[Variable, List[int]]:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Построить отображение: Variable -&gt; глобальные индексы DOF<br>
&#9;&#9;<br>
&#9;&#9;Назначает каждой компоненте каждой переменной уникальный<br>
&#9;&#9;глобальный индекс в системе.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;index_map = {}<br>
&#9;&#9;current_index = 0<br>
&#9;&#9;<br>
&#9;&#9;for var in variables:<br>
&#9;&#9;&#9;indices = list(range(current_index, current_index + var.size))<br>
&#9;&#9;&#9;index_map[var] = indices<br>
&#9;&#9;&#9;var.global_indices = indices<br>
&#9;&#9;&#9;current_index += var.size<br>
&#9;&#9;<br>
&#9;&#9;return index_map<br>
<br>
&#9;def _build_full_index_map(self) -&gt; Dict[Variable, List[int]]:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Построить полное отображение: Variable -&gt; глобальные индексы DOF<br>
&#9;&#9;включая все переменные и переменные связей<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;full_variables = self.variables + self._holonomic_constraint_vars + self._nonholonomic_constraint_vars<br>
&#9;&#9;full_index_map = {}<br>
&#9;&#9;current_index = 0<br>
&#9;&#9;<br>
&#9;&#9;for var in full_variables:<br>
&#9;&#9;&#9;indices = list(range(current_index, current_index + var.size))<br>
&#9;&#9;&#9;full_index_map[var] = indices<br>
&#9;&#9;&#9;current_index += var.size<br>
&#9;&#9;<br>
&#9;&#9;return full_index_map<br>
<br>
&#9;def _build_index_maps(self) -&gt; Dict[Variable, List[int]]:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Построить отображение: Variable -&gt; глобальные индексы DOF<br>
&#9;&#9;<br>
&#9;&#9;Назначает каждой компоненте каждой переменной уникальный<br>
&#9;&#9;глобальный индекс в системе.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;self._index_map = self._build_index_map(self.variables)<br>
&#9;&#9;self._holonomic_index_map = self._build_index_map(self._holonomic_constraint_vars)<br>
&#9;&#9;self._nonholonomic_index_map = self._build_index_map(self._nonholonomic_constraint_vars)<br>
<br>
&#9;&#9;self._full_index_map = self._build_full_index_map()<br>
<br>
&#9;&#9;self._dirty_index_map = False<br>
&#9;&#9;#self._rebuild_state_vectors()<br>
&#9;<br>
&#9;def index_map(self) -&gt; Dict[Variable, List[int]]:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Получить текущее отображение Variable -&gt; глобальные индексы DOF<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;if self._dirty_index_map:<br>
&#9;&#9;&#9;self._build_index_maps()<br>
&#9;&#9;return self._index_map<br>
&#9;<br>
&#9;def total_dofs(self) -&gt; int:<br>
&#9;&#9;&quot;&quot;&quot;Общее количество степеней свободы в системе&quot;&quot;&quot;<br>
&#9;&#9;return sum(var.size for var in self.variables)<br>
&#9;<br>
&#9;def assemble(self) -&gt; Tuple[np.ndarray, np.ndarray]:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Собрать глобальную систему A*x = b<br>
&#9;&#9;<br>
&#9;&#9;Returns:<br>
&#9;&#9;&#9;(A, b): Матрица и вектор правой части<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;# Построить карту индексов<br>
&#9;&#9;index_map = self.index_map()<br>
&#9;&#9;<br>
&#9;&#9;# Создать глобальные матрицу и вектор<br>
&#9;&#9;n_dofs = self.total_dofs()<br>
&#9;&#9;A = np.zeros((n_dofs, n_dofs))<br>
&#9;&#9;b = np.zeros(n_dofs)<br>
&#9;&#9;<br>
&#9;&#9;# Собрать вклады<br>
&#9;&#9;for contribution in self.contributions:<br>
&#9;&#9;&#9;contribution.contribute_to_stiffness(A, index_map)<br>
&#9;&#9;&#9;contribution.contribute_to_load(b, index_map)<br>
&#9;&#9;<br>
&#9;&#9;return A, b<br>
<br>
&#9;def assemble_dynamic_system(self) -&gt; Tuple[np.ndarray, np.ndarray]:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Собрать глобальную систему A*x'' + C*x' + K*x = b<br>
&#9;&#9;<br>
&#9;&#9;Returns:<br>
&#9;&#9;&#9;(A, C, K, b): Матрицы и вектор правой части<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;# Построить карту индексов<br>
&#9;&#9;index_map = self.index_map()<br>
<br>
&#9;&#9;# Создать глобальные матрицы и вектор<br>
&#9;&#9;n_dofs = self.total_dofs()<br>
&#9;&#9;<br>
&#9;&#9;A = np.zeros((n_dofs, n_dofs))<br>
&#9;&#9;C = np.zeros((n_dofs, n_dofs))<br>
&#9;&#9;K = np.zeros((n_dofs, n_dofs))<br>
&#9;&#9;b = np.zeros(n_dofs)<br>
<br>
&#9;&#9;matrices = {<br>
&#9;&#9;&#9;&quot;mass&quot;: A,<br>
&#9;&#9;&#9;&quot;damping&quot;: C,<br>
&#9;&#9;&#9;&quot;stiffness&quot;: K,<br>
&#9;&#9;&#9;&quot;load&quot;: b<br>
&#9;&#9;}<br>
<br>
&#9;&#9;for contribution in self.contributions:<br>
&#9;&#9;&#9;contribution.contribute(matrices, index_map)<br>
<br>
&#9;&#9;return matrices<br>
<br>
<br>
&#9;def assemble_stiffness_problem(self) -&gt; Tuple[np.ndarray, np.ndarray]:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Собрать глобальную систему K*x = b<br>
<br>
&#9;&#9;Returns:<br>
&#9;&#9;&#9;(K, b): Матрица и вектор правой части<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;# Построить карту индексов<br>
&#9;&#9;index_map = self.index_map()<br>
&#9;&#9;<br>
&#9;&#9;# Создать глобальные матрицу и вектор<br>
&#9;&#9;n_dofs = self.total_dofs()<br>
&#9;&#9;K = np.zeros((n_dofs, n_dofs))<br>
&#9;&#9;b = np.zeros(n_dofs)<br>
&#9;&#9;<br>
&#9;&#9;# Собрать вклады<br>
&#9;&#9;for contribution in self.contributions:<br>
&#9;&#9;&#9;contribution.contribute_to_stiffness(K, index_map)<br>
&#9;&#9;&#9;contribution.contribute_to_load(b, index_map)<br>
&#9;&#9;<br>
&#9;&#9;return K, b<br>
&#9;<br>
&#9;def assemble_static_problem(self) -&gt; Tuple[np.ndarray, np.ndarray]:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Собрать глобальную систему K*x = b<br>
<br>
&#9;&#9;Returns:<br>
&#9;&#9;&#9;(K, b): Матрица и вектор правой части<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;# Построить карту индексов<br>
&#9;&#9;index_map = self.index_map()<br>
&#9;&#9;<br>
&#9;&#9;# Создать глобальные матрицу и вектор<br>
&#9;&#9;n_dofs = self.total_dofs()<br>
&#9;&#9;K = np.zeros((n_dofs, n_dofs))<br>
&#9;&#9;b = np.zeros(n_dofs)<br>
&#9;&#9;<br>
&#9;&#9;# Собрать вклады<br>
&#9;&#9;for contribution in self.contributions:<br>
&#9;&#9;&#9;contribution.contribute_to_mass(K, index_map)<br>
&#9;&#9;&#9;contribution.contribute_to_load(b, index_map)<br>
&#9;&#9;<br>
&#9;&#9;return K, b<br>
&#9;<br>
&#9;def assemble_dynamic_problem(self) -&gt; Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Собрать глобальную систему Ad·x'' + C·x' + K·x = b<br>
&#9;&#9;<br>
&#9;&#9;Returns:<br>
&#9;&#9;&#9;(Ad, C, K, b): Матрицы и вектор правой части<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;# Построить карту индексов<br>
&#9;&#9;index_map = self.index_map()<br>
<br>
&#9;&#9;# Создать глобальные матрицы и вектор<br>
&#9;&#9;n_dofs = self.total_dofs()<br>
&#9;&#9;A = np.zeros((n_dofs, n_dofs))<br>
&#9;&#9;C = np.zeros((n_dofs, n_dofs))<br>
&#9;&#9;K = np.zeros((n_dofs, n_dofs))<br>
&#9;&#9;b = np.zeros(n_dofs)<br>
&#9;&#9;<br>
&#9;&#9;# Собрать вклады<br>
&#9;&#9;for contribution in self.contributions:<br>
&#9;&#9;&#9;contribution.contribute_to_mass(A, index_map)<br>
&#9;&#9;&#9;contribution.contribute_to_damping(C, index_map)<br>
&#9;&#9;&#9;contribution.contribute_to_stiffness(K, index_map)<br>
&#9;&#9;&#9;contribution.contribute_to_load(b, index_map)<br>
<br>
&#9;&#9;return A, C, K, b<br>
<br>
&#9;def assemble_constraints(self) -&gt; Tuple[np.ndarray, np.ndarray]:    <br>
&#9;&#9;index_map = self.index_map()<br>
<br>
&#9;&#9;# Подсчитать общее количество связей<br>
&#9;&#9;n_hconstraints = sum(constraint.get_n_holonomic() for constraint in self.constraints)<br>
&#9;&#9;n_nhconstraints = sum(constraint.get_n_nonholonomic() for constraint in self.constraints)<br>
&#9;&#9;n_dofs = self.total_dofs()<br>
<br>
&#9;&#9;# Создать матрицу связей (n_constraints × n_dofs)<br>
&#9;&#9;H = np.zeros((n_hconstraints, n_dofs))<br>
&#9;&#9;N = np.zeros((n_nhconstraints, n_dofs))<br>
&#9;&#9;dH = np.zeros(n_hconstraints)<br>
&#9;&#9;dN = np.zeros(n_nhconstraints)<br>
<br>
&#9;&#9;# Заполнить матрицу связей<br>
&#9;&#9;for constraint in self.constraints:<br>
&#9;&#9;&#9;constraint.contribute_to_holonomic(H, index_map, self._holonomic_index_map)<br>
&#9;&#9;&#9;constraint.contribute_to_nonholonomic(N, index_map, self._nonholonomic_index_map)<br>
&#9;&#9;&#9;constraint.contribute_to_holonomic_load(dH, self._holonomic_index_map)<br>
<br>
&#9;&#9;return H, N, dH, dN<br>
<br>
&#9;def make_extended_system(<br>
&#9;&#9;&#9;self, A, C, K, b, H, N, dH, dN, q, q_d) -&gt; Tuple[np.ndarray, np.ndarray]:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Собрать расширенную систему с множителями Лагранжа<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;n_dofs = A.shape[0] + H.shape[0] + N.shape[0]<br>
<br>
&#9;&#9;A_ext = np.zeros((n_dofs, n_dofs))<br>
&#9;&#9;b_ext = np.zeros(n_dofs)<br>
<br>
&#9;&#9;#[ A H.T N.T ]<br>
&#9;&#9;#[ H 0   0   ]<br>
&#9;&#9;#[ N 0   0   ]<br>
<br>
&#9;&#9;r0 = A.shape[0]<br>
&#9;&#9;r1 = A.shape[0] + H.shape[0]<br>
&#9;&#9;r2 = A.shape[0] + H.shape[0] + N.shape[0]<br>
<br>
&#9;&#9;c0 = A.shape[1]<br>
&#9;&#9;c1 = A.shape[1] + H.shape[0]<br>
&#9;&#9;c2 = A.shape[1] + H.shape[0] + N.shape[0]<br>
<br>
&#9;&#9;A_ext[0:r0, 0:c0] = A<br>
&#9;&#9;A_ext[0:r0, c0:c1] = H.T<br>
&#9;&#9;A_ext[0:r0, c1:c2] = N.T<br>
<br>
&#9;&#9;A_ext[r0:r1, 0:c0] = H<br>
&#9;&#9;A_ext[r1:r2, 0:c0] = N<br>
<br>
&#9;&#9;b_ext[0:r0] = b - C @ q_d - K @ q<br>
&#9;&#9;b_ext[r0:r1] = dH<br>
&#9;&#9;b_ext[r1:r2] = dN<br>
<br>
&#9;&#9;return A_ext, b_ext<br>
<br>
&#9;def extended_dynamic_system_size(self) -&gt; int:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Получить размер расширенной системы с учетом связей<br>
&#9;&#9;Returns:<br>
&#9;&#9;&#9;Размер расширенной системы<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;n_dofs = self.total_dofs()<br>
&#9;&#9;n_hconstraints = sum(constraint.get_n_holonomic() for constraint in self.constraints)<br>
&#9;&#9;n_nhconstraints = sum(constraint.get_n_nonholonomic() for constraint in self.constraints)<br>
&#9;&#9;return n_dofs + n_hconstraints + n_nhconstraints<br>
<br>
&#9;def simulation_step_dynamic_with_constraints(self,<br>
&#9;&#9;&#9;dt: float,<br>
&#9;&#9;&#9;check_conditioning: bool = True,<br>
&#9;&#9;&#9;use_least_squares: bool = False) -&gt; np.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Выполнить шаг динамического решения с учетом связей<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;dt: Шаг времени<br>
&#9;&#9;&#9;check_conditioning: Проверить обусловленность матрицы и выдать предупреждение<br>
&#9;&#9;&#9;use_least_squares: Использовать lstsq вместо solve (робастнее, но медленнее)<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;self._q_ext_ddot, A, C, K, b, H, N, dH, dN = (<br>
&#9;&#9;&#9;self.solve_Ad2x_Cdx_Kx_b_with_constraints(<br>
&#9;&#9;&#9;&#9;check_conditioning=check_conditioning,<br>
&#9;&#9;&#9;&#9;use_least_squares=use_least_squares<br>
&#9;&#9;))<br>
<br>
&#9;&#9;self._q_ddot = self._q_ext_ddot[:self.total_dofs()]<br>
&#9;&#9;self._lambdas_holonomic = self._q_ext_ddot[self.total_dofs():<br>
&#9;&#9;&#9;&#9;&#9;&#9;&#9;&#9;&#9;&#9;&#9;&#9;self.total_dofs() + sum(constraint.get_n_holonomic() for constraint in self.constraints)]<br>
&#9;&#9;self._lambdas_nonholonomic = self._q_ext_ddot[self.total_dofs() + sum(constraint.get_n_holonomic() for constraint in self.constraints):]<br>
<br>
&#9;&#9;# Обновить переменные<br>
&#9;&#9;self._q_dot += self._q_ddot * dt<br>
&#9;&#9;H_add_N_T = H.T + N.T<br>
<br>
&#9;&#9;q_dot_violation = termin.linalg.subspaces.rowspace(H_add_N_T) @ self._q_dot<br>
&#9;&#9;self._q_dot -= q_dot_violation<br>
<br>
&#9;&#9;self._q += self._q_dot * dt + 0.5 * self._q_ddot * dt * dt<br>
&#9;&#9;q_violation = termin.linalg.subspaces.rowspace(H) @ self._q<br>
&#9;&#9;self._q -= q_violation<br>
<br>
&#9;&#9;self._update_variables_from_state_vectors()<br>
<br>
<br>
&#9;# def _update_variables_from_state_vectors(self):<br>
&#9;#     &quot;&quot;&quot;Обновить значения переменных из внутренних векторов состояния q и q_dot&quot;&quot;&quot;<br>
&#9;#     index_map = self.index_map()<br>
&#9;#     for var in self.variables:<br>
&#9;#         indices = index_map[var]<br>
&#9;#         var.value = self._q[indices]<br>
&#9;#         var.value_dot = self._q_dot[indices]<br>
&#9;#         var.nonlinear_integral()<br>
<br>
<br>
&#9;def _solve_system(self, A, b, <br>
&#9;&#9;&#9;&#9;&#9;check_conditioning: bool = True, <br>
&#9;&#9;&#9;use_least_squares: bool = False) -&gt; np.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Решить систему A*x = b<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;A: Матрица системы<br>
&#9;&#9;&#9;b: Вектор правой части<br>
&#9;&#9;&#9;check_conditioning: Проверить обусловленность матрицы и выдать предупреждение<br>
&#9;&#9;&#9;use_least_squares: Использовать lstsq вместо solve (робастнее, но медленнее)<br>
&#9;&#9;Returns:<br>
&#9;&#9;&#9;x: Вектор решения<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;# Проверка обусловленности<br>
&#9;&#9;if check_conditioning:<br>
&#9;&#9;&#9;cond_number = np.linalg.cond(A)<br>
&#9;&#9;&#9;if cond_number &gt; 1e10:<br>
&#9;&#9;&#9;&#9;import warnings<br>
&#9;&#9;&#9;&#9;warnings.warn(<br>
&#9;&#9;&#9;&#9;&#9;f&quot;Матрица плохо обусловлена: cond(A) = {cond_number:.2e}. &quot;<br>
&#9;&#9;&#9;&#9;&#9;f&quot;Это может быть из-за penalty method в граничных условиях. &quot;<br>
&#9;&#9;&#9;&#9;&#9;f&quot;Рассмотрите использование use_least_squares=True&quot;,<br>
&#9;&#9;&#9;&#9;&#9;RuntimeWarning<br>
&#9;&#9;&#9;&#9;)<br>
&#9;&#9;&#9;elif cond_number &gt; 1e6:<br>
&#9;&#9;&#9;&#9;import warnings<br>
&#9;&#9;&#9;&#9;warnings.warn(<br>
&#9;&#9;&#9;&#9;&#9;f&quot;Матрица имеет высокое число обусловленности: cond(A) = {cond_number:.2e}&quot;,<br>
&#9;&#9;&#9;&#9;&#9;RuntimeWarning<br>
&#9;&#9;&#9;&#9;)<br>
<br>
&#9;&#9;# Решение системы<br>
&#9;&#9;if use_least_squares:<br>
&#9;&#9;&#9;# Метод наименьших квадратов - более робастный<br>
&#9;&#9;&#9;x, residuals, rank, s = np.linalg.lstsq(A, b, rcond=None)<br>
&#9;&#9;&#9;if check_conditioning and rank &lt; len(b):<br>
&#9;&#9;&#9;&#9;import warnings<br>
&#9;&#9;&#9;&#9;warnings.warn(<br>
&#9;&#9;&#9;&#9;&#9;f&quot;Матрица вырожденная или близка к вырожденной: &quot;<br>
&#9;&#9;&#9;&#9;&#9;f&quot;rank(A) = {rank}, expected {len(b)}&quot;,<br>
&#9;&#9;&#9;&#9;&#9;RuntimeWarning<br>
&#9;&#9;&#9;&#9;)<br>
&#9;&#9;&#9;elif check_conditioning and rank &lt; len(b):<br>
&#9;&#9;&#9;&#9;import warnings<br>
&#9;&#9;&#9;&#9;warnings.warn(<br>
&#9;&#9;&#9;&#9;&#9;f&quot;Матрица вырожденная или близка к вырожденной: &quot;<br>
&#9;&#9;&#9;&#9;&#9;f&quot;rank(A) = {rank}, expected {len(b)}&quot;,<br>
&#9;&#9;&#9;&#9;&#9;RuntimeWarning<br>
&#9;&#9;&#9;&#9;)<br>
<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;# Прямое решение - быстрее, но менее робастное<br>
&#9;&#9;&#9;try:<br>
&#9;&#9;&#9;&#9;x = np.linalg.solve(A, b)<br>
&#9;&#9;&#9;except np.linalg.LinAlgError as e:<br>
&#9;&#9;&#9;&#9;raise RuntimeError(<br>
&#9;&#9;&#9;&#9;&#9;f&quot;Не удалось решить систему: {e}. &quot;<br>
&#9;&#9;&#9;&#9;&#9;f&quot;Возможно, матрица вырожденная (не хватает граничных условий?) &quot;<br>
&#9;&#9;&#9;&#9;&#9;f&quot;или плохо обусловлена. Попробуйте use_least_squares=True&quot;<br>
&#9;&#9;&#9;&#9;) from e<br>
&#9;&#9;<br>
&#9;&#9;return x<br>
<br>
&#9;# def state_vectors(self) -&gt; Tuple[np.ndarray, np.ndarray]:<br>
&#9;#     &quot;&quot;&quot;<br>
&#9;#     Собрать векторы состояния x и x_dot из текущих значений переменных<br>
&#9;&#9;<br>
&#9;#     Returns:<br>
&#9;#         x: Вектор состояний<br>
&#9;#         x_dot: Вектор скоростей состояний<br>
&#9;#     &quot;&quot;&quot;<br>
&#9;#     if self._index_map is None:<br>
&#9;#         raise RuntimeError(&quot;Система не собрана. Вызовите assemble() перед получением векторов состояния.&quot;)<br>
&#9;&#9;<br>
&#9;#     n_dofs = self.total_dofs()<br>
&#9;#     x = np.zeros(n_dofs)<br>
&#9;#     x_dot = np.zeros(n_dofs)<br>
&#9;&#9;<br>
&#9;#     for var in self.variables:<br>
&#9;#         indices = self._index_map[var]<br>
&#9;#         value, value_dot = var.state_for_assembler()<br>
&#9;#         x[indices] = value<br>
&#9;#         x_dot[indices] = value_dot<br>
&#9;&#9;<br>
&#9;#     return x, x_dot<br>
<br>
&#9;def solve_Adxx_Cdx_Kx_b(self, x_dot: np.ndarray, x: np.ndarray,<br>
&#9;&#9;&#9;&#9;&#9;&#9;&#9;check_conditioning: bool = True,<br>
&#9;&#9;&#9;&#9;&#9;&#9;&#9;use_least_squares: bool = False) -&gt; np.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Решить систему Ad·x'' + C·x' + K·x = b<br>
<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;x_dot: Вектор скоростей состояний<br>
&#9;&#9;&#9;x: Вектор состояний<br>
&#9;&#9;&#9;check_conditioning: Проверить обусловленность матрицы<br>
&#9;&#9;&#9;use_least_squares: Использовать lstsq вместо solve<br>
&#9;&#9;&#9;b: Вектор правой части<br>
&#9;&#9;&#9;&quot;&quot;&quot;<br>
<br>
&#9;&#9;Ad, C, K, b = self.assemble_Adxx_Cdx_Kx_b()<br>
&#9;&#9;v, v_dot = self.state_vectors()<br>
<br>
&#9;&#9;# Собрать левую часть<br>
&#9;&#9;A_eff = Ad<br>
&#9;&#9;A_eff += C @ x_dot<br>
&#9;&#9;A_eff += K @ x<br>
<br>
&#9;&#9;# Правая часть<br>
&#9;&#9;b_eff = b<br>
<br>
&#9;&#9;return self.solve(check_conditioning=check_conditioning,<br>
&#9;&#9;&#9;&#9;&#9;&#9;use_least_squares=use_least_squares,<br>
&#9;&#9;&#9;&#9;&#9;&#9;use_constraints=False)<br>
<br>
&#9;<br>
&#9;def set_solution_to_variables(self, x: np.ndarray):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Сохранить решение в объекты Variable<br>
&#9;&#9;<br>
&#9;&#9;После вызова этого метода каждая переменная будет иметь атрибут value<br>
&#9;&#9;с решением (скаляр или numpy array).<br>
&#9;&#9;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;x: Вектор решения<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;if self._index_map is None:<br>
&#9;&#9;&#9;raise RuntimeError(&quot;Система не собрана. Вызовите assemble() или solve()&quot;)<br>
&#9;&#9;<br>
&#9;&#9;for var in self.variables:<br>
&#9;&#9;&#9;indices = self._index_map[var]<br>
&#9;&#9;&#9;if len(indices) &gt; 1:<br>
&#9;&#9;&#9;&#9;var.value = x[indices]<br>
&#9;&#9;&#9;else:<br>
&#9;&#9;&#9;&#9;var.value = x[indices[0]]<br>
&#9;<br>
&#9;def solve_stiffness_problem(self, check_conditioning: bool = True, <br>
&#9;&#9;&#9;&#9;&#9;use_least_squares: bool = False,<br>
&#9;&#9;&#9;&#9;&#9;use_constraints: bool = True) -&gt; np.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Решить систему и сохранить результат в переменные<br>
&#9;&#9;<br>
&#9;&#9;Удобный метод, который объединяет solve() и set_solution_to_variables().<br>
&#9;&#9;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;check_conditioning: Проверить обусловленность матрицы<br>
&#9;&#9;&#9;use_least_squares: Использовать lstsq вместо solve<br>
&#9;&#9;&#9;use_constraints: Использовать множители Лагранжа для связей<br>
&#9;&#9;<br>
&#9;&#9;Returns:<br>
&#9;&#9;&#9;x: Вектор решения (также сохранен в переменных)<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;# x = self.solve(check_conditioning=check_conditioning, <br>
&#9;&#9;#                use_least_squares=use_least_squares,<br>
&#9;&#9;#                use_constraints=use_constraints)<br>
<br>
&#9;&#9;K, b = self.assemble_stiffness_problem()<br>
<br>
&#9;&#9;x = self._solve_system(A=K, b=b, check_conditioning=check_conditioning,<br>
&#9;&#9;&#9;&#9;&#9;&#9;&#9;&#9;use_least_squares=use_least_squares)<br>
<br>
&#9;&#9;self.set_solution_to_variables(x)<br>
&#9;&#9;return x<br>
&#9;<br>
&#9;def get_lagrange_multipliers(self) -&gt; Optional[np.ndarray]:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Получить множители Лагранжа после решения системы с связями<br>
&#9;&#9;<br>
&#9;&#9;Множители Лагранжа представляют собой силы реакции связей.<br>
&#9;&#9;<br>
&#9;&#9;Returns:<br>
&#9;&#9;&#9;Массив множителей Лагранжа или None, если система решалась без связей<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;return getattr(self, '_lagrange_multipliers', None)<br>
&#9;<br>
&#9;def diagnose_matrix(self) -&gt; Dict[str, any]:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Диагностика собранной матрицы системы<br>
&#9;&#9;<br>
&#9;&#9;Returns:<br>
&#9;&#9;&#9;Словарь с информацией о матрице:<br>
&#9;&#9;&#9;- condition_number: число обусловленности<br>
&#9;&#9;&#9;- is_symmetric: симметричность<br>
&#9;&#9;&#9;- is_positive_definite: положительная определённость<br>
&#9;&#9;&#9;- rank: ранг матрицы<br>
&#9;&#9;&#9;- min_eigenvalue: минимальное собственное значение<br>
&#9;&#9;&#9;- max_eigenvalue: максимальное собственное значение<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;A, b = self.assemble()<br>
&#9;&#9;<br>
&#9;&#9;info = {}<br>
&#9;&#9;<br>
&#9;&#9;# Число обусловленности<br>
&#9;&#9;info['condition_number'] = np.linalg.cond(A)<br>
&#9;&#9;<br>
&#9;&#9;# Симметричность<br>
&#9;&#9;info['is_symmetric'] = np.allclose(A, A.T)<br>
&#9;&#9;<br>
&#9;&#9;# Ранг<br>
&#9;&#9;info['rank'] = np.linalg.matrix_rank(A)<br>
&#9;&#9;info['expected_rank'] = len(A)<br>
&#9;&#9;info['is_full_rank'] = info['rank'] == info['expected_rank']<br>
&#9;&#9;<br>
&#9;&#9;# Собственные значения (только для небольших матриц)<br>
&#9;&#9;if len(A) &lt;= 100:<br>
&#9;&#9;&#9;eigenvalues = np.linalg.eigvalsh(A) if info['is_symmetric'] else np.linalg.eigvals(A)<br>
&#9;&#9;&#9;eigenvalues = np.real(eigenvalues)<br>
&#9;&#9;&#9;info['min_eigenvalue'] = np.min(eigenvalues)<br>
&#9;&#9;&#9;info['max_eigenvalue'] = np.max(eigenvalues)<br>
&#9;&#9;&#9;info['is_positive_definite'] = np.all(eigenvalues &gt; 0)<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;info['eigenvalues'] = 'Skipped (matrix too large)'<br>
&#9;&#9;&#9;info['is_positive_definite'] = None<br>
&#9;&#9;<br>
&#9;&#9;# Оценка качества<br>
&#9;&#9;cond = info['condition_number']<br>
&#9;&#9;if cond &lt; 100:<br>
&#9;&#9;&#9;info['quality'] = 'excellent'<br>
&#9;&#9;elif cond &lt; 1e4:<br>
&#9;&#9;&#9;info['quality'] = 'good'<br>
&#9;&#9;elif cond &lt; 1e8:<br>
&#9;&#9;&#9;info['quality'] = 'acceptable'<br>
&#9;&#9;elif cond &lt; 1e12:<br>
&#9;&#9;&#9;info['quality'] = 'poor'<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;info['quality'] = 'very_poor'<br>
&#9;&#9;<br>
&#9;&#9;return info<br>
&#9;<br>
&#9;@staticmethod<br>
&#9;def system_to_human_readable(<br>
&#9;&#9;A_ext: np.ndarray, <br>
&#9;&#9;b_ext: np.ndarray, <br>
&#9;&#9;variables: List[Variable]) -&gt; str:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Преобразовать расширенную систему в человекочитаемый формат<br>
&#9;&#9;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;A_ext: Расширенная матрица системы<br>
&#9;&#9;&#9;b_ext: Расширенный вектор правой части<br>
&#9;&#9;&#9;variables: Список переменных системы<br>
&#9;&#9;&#9;<br>
&#9;&#9;Returns:<br>
&#9;&#9;&#9;Строковое представление системы<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;lines = []<br>
&#9;&#9;n_vars = len(variables)<br>
&#9;&#9;<br>
&#9;&#9;for i in range(A_ext.shape[0]):<br>
&#9;&#9;&#9;row_terms = []<br>
<br>
&#9;&#9;&#9;count_of_nonzero = 0<br>
&#9;&#9;&#9;for j in range(A_ext.shape[1]):<br>
&#9;&#9;&#9;&#9;coeff = A_ext[i, j]<br>
&#9;&#9;&#9;&#9;if abs(coeff) &gt; 1e-12:<br>
&#9;&#9;&#9;&#9;&#9;var_name = variables[j]<br>
&#9;&#9;&#9;&#9;&#9;count_of_nonzero += 1<br>
<br>
&#9;&#9;&#9;&#9;&#9;if (np.isclose(coeff, 1.0)):<br>
&#9;&#9;&#9;&#9;&#9;&#9;row_terms.append(f&quot;{var_name}&quot;)<br>
&#9;&#9;&#9;&#9;&#9;elif (np.isclose(coeff, -1.0)):<br>
&#9;&#9;&#9;&#9;&#9;&#9;row_terms.append(f&quot;-{var_name}&quot;)<br>
&#9;&#9;&#9;&#9;&#9;else:<br>
&#9;&#9;&#9;&#9;&#9;&#9;row_terms.append(f&quot;{coeff}*{var_name}&quot;)<br>
&#9;&#9;&#9;row_str = &quot; &quot;<br>
&#9;&#9;&#9;row_str += &quot; + &quot;.join(row_terms)<br>
&#9;&#9;&#9;row_str += f&quot; = {b_ext[i]}&quot;<br>
<br>
&#9;&#9;&#9;if count_of_nonzero == 0:<br>
&#9;&#9;&#9;&#9;row_str = f&quot; 0 = {b_ext[i]}&quot;<br>
<br>
&#9;&#9;&#9;lines.append(row_str)<br>
&#9;&#9;<br>
&#9;&#9;return &quot;\n&quot;.join(lines)<br>
<br>
&#9;def result_to_human_readable(self, x_ext: np.ndarray, variables: List[Variable]) -&gt; str:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Преобразовать вектор решения в человекочитаемый формат<br>
<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;x_ext: Вектор решения<br>
&#9;&#9;&#9;variables: Список переменных системы<br>
<br>
&#9;&#9;Returns:<br>
&#9;&#9;&#9;Строковое представление решения<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;lines = []<br>
<br>
&#9;&#9;for i, var in enumerate(variables):<br>
&#9;&#9;&#9;lines.append(f&quot; {var} = {x_ext[i]}&quot;)<br>
&#9;&#9;return &quot;\n&quot;.join(lines)<br>
<br>
&#9;@staticmethod<br>
&#9;def matrix_diagnosis(A, tol=1e-10):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Анализирует матрицу A_ext:<br>
&#9;&#9;- вычисляет ранг<br>
&#9;&#9;- определяет нулевое подпространство<br>
&#9;&#9;- сообщает, какая часть системы линейно зависима<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;import numpy as np<br>
<br>
&#9;&#9;U, S, Vt = np.linalg.svd(A)<br>
&#9;&#9;rank = np.sum(S &gt; tol)<br>
&#9;&#9;nullity = A.shape[0] - rank<br>
<br>
&#9;&#9;return {<br>
&#9;&#9;&#9;&quot;size&quot;: A.shape,<br>
&#9;&#9;&#9;&quot;rank&quot;: rank,<br>
&#9;&#9;&#9;&quot;nullity&quot;: nullity,<br>
&#9;&#9;&#9;&quot;singular&quot;: nullity &gt; 0,<br>
&#9;&#9;&#9;&quot;small_singular_values&quot;: S[S &lt; tol],<br>
&#9;&#9;&#9;&quot;condition_number&quot;: S.max() / S.min() if S.min() &gt; 0 else np.inf<br>
&#9;&#9;}<br>
<br>
&#9;def print_diagnose(self):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Print human-readable matrix diagnostics<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;info = self.diagnose_matrix()<br>
&#9;&#9;<br>
&#9;&#9;print(&quot;=&quot; * 70)<br>
&#9;&#9;print(&quot;MATRIX SYSTEM DIAGNOSTICS&quot;)<br>
&#9;&#9;print(&quot;=&quot; * 70)<br>
&#9;&#9;<br>
&#9;&#9;# Dimensions<br>
&#9;&#9;print(f&quot;\nSystem dimensions:&quot;)<br>
&#9;&#9;print(f&quot;  Number of variables: {len(self.variables)}&quot;)<br>
&#9;&#9;print(f&quot;  Degrees of freedom (DOF): {self.total_dofs()}&quot;)<br>
&#9;&#9;<br>
&#9;&#9;# Matrix rank<br>
&#9;&#9;print(f&quot;\nMatrix rank:&quot;)<br>
&#9;&#9;print(f&quot;  Current rank: {info['rank']}&quot;)<br>
&#9;&#9;print(f&quot;  Expected rank: {info['expected_rank']}&quot;)<br>
&#9;&#9;if info['is_full_rank']:<br>
&#9;&#9;&#9;print(f&quot;  [OK] Matrix has full rank&quot;)<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;print(f&quot;  [PROBLEM] Matrix is singular (rank deficient)&quot;)<br>
&#9;&#9;&#9;print(f&quot;    Possibly missing boundary conditions&quot;)<br>
&#9;&#9;<br>
&#9;&#9;# Symmetry<br>
&#9;&#9;print(f&quot;\nSymmetry:&quot;)<br>
&#9;&#9;if info['is_symmetric']:<br>
&#9;&#9;&#9;print(f&quot;  [OK] Matrix is symmetric&quot;)<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;print(f&quot;  [PROBLEM] Matrix is not symmetric&quot;)<br>
&#9;&#9;&#9;print(f&quot;    This may indicate an error in contributions&quot;)<br>
&#9;&#9;<br>
&#9;&#9;# Conditioning<br>
&#9;&#9;print(f&quot;\nConditioning:&quot;)<br>
&#9;&#9;print(f&quot;  Condition number: {info['condition_number']:.2e}&quot;)<br>
&#9;&#9;print(f&quot;  Quality assessment: {info['quality']}&quot;)<br>
&#9;&#9;<br>
&#9;&#9;quality_desc = {<br>
&#9;&#9;&#9;'excellent': '[OK] Excellent - matrix is very well conditioned',<br>
&#9;&#9;&#9;'good': '[OK] Good - matrix is well conditioned',<br>
&#9;&#9;&#9;'acceptable': '[WARNING] Acceptable - may have small numerical errors',<br>
&#9;&#9;&#9;'poor': '[PROBLEM] Poor - high risk of numerical errors',<br>
&#9;&#9;&#9;'very_poor': '[PROBLEM] Very poor - solution may be inaccurate'<br>
&#9;&#9;}<br>
&#9;&#9;print(f&quot;  {quality_desc.get(info['quality'], '')}&quot;)<br>
&#9;&#9;<br>
&#9;&#9;if info['quality'] in ['poor', 'very_poor']:<br>
&#9;&#9;&#9;print(f&quot;\n  Recommendations:&quot;)<br>
&#9;&#9;&#9;print(f&quot;    - Reduce penalty in boundary conditions (try 1e8)&quot;)<br>
&#9;&#9;&#9;print(f&quot;    - Use use_least_squares=True when solving&quot;)<br>
&#9;&#9;&#9;print(f&quot;    - Check the scales of quantities in the problem&quot;)<br>
&#9;&#9;<br>
&#9;&#9;# Eigenvalues<br>
&#9;&#9;if info.get('min_eigenvalue') is not None:<br>
&#9;&#9;&#9;print(f&quot;\nEigenvalues:&quot;)<br>
&#9;&#9;&#9;print(f&quot;  Minimum: {info['min_eigenvalue']:.2e}&quot;)<br>
&#9;&#9;&#9;print(f&quot;  Maximum: {info['max_eigenvalue']:.2e}&quot;)<br>
&#9;&#9;&#9;<br>
&#9;&#9;&#9;if info.get('is_positive_definite'):<br>
&#9;&#9;&#9;&#9;print(f&quot;  [OK] Matrix is positive definite&quot;)<br>
&#9;&#9;&#9;else:<br>
&#9;&#9;&#9;&#9;print(f&quot;  [PROBLEM] Matrix is not positive definite&quot;)<br>
&#9;&#9;&#9;&#9;if info['min_eigenvalue'] &lt;= 0:<br>
&#9;&#9;&#9;&#9;&#9;print(f&quot;    Has non-positive eigenvalues&quot;)<br>
&#9;&#9;<br>
&#9;&#9;# Final recommendation<br>
&#9;&#9;print(f&quot;\n&quot; + &quot;=&quot; * 70)<br>
&#9;&#9;if info['is_full_rank'] and info['is_symmetric'] and info['quality'] in ['excellent', 'good', 'acceptable']:<br>
&#9;&#9;&#9;print(&quot;SUMMARY: [OK] System is ready to solve&quot;)<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;print(&quot;SUMMARY: [WARNING] Problems detected, attention required&quot;)<br>
&#9;&#9;print(&quot;=&quot; * 70)<br>
<br>
<br>
<br>
<br>
# ============================================================================<br>
# Примеры конкретных вкладов<br>
# ============================================================================<br>
<br>
class BilinearContribution(Contribution):<br>
&#9;&quot;&quot;&quot;<br>
&#9;Билинейный вклад: связь двух переменных через локальную матрицу<br>
&#9;<br>
&#9;Пример: стержень, пружина, резистор<br>
&#9;Вклад в A: A[i,j] += K_local[i,j] для пар индексов переменных<br>
&#9;&quot;&quot;&quot;<br>
&#9;<br>
&#9;def __init__(self, variables: List[Variable], K_local: np.ndarray):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;variables: Список переменных (например, [u1, u2] для стержня)<br>
&#9;&#9;&#9;K_local: Локальная матрица вклада<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;self.variables = variables<br>
&#9;&#9;self.K_local = np.array(K_local)<br>
&#9;&#9;<br>
&#9;&#9;# Проверка размерности<br>
&#9;&#9;expected_size = sum(v.size for v in variables)<br>
&#9;&#9;if self.K_local.shape != (expected_size, expected_size):<br>
&#9;&#9;&#9;raise ValueError(f&quot;Размер K_local {self.K_local.shape} не соответствует &quot;<br>
&#9;&#9;&#9;&#9;&#9;&#9;f&quot;суммарному размеру переменных {expected_size}&quot;)<br>
&#9;&#9;<br>
&#9;def contribute_to_stiffness(self, A: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
&#9;&#9;# Собрать глобальные индексы всех переменных<br>
&#9;&#9;global_indices = []<br>
&#9;&#9;for var in self.variables:<br>
&#9;&#9;&#9;global_indices.extend(index_map[var])<br>
&#9;&#9;<br>
&#9;&#9;# Добавить локальную матрицу в глобальную<br>
&#9;&#9;for i, gi in enumerate(global_indices):<br>
&#9;&#9;&#9;for j, gj in enumerate(global_indices):<br>
&#9;&#9;&#9;&#9;A[gi, gj] += self.K_local[i, j]<br>
&#9;<br>
&#9;def contribute_to_load(self, b: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
&#9;&#9;# Этот тип вклада не влияет на правую часть<br>
&#9;&#9;pass<br>
<br>
<br>
class LoadContribution(Contribution):<br>
&#9;&quot;&quot;&quot;<br>
&#9;Вклад нагрузки/источника в правую часть<br>
&#9;<br>
&#9;Пример: приложенная сила, источник тока, тепловой источник<br>
&#9;Вклад в b: b[i] += F[i]<br>
&#9;&quot;&quot;&quot;<br>
&#9;<br>
&#9;def __init__(self, variable: Variable, load: np.ndarray):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;variable: Переменная, к которой приложена нагрузка<br>
&#9;&#9;&#9;load: Вектор нагрузки (размера variable.size)<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;self.variable = variable<br>
&#9;&#9;self.load = np.atleast_1d(load)<br>
&#9;&#9;<br>
&#9;&#9;if len(self.load) != variable.size:<br>
&#9;&#9;&#9;raise ValueError(f&quot;Размер нагрузки {len(self.load)} не соответствует &quot;<br>
&#9;&#9;&#9;&#9;&#9;&#9;f&quot;размеру переменной {variable.size}&quot;)<br>
&#9;<br>
&#9;def get_variables(self) -&gt; List[Variable]:<br>
&#9;&#9;return [self.variable]<br>
&#9;<br>
&#9;def contribute_to_stiffness(self, A: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
&#9;&#9;# Не влияет на матрицу<br>
&#9;&#9;pass<br>
&#9;<br>
&#9;def contribute_to_load(self, b: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
&#9;&#9;indices = index_map[self.variable]<br>
&#9;&#9;for i, idx in enumerate(indices):<br>
&#9;&#9;&#9;b[idx] += self.load[i]<br>
<br>
<br>
class ConstraintContribution(Contribution):<br>
&#9;&quot;&quot;&quot;<br>
&#9;Граничное условие: фиксированное значение переменной<br>
&#9;<br>
&#9;Пример: u1 = 0 (закрепленный узел), V1 = 5 (источник напряжения)<br>
&#9;<br>
&#9;Реализовано через penalty method:<br>
&#9;A[i,i] += penalty<br>
&#9;b[i] += penalty * prescribed_value<br>
&#9;&quot;&quot;&quot;<br>
&#9;<br>
&#9;def __init__(self, variable: Variable, value: float, <br>
&#9;&#9;&#9;&#9;component: int = 0, penalty: float = 1e10):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;variable: Переменная для ограничения<br>
&#9;&#9;&#9;value: Предписанное значение<br>
&#9;&#9;&#9;component: Компонента переменной (0 для скаляра)<br>
&#9;&#9;&#9;penalty: Штрафной коэффициент (большое число)<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;self.variable = variable<br>
&#9;&#9;self.value = value<br>
&#9;&#9;self.component = component<br>
&#9;&#9;self.penalty = penalty<br>
&#9;&#9;<br>
&#9;&#9;if component &gt;= variable.size:<br>
&#9;&#9;&#9;raise ValueError(f&quot;Компонента {component} вне диапазона для переменной &quot;<br>
&#9;&#9;&#9;&#9;&#9;&#9;f&quot;размера {variable.size}&quot;)<br>
&#9;<br>
&#9;def get_variables(self) -&gt; List[Variable]:<br>
&#9;&#9;return [self.variable]<br>
&#9;<br>
&#9;def contribute_to_stiffness(self, A: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
&#9;&#9;indices = index_map[self.variable]<br>
&#9;&#9;idx = indices[self.component]<br>
&#9;&#9;A[idx, idx] += self.penalty<br>
&#9;<br>
&#9;def contribute_to_load(self, b: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
&#9;&#9;indices = index_map[self.variable]<br>
&#9;&#9;idx = indices[self.component]<br>
&#9;&#9;b[idx] += self.penalty * self.value<br>
<br>
<br>
class LagrangeConstraint(Constraint):<br>
&#9;&quot;&quot;&quot;<br>
&#9;Голономная связь, реализованная через множители Лагранжа.<br>
&#9;<br>
&#9;Связь имеет вид: C·x = d<br>
&#9;<br>
&#9;где C - матрица коэффициентов связи, d - правая часть.<br>
&#9;<br>
&#9;Для решения системы с связями используется расширенная матрица:<br>
&#9;[ A   C^T ] [ x ]   [ b ]<br>
&#9;[ C    0  ] [ λ ] = [ d ]<br>
&#9;<br>
&#9;Примеры:<br>
&#9;- Фиксация точки: vx = 0, vy = 0<br>
&#9;- Шарнирная связь: v + ω × r = 0<br>
&#9;- Равенство переменных: u1 = u2<br>
&#9;&quot;&quot;&quot;<br>
&#9;<br>
&#9;def __init__(self, variables: List[Variable], <br>
&#9;&#9;&#9;&#9;coefficients: List[np.ndarray], <br>
&#9;&#9;&#9;&#9;rhs: np.ndarray = None):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;variables: Список переменных, участвующих в связи<br>
&#9;&#9;&#9;coefficients: Список матриц коэффициентов для каждой переменной<br>
&#9;&#9;&#9;&#9;&#9;&#9;coefficients[i] имеет форму (n_constraints, variables[i].size)<br>
&#9;&#9;&#9;rhs: Правая часть связи (вектор размера n_constraints), по умолчанию 0<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;self.variables = variables<br>
&#9;&#9;self.coefficients = [np.atleast_2d(c) for c in coefficients]<br>
&#9;&#9;<br>
&#9;&#9;# Проверка размерностей<br>
&#9;&#9;n_constraints = self.coefficients[0].shape[0]<br>
&#9;&#9;for i, (var, coef) in enumerate(zip(variables, self.coefficients)):<br>
&#9;&#9;&#9;if coef.shape[0] != n_constraints:<br>
&#9;&#9;&#9;&#9;raise ValueError(f&quot;Все матрицы коэффициентов должны иметь одинаковое &quot;<br>
&#9;&#9;&#9;&#9;&#9;&#9;&#9;f&quot;количество строк (связей)&quot;)<br>
&#9;&#9;&#9;if coef.shape[1] != var.size:<br>
&#9;&#9;&#9;&#9;raise ValueError(f&quot;Матрица коэффициентов {i} имеет {coef.shape[1]} столбцов, &quot;<br>
&#9;&#9;&#9;&#9;&#9;&#9;&#9;f&quot;ожидалось {var.size}&quot;)<br>
&#9;&#9;<br>
&#9;&#9;self.n_constraints = n_constraints<br>
<br>
&#9;&#9;self.lambdas = Variable(name=&quot;lambda_constraint&quot;, size=n_constraints)<br>
&#9;&#9;super().__init__([self.variables[0]], [self.lambdas], [])  # Инициализация базового класса Constraint<br>
&#9;&#9;<br>
&#9;&#9;if rhs is None:<br>
&#9;&#9;&#9;self.rhs = np.zeros(n_constraints)<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;self.rhs = np.atleast_1d(rhs)<br>
&#9;&#9;&#9;if len(self.rhs) != n_constraints:<br>
&#9;&#9;&#9;&#9;raise ValueError(f&quot;Размер правой части {len(self.rhs)} не соответствует &quot;<br>
&#9;&#9;&#9;&#9;&#9;&#9;&#9;f&quot;количеству связей {n_constraints}&quot;)<br>
&#9;<br>
<br>
&#9;def contribute_to_holonomic(self, C: np.ndarray, <br>
&#9;&#9;&#9;&#9;&#9;index_map: Dict[Variable, List[int]],<br>
&#9;&#9;&#9;&#9;&#9;lambdas_index_map: Dict[Variable, List[int]]):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Добавить вклад в матрицу связей C<br>
&#9;&#9;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;C: Матрица связей (n_constraints_total × n_dofs)<br>
&#9;&#9;&#9;index_map: Отображение Variable -&gt; список глобальных индексов<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;# for var, coef in zip(self.variables, self.coefficients):<br>
&#9;&#9;#     var_indices = index_map[var]<br>
&#9;&#9;#     for i in range(self.n_constraints):<br>
&#9;&#9;#         for j, global_idx in enumerate(var_indices):<br>
&#9;&#9;#             C[i, global_idx] += coef[i, j]<br>
&#9;&#9;indices = index_map[self.variables[0]]<br>
&#9;&#9;contr_indicies = lambdas_index_map[self.lambdas]<br>
&#9;&#9;for i in range(self.n_constraints):<br>
&#9;&#9;&#9;for var, coef in zip(self.variables, self.coefficients):<br>
&#9;&#9;&#9;&#9;var_indices = index_map[var]<br>
&#9;&#9;&#9;&#9;for j, global_idx in enumerate(var_indices):<br>
&#9;&#9;&#9;&#9;&#9;C[contr_indicies[i], global_idx] += coef[i, j]<br>
<br>
&#9;def contribute_to_holonomic_load(self, d: np.ndarray,  holonomic_index_map: Dict[Variable, List[int]]):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Добавить вклад в правую часть связей d<br>
&#9;&#9;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;d: Вектор правой части связей<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;for var in self.variables:<br>
&#9;&#9;&#9;index = holonomic_index_map[var][0]<br>
&#9;&#9;&#9;d[index] += self.rhs<br>
<br>
# ============================================================================<br>
# Вспомогательные функции для удобства<br>
# ============================================================================<br>
<br>
def spring_element(u1: Variable, u2: Variable, stiffness: float) -&gt; BilinearContribution:<br>
&#9;&quot;&quot;&quot;<br>
&#9;Создать вклад пружины/стержня между двумя скалярными переменными<br>
&#9;<br>
&#9;Уравнение: F = k*(u2-u1)<br>
&#9;Матрица:  [[k, -k],<br>
&#9;&#9;&#9;[-k, k]]<br>
&#9;&quot;&quot;&quot;<br>
&#9;K = stiffness * np.array([<br>
&#9;&#9;[ 1, -1],<br>
&#9;&#9;[-1,  1]<br>
&#9;])<br>
&#9;return BilinearContribution([u1, u2], K)<br>
<br>
<br>
def conductance_element(V1: Variable, V2: Variable, conductance: float) -&gt; BilinearContribution:<br>
&#9;&quot;&quot;&quot;<br>
&#9;Создать вклад проводимости (резистор) между двумя узлами<br>
&#9;<br>
&#9;То же самое что spring_element, но с другим физическим смыслом<br>
&#9;&quot;&quot;&quot;<br>
&#9;return spring_element(V1, V2, conductance)<br>
<!-- END SCAT CODE -->
</body>
</html>
