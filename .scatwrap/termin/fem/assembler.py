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
    &quot;&quot;&quot;<br>
    Переменная (неизвестная величина) в системе уравнений.<br>
    <br>
    Может представлять:<br>
    - Перемещение узла в механике<br>
    - Напряжение в узле электрической цепи<br>
    - Температуру в узле тепловой задачи<br>
    - И т.д.<br>
    &quot;&quot;&quot;<br>
<br>
    def __init__(self, name: str, size: int = 1, tag = None):<br>
        &quot;&quot;&quot;<br>
        Args:<br>
            name: Имя переменной (для отладки)<br>
            size: Размерность<br>
        &quot;&quot;&quot;<br>
        <br>
        self.size = size<br>
        self.global_indices = []  # будет заполнено при сборке<br>
        self.tag = tag  # произвольный тег для пользователя<br>
        self._assembler = None  # ссылка на assembler, в котором зарегистрирована переменная<br>
        self.value = np.zeros(size)         # текущее значение переменной (обновляется после решения)<br>
<br>
        self.name_list = []<br>
        if size == 1:<br>
            self.name_list.append(name)<br>
        else:<br>
            lst = [&quot;x&quot;, &quot;y&quot;, &quot;z&quot;, &quot;a&quot;, &quot;b&quot;, &quot;c&quot;, &quot;w&quot;]<br>
            for i in range(size):<br>
                vname = name + &quot;_&quot; + lst[i]<br>
                self.name_list.append(vname)<br>
<br>
        print(self.name_list, self.size)<br>
<br>
    def __str__(self):<br>
        return f&quot;{self.name_list}&quot;<br>
<br>
    def __repr__(self):<br>
        return f&quot;{self.name_list} (size={self.size})&quot;<br>
<br>
    def names(self) -&gt; List[str]:<br>
        &quot;&quot;&quot;Вернуть список имен компонент переменной&quot;&quot;&quot;<br>
        return self.name_list<br>
<br>
    def set_value(self, value: np.ndarray):<br>
        &quot;&quot;&quot;<br>
        Установить значение переменной<br>
        <br>
        Args:<br>
            value: Значение для установки<br>
        &quot;&quot;&quot;<br>
<br>
        if isinstance(value, list):<br>
            self.value = np.array(value)<br>
        elif isinstance(value, (int, float)):<br>
            self.value = np.array([value])<br>
        else:<br>
            if value.shape != (self.size,):<br>
                raise ValueError(f&quot;Размер входного значения {value.shape} не соответствует размеру переменной {self.size}&quot;)<br>
            self.value = value <br>
            <br>
    <br>
<br>
<br>
<br>
class Contribution:<br>
    &quot;&quot;&quot;<br>
    Базовый класс для вклада в систему уравнений.<br>
    <br>
    Вклад - это что-то, что добавляет элементы в матрицу A и/или вектор b.<br>
    Примеры:<br>
    - Уравнение стержня в механике<br>
    - Резистор в электрической цепи<br>
    - Граничное условие<br>
    - Уравнение связи между переменными<br>
    &quot;&quot;&quot;<br>
    <br>
    def __init__(self, variables: List[Variable], domain = &quot;mechanic&quot;, assembler=None):<br>
        self.variables = variables<br>
        self._assembler = assembler  # ссылка на assembler, в котором зарегистрирован вклад<br>
        self.assembler = assembler<br>
        self.domain = domain<br>
        if assembler is not None:<br>
            assembler.add_contribution(self)<br>
        self._rank = self._evaluate_rank()<br>
<br>
        if self.domain is None:<br>
            raise ValueError(f&quot;Domain must be specified for {type(self)}&quot;)<br>
<br>
    def _evaluate_rank(self) -&gt; int:<br>
        &quot;&quot;&quot;Возвращает размерность вклада (число уравнений, которые он добавляет)&quot;&quot;&quot;<br>
        total_size = sum(var.size for var in self.variables)<br>
        return total_size<br>
<br>
    def get_variables(self) -&gt; List[Variable]:<br>
        &quot;&quot;&quot;Возвращает список переменных, которые затрагивает этот вклад&quot;&quot;&quot;<br>
        return self.variables<br>
<br>
    def contribute_to_matrices(self, matrices, index_map: Dict[Variable, List[int]]):<br>
        &quot;&quot;&quot;<br>
        Добавить вклад в матрицы<br>
        &quot;&quot;&quot;<br>
        pass  <br>
    <br>
    def contribute_to_mass(self, A: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
        &quot;&quot;&quot;<br>
        Добавить вклад в матрицу A<br>
        Уравнение: A*x_d2 + B*x_d + C*x = b<br>
        <br>
        Args:<br>
            A: Глобальная матрица (изменяется in-place)<br>
            index_map: Отображение Variable -&gt; список глобальных индексов<br>
        &quot;&quot;&quot;<br>
        return np.zeros((self._rank, self._rank))<br>
    <br>
    def contribute_to_stiffness(self, K: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
        &quot;&quot;&quot;<br>
        Добавить вклад в матрицу K<br>
        <br>
        Args:<br>
            A: Глобальная матрица (изменяется in-place)<br>
            index_map: Отображение Variable -&gt; список глобальных индексов<br>
        &quot;&quot;&quot;<br>
        return np.zeros((self._rank, self._rank))<br>
<br>
    def contribute_to_damping(self, C: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
        &quot;&quot;&quot;<br>
        Добавить вклад в матрицу C<br>
        <br>
        Args:<br>
            A: Глобальная матрица (изменяется in-place)<br>
            index_map: Отображение Variable -&gt; список глобальных индексов<br>
        &quot;&quot;&quot;<br>
        return np.zeros((self._rank, self._rank))<br>
    <br>
    def contribute_to_load(self, b: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
        &quot;&quot;&quot;<br>
        Добавить вклад в вектор правой части b<br>
        <br>
        Args:<br>
            b: Глобальный вектор (изменяется in-place)<br>
            index_map: Отображение Variable -&gt; список глобальных индексов<br>
        &quot;&quot;&quot;<br>
        return np.zeros(self._rank)<br>
<br>
    def finish_timestep(self, dt: float):<br>
        &quot;&quot;&quot;<br>
        Завершить шаг по времени (обновить внутренние состояния, если нужно)<br>
        <br>
        Args:<br>
            dt: Шаг по времени<br>
        &quot;&quot;&quot;<br>
        pass<br>
<br>
<br>
class Constraint:<br>
    &quot;&quot;&quot;<br>
    Базовый класс для голономных связей (constraints).<br>
    <br>
    Связь ограничивает движение системы: C·x = d<br>
    <br>
    В отличие от Contribution (который добавляет вклад в A и b),<br>
    Constraint реализуется через множители Лагранжа и добавляет<br>
    строки в расширенную систему.<br>
    <br>
    Примеры:<br>
    - Фиксация точки в пространстве<br>
    - Шарнирное соединение тел<br>
    - Равенство переменных<br>
    - Кинематические ограничения<br>
    &quot;&quot;&quot;<br>
    <br>
    def __init__(self, variables: List[Variable], <br>
                 holonomic_lambdas: List[Variable], <br>
                 nonholonomic_lambdas: List[Variable], <br>
                 assembler=None):<br>
        self.variables = variables<br>
        self.holonomic_lambdas = holonomic_lambdas  # переменные для множителей Лагранжа<br>
        self.nonholonomic_lambdas = nonholonomic_lambdas  # переменные для множителей Лагранжа<br>
        self._assembler = assembler  # ссылка на assembler, в котором зарегистрирована связь<br>
        if assembler is not None:<br>
            assembler.add_constraint(self)<br>
        self._rank = self._evaluate_rank()<br>
<br>
        self._rank_holonomic = sum(var.size for var in self.holonomic_lambdas)<br>
        self._rank_nonholonomic = sum(var.size for var in self.nonholonomic_lambdas)<br>
<br>
    def _evaluate_rank(self) -&gt; int:<br>
        return sum(var.size for var in self.variables)<br>
<br>
    def get_variables(self) -&gt; List[Variable]:<br>
        &quot;&quot;&quot;Возвращает список переменных, участвующих в связи&quot;&quot;&quot;<br>
        return self.variables<br>
<br>
    def get_holonomic_lambdas(self) -&gt; List[Variable]:<br>
        &quot;&quot;&quot;Возвращает список переменных-множителей Лагранжа&quot;&quot;&quot;<br>
        return self.holonomic_lambdas<br>
<br>
    def get_nonholonomic_lambdas(self) -&gt; List[Variable]:<br>
        &quot;&quot;&quot;Возвращает список переменных-множителей Лагранжа для неоголономных связей&quot;&quot;&quot;<br>
        return self.nonholonomic_lambdas<br>
    <br>
    def get_n_holonomic(self) -&gt; int:<br>
        &quot;&quot;&quot;Возвращает количество голономных уравнений связи&quot;&quot;&quot;<br>
        return self._rank_holonomic<br>
<br>
    def get_n_nonholonomic(self) -&gt; int:<br>
        &quot;&quot;&quot;Возвращает количество неоголономных уравнений связи&quot;&quot;&quot;<br>
        return self._rank_nonholonomic<br>
<br>
    def contribute_to_holonomic(self, H: np.ndarray, <br>
                       index_map: Dict[Variable, List[int]]):<br>
        &quot;&quot;&quot;<br>
        Добавить вклад в матрицу связей<br>
        <br>
        Args:<br>
            H: Матрица связей (n_constraints_total × n_dofs)<br>
            index_map: Отображение Variable -&gt; список глобальных индексов<br>
        &quot;&quot;&quot;<br>
        return np.zeros((self.get_n_holonomic(), H.shape[1]))<br>
    <br>
    def contribute_to_nonholonomic(self, N: np.ndarray,                                    <br>
                                     vars_index_map: Dict[Variable, List[int]],<br>
                                     lambdas_index_map: Dict[Variable, List[int]]):<br>
        &quot;&quot;&quot;<br>
        Добавить вклад в матрицу связей для неограниченных связей<br>
<br>
        Args:<br>
            N: Матрица связей (n_constraints_total × n_dofs)<br>
            index_map: Отображение Variable -&gt; список глобальных индексов<br>
        &quot;&quot;&quot;<br>
        return np.zeros((self.get_n_nonholonomic(), N.shape[1]))<br>
<br>
    def contribute_to_holonomic_load(self, d: np.ndarray,  holonomic_index_map: Dict[Variable, List[int]]):<br>
        &quot;&quot;&quot;<br>
        Добавить вклад в правую часть связей d<br>
        <br>
        Args:<br>
            d: Вектор правой части связей<br>
        &quot;&quot;&quot;<br>
        return np.zeros(self.get_n_holonomic())<br>
<br>
    def contribute_to_nonholonomic_load(self, d: np.ndarray,  lambdas_index_map: Dict[Variable, List[int]]):<br>
        &quot;&quot;&quot;<br>
        Добавить вклад в правую часть связей d для неограниченных связей<br>
<br>
        Args:<br>
            d: Вектор правой части связей<br>
        &quot;&quot;&quot;<br>
        return np.zeros(self.get_n_nonholonomic())<br>
    <br>
<br>
<br>
<br>
class MatrixAssembler:<br>
    &quot;&quot;&quot;<br>
    Сборщик матриц из вкладов.<br>
    <br>
    Основной класс системы - собирает глобальную матрицу A и вектор b<br>
    из множества локальных вкладов.<br>
    &quot;&quot;&quot;<br>
    <br>
    def __init__(self):<br>
        self._dirty_index_map = True<br>
        self.variables: List[Variable] = []<br>
        self.contributions: List[Contribution] = []<br>
        self.constraints: List[Constraint] = []  # Связи через множители Лагранжа<br>
<br>
        self._full_index_map : Optional[Dict[Variable, List[int]]] = None<br>
        self._variables_index_map: Optional[Dict[Variable, List[int]]] = None<br>
        self._holonomic_index_map: Optional[Dict[Variable, List[int]]] = None<br>
        self._nonholonomic_index_map: Optional[Dict[Variable, List[int]]] = None<br>
<br>
        self._holonomic_constraint_vars: List[Variable] = []  # Переменные для множителей Лагранжа<br>
        self._nonholonomic_constraint_vars: List[Variable] = []  # Переменные для множителей Лагранжа для неоголономных связей<br>
<br>
        self._q = None  # Вектор состояний<br>
        self._q_dot = None  # Вектор скоростей состояний<br>
        self._q_ext_ddot = None  # Вектор ускорений состояний (расширенный)<br>
        self._q_ddot = None  # Вектор ускорений состояний<br>
        self._lambdas_holonomic = None  # Множители Лагранжа для голономных связей<br>
        self._lambdas_nonholonomic = None  # Множители Лагранжа для неограниченных связей<br>
<br>
        self._variables_by_tag: Dict = {}  # Словарь переменных по тегам для быстрого доступа<br>
        <br>
    def add_variable(self, name: str, size: int = 1) -&gt; Variable:<br>
        &quot;&quot;&quot;<br>
        Добавить переменную в систему<br>
        <br>
        Args:<br>
            name: Имя переменной<br>
            size: Размерность (1 для скаляра, 2/3 для вектора)<br>
            <br>
        Returns:<br>
            Созданная переменная<br>
        &quot;&quot;&quot;<br>
        var = Variable(name, size)<br>
        self._register_variable(var)<br>
        return var<br>
    <br>
    def add_holonomic_constraint_variable(self, name: str, size: int = 1) -&gt; Variable:<br>
        &quot;&quot;&quot;<br>
        Добавить переменную-множитель Лагранжа в систему<br>
        <br>
        Args:<br>
            name: Имя переменной<br>
            size: Размерность (1 для скаляра, 2/3 для вектора)<br>
            <br>
        Returns:<br>
            Созданная переменная<br>
        &quot;&quot;&quot;<br>
        var = Variable(name, size)<br>
        self._register_holonomic_constraint_variable(var)<br>
        return var<br>
    <br>
    def add_nonholonomic_constraint_variable(self, name: str, size: int = 1) -&gt; Variable:<br>
        &quot;&quot;&quot;<br>
        Добавить переменную-множитель Лагранжа для неоголономных связей в систему<br>
        <br>
        Args:<br>
            name: Имя переменной<br>
            size: Размерность (1 для скаляра, 2/3 для вектора)<br>
            <br>
        Returns:<br>
            Созданная переменная<br>
        &quot;&quot;&quot;<br>
        var = Variable(name, size)<br>
        self._register_nonholonomic_constraint_variable(var)<br>
        return var<br>
    <br>
    def _register_variable(self, var: Variable):<br>
        &quot;&quot;&quot;<br>
        Зарегистрировать переменную в assembler, если она еще не зарегистрирована<br>
        <br>
        Args:<br>
            var: Переменная для регистрации<br>
        &quot;&quot;&quot;<br>
        if var._assembler is None:<br>
            var._assembler = self<br>
            self.variables.append(var)<br>
            self._dirty_index_map = True<br>
            if var.tag not in self._variables_by_tag:<br>
                self._variables_by_tag[var.tag] = []<br>
            self._variables_by_tag[var.tag].append(var)<br>
        elif var._assembler is not self:<br>
            raise ValueError(f&quot;Переменная {var.name} уже зарегистрирована в другом assembler&quot;)<br>
<br>
    def total_variables_by_tag(self, tag) -&gt; int:<br>
        &quot;&quot;&quot;Вернуть количество переменных с заданным тегом&quot;&quot;&quot;<br>
        if tag in self._variables_by_tag:<br>
            return sum(var.size for var in self._variables_by_tag[tag])<br>
        return 0<br>
        <br>
    def _register_holonomic_constraint_variable(self, var: Variable):<br>
        &quot;&quot;&quot;<br>
        Зарегистрировать переменную-множитель Лагранжа в assembler, если она еще не зарегистрирована<br>
        <br>
        Args:<br>
            var: Переменная для регистрации<br>
        &quot;&quot;&quot;<br>
        if var._assembler is None:<br>
            var._assembler = self<br>
            self._holonomic_constraint_vars.append(var)<br>
            self._dirty_index_map = True<br>
        elif var._assembler is not self:<br>
            raise ValueError(f&quot;Переменная {var.name} уже зарегистрирована в другом assembler&quot;)<br>
        <br>
    def _register_nonholonomic_constraint_variable(self, var: Variable):<br>
        &quot;&quot;&quot;<br>
        Зарегистрировать переменную-множитель Лагранжа в assembler, если она еще не зарегистрирована<br>
        <br>
        Args:<br>
            var: Переменная для регистрации<br>
        &quot;&quot;&quot;<br>
        if var._assembler is None:<br>
            var._assembler = self<br>
            self._nonholonomic_constraint_vars.append(var)<br>
            self._dirty_index_map = True<br>
        elif var._assembler is not self:<br>
            raise ValueError(f&quot;Переменная {var.name} уже зарегистрирована в другом assembler&quot;)<br>
    <br>
    def add_contribution(self, contribution: Contribution):<br>
        &quot;&quot;&quot;<br>
        Добавить вклад в систему<br>
        <br>
        Args:<br>
            contribution: Вклад (уравнение, граничное условие, и т.д.)<br>
        &quot;&quot;&quot;<br>
        # Проверяем и регистрируем все переменные, используемые вкладом<br>
        for var in contribution.get_variables():<br>
            self._register_variable(var)<br>
        <br>
        contribution._assembler = self  # регистрируем assembler<br>
        self.contributions.append(contribution)<br>
    <br>
    def add_constraint(self, constraint: Constraint):<br>
        &quot;&quot;&quot;<br>
        Добавить связь в систему<br>
        <br>
        Args:<br>
            constraint: Связь (кинематическое ограничение, и т.д.)<br>
        &quot;&quot;&quot;<br>
        # Проверяем и регистрируем все переменные, используемые связью<br>
        for lvar in constraint.get_holonomic_lambdas():<br>
            self._register_holonomic_constraint_variable(lvar)<br>
<br>
        for nvar in constraint.get_nonholonomic_lambdas():<br>
            self._register_nonholonomic_constraint_variable(nvar)<br>
<br>
        constraint._assembler = self  # регистрируем assembler<br>
        self.constraints.append(constraint)<br>
<br>
    def _build_index_map(self, variables) -&gt; Dict[Variable, List[int]]:<br>
        &quot;&quot;&quot;<br>
        Построить отображение: Variable -&gt; глобальные индексы DOF<br>
        <br>
        Назначает каждой компоненте каждой переменной уникальный<br>
        глобальный индекс в системе.<br>
        &quot;&quot;&quot;<br>
        index_map = {}<br>
        current_index = 0<br>
        <br>
        for var in variables:<br>
            indices = list(range(current_index, current_index + var.size))<br>
            index_map[var] = indices<br>
            var.global_indices = indices<br>
            current_index += var.size<br>
        <br>
        return index_map<br>
<br>
    def _build_full_index_map(self) -&gt; Dict[Variable, List[int]]:<br>
        &quot;&quot;&quot;<br>
        Построить полное отображение: Variable -&gt; глобальные индексы DOF<br>
        включая все переменные и переменные связей<br>
        &quot;&quot;&quot;<br>
        full_variables = self.variables + self._holonomic_constraint_vars + self._nonholonomic_constraint_vars<br>
        full_index_map = {}<br>
        current_index = 0<br>
        <br>
        for var in full_variables:<br>
            indices = list(range(current_index, current_index + var.size))<br>
            full_index_map[var] = indices<br>
            current_index += var.size<br>
        <br>
        return full_index_map<br>
<br>
    def _build_index_maps(self) -&gt; Dict[Variable, List[int]]:<br>
        &quot;&quot;&quot;<br>
        Построить отображение: Variable -&gt; глобальные индексы DOF<br>
        <br>
        Назначает каждой компоненте каждой переменной уникальный<br>
        глобальный индекс в системе.<br>
        &quot;&quot;&quot;<br>
        self._index_map = self._build_index_map(self.variables)<br>
        self._holonomic_index_map = self._build_index_map(self._holonomic_constraint_vars)<br>
        self._nonholonomic_index_map = self._build_index_map(self._nonholonomic_constraint_vars)<br>
<br>
        self._full_index_map = self._build_full_index_map()<br>
<br>
        self._dirty_index_map = False<br>
        #self._rebuild_state_vectors()<br>
    <br>
    def index_map(self) -&gt; Dict[Variable, List[int]]:<br>
        &quot;&quot;&quot;<br>
        Получить текущее отображение Variable -&gt; глобальные индексы DOF<br>
        &quot;&quot;&quot;<br>
        if self._dirty_index_map:<br>
            self._build_index_maps()<br>
        return self._index_map<br>
    <br>
    def total_dofs(self) -&gt; int:<br>
        &quot;&quot;&quot;Общее количество степеней свободы в системе&quot;&quot;&quot;<br>
        return sum(var.size for var in self.variables)<br>
    <br>
    def assemble(self) -&gt; Tuple[np.ndarray, np.ndarray]:<br>
        &quot;&quot;&quot;<br>
        Собрать глобальную систему A*x = b<br>
        <br>
        Returns:<br>
            (A, b): Матрица и вектор правой части<br>
        &quot;&quot;&quot;<br>
        # Построить карту индексов<br>
        index_map = self.index_map()<br>
        <br>
        # Создать глобальные матрицу и вектор<br>
        n_dofs = self.total_dofs()<br>
        A = np.zeros((n_dofs, n_dofs))<br>
        b = np.zeros(n_dofs)<br>
        <br>
        # Собрать вклады<br>
        for contribution in self.contributions:<br>
            contribution.contribute_to_stiffness(A, index_map)<br>
            contribution.contribute_to_load(b, index_map)<br>
        <br>
        return A, b<br>
<br>
    def assemble_dynamic_system(self) -&gt; Tuple[np.ndarray, np.ndarray]:<br>
        &quot;&quot;&quot;<br>
        Собрать глобальную систему A*x'' + C*x' + K*x = b<br>
        <br>
        Returns:<br>
            (A, C, K, b): Матрицы и вектор правой части<br>
        &quot;&quot;&quot;<br>
        # Построить карту индексов<br>
        index_map = self.index_map()<br>
<br>
        # Создать глобальные матрицы и вектор<br>
        n_dofs = self.total_dofs()<br>
        <br>
        A = np.zeros((n_dofs, n_dofs))<br>
        C = np.zeros((n_dofs, n_dofs))<br>
        K = np.zeros((n_dofs, n_dofs))<br>
        b = np.zeros(n_dofs)<br>
<br>
        matrices = {<br>
            &quot;mass&quot;: A,<br>
            &quot;damping&quot;: C,<br>
            &quot;stiffness&quot;: K,<br>
            &quot;load&quot;: b<br>
        }<br>
<br>
        for contribution in self.contributions:<br>
            contribution.contribute(matrices, index_map)<br>
<br>
        return matrices<br>
<br>
<br>
    def assemble_stiffness_problem(self) -&gt; Tuple[np.ndarray, np.ndarray]:<br>
        &quot;&quot;&quot;<br>
        Собрать глобальную систему K*x = b<br>
<br>
        Returns:<br>
            (K, b): Матрица и вектор правой части<br>
        &quot;&quot;&quot;<br>
        # Построить карту индексов<br>
        index_map = self.index_map()<br>
        <br>
        # Создать глобальные матрицу и вектор<br>
        n_dofs = self.total_dofs()<br>
        K = np.zeros((n_dofs, n_dofs))<br>
        b = np.zeros(n_dofs)<br>
        <br>
        # Собрать вклады<br>
        for contribution in self.contributions:<br>
            contribution.contribute_to_stiffness(K, index_map)<br>
            contribution.contribute_to_load(b, index_map)<br>
        <br>
        return K, b<br>
    <br>
    def assemble_static_problem(self) -&gt; Tuple[np.ndarray, np.ndarray]:<br>
        &quot;&quot;&quot;<br>
        Собрать глобальную систему K*x = b<br>
<br>
        Returns:<br>
            (K, b): Матрица и вектор правой части<br>
        &quot;&quot;&quot;<br>
        # Построить карту индексов<br>
        index_map = self.index_map()<br>
        <br>
        # Создать глобальные матрицу и вектор<br>
        n_dofs = self.total_dofs()<br>
        K = np.zeros((n_dofs, n_dofs))<br>
        b = np.zeros(n_dofs)<br>
        <br>
        # Собрать вклады<br>
        for contribution in self.contributions:<br>
            contribution.contribute_to_mass(K, index_map)<br>
            contribution.contribute_to_load(b, index_map)<br>
        <br>
        return K, b<br>
    <br>
    def assemble_dynamic_problem(self) -&gt; Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:<br>
        &quot;&quot;&quot;<br>
        Собрать глобальную систему Ad·x'' + C·x' + K·x = b<br>
        <br>
        Returns:<br>
            (Ad, C, K, b): Матрицы и вектор правой части<br>
        &quot;&quot;&quot;<br>
        # Построить карту индексов<br>
        index_map = self.index_map()<br>
<br>
        # Создать глобальные матрицы и вектор<br>
        n_dofs = self.total_dofs()<br>
        A = np.zeros((n_dofs, n_dofs))<br>
        C = np.zeros((n_dofs, n_dofs))<br>
        K = np.zeros((n_dofs, n_dofs))<br>
        b = np.zeros(n_dofs)<br>
        <br>
        # Собрать вклады<br>
        for contribution in self.contributions:<br>
            contribution.contribute_to_mass(A, index_map)<br>
            contribution.contribute_to_damping(C, index_map)<br>
            contribution.contribute_to_stiffness(K, index_map)<br>
            contribution.contribute_to_load(b, index_map)<br>
<br>
        return A, C, K, b<br>
<br>
    def assemble_constraints(self) -&gt; Tuple[np.ndarray, np.ndarray]:    <br>
        index_map = self.index_map()<br>
<br>
        # Подсчитать общее количество связей<br>
        n_hconstraints = sum(constraint.get_n_holonomic() for constraint in self.constraints)<br>
        n_nhconstraints = sum(constraint.get_n_nonholonomic() for constraint in self.constraints)<br>
        n_dofs = self.total_dofs()<br>
<br>
        # Создать матрицу связей (n_constraints × n_dofs)<br>
        H = np.zeros((n_hconstraints, n_dofs))<br>
        N = np.zeros((n_nhconstraints, n_dofs))<br>
        dH = np.zeros(n_hconstraints)<br>
        dN = np.zeros(n_nhconstraints)<br>
<br>
        # Заполнить матрицу связей<br>
        for constraint in self.constraints:<br>
            constraint.contribute_to_holonomic(H, index_map, self._holonomic_index_map)<br>
            constraint.contribute_to_nonholonomic(N, index_map, self._nonholonomic_index_map)<br>
            constraint.contribute_to_holonomic_load(dH, self._holonomic_index_map)<br>
<br>
        return H, N, dH, dN<br>
<br>
    def make_extended_system(<br>
            self, A, C, K, b, H, N, dH, dN, q, q_d) -&gt; Tuple[np.ndarray, np.ndarray]:<br>
        &quot;&quot;&quot;<br>
        Собрать расширенную систему с множителями Лагранжа<br>
        &quot;&quot;&quot;<br>
        n_dofs = A.shape[0] + H.shape[0] + N.shape[0]<br>
<br>
        A_ext = np.zeros((n_dofs, n_dofs))<br>
        b_ext = np.zeros(n_dofs)<br>
<br>
        #[ A H.T N.T ]<br>
        #[ H 0   0   ]<br>
        #[ N 0   0   ]<br>
<br>
        r0 = A.shape[0]<br>
        r1 = A.shape[0] + H.shape[0]<br>
        r2 = A.shape[0] + H.shape[0] + N.shape[0]<br>
<br>
        c0 = A.shape[1]<br>
        c1 = A.shape[1] + H.shape[0]<br>
        c2 = A.shape[1] + H.shape[0] + N.shape[0]<br>
<br>
        A_ext[0:r0, 0:c0] = A<br>
        A_ext[0:r0, c0:c1] = H.T<br>
        A_ext[0:r0, c1:c2] = N.T<br>
<br>
        A_ext[r0:r1, 0:c0] = H<br>
        A_ext[r1:r2, 0:c0] = N<br>
<br>
        b_ext[0:r0] = b - C @ q_d - K @ q<br>
        b_ext[r0:r1] = dH<br>
        b_ext[r1:r2] = dN<br>
<br>
        return A_ext, b_ext<br>
<br>
    def extended_dynamic_system_size(self) -&gt; int:<br>
        &quot;&quot;&quot;<br>
        Получить размер расширенной системы с учетом связей<br>
        Returns:<br>
            Размер расширенной системы<br>
        &quot;&quot;&quot;<br>
        n_dofs = self.total_dofs()<br>
        n_hconstraints = sum(constraint.get_n_holonomic() for constraint in self.constraints)<br>
        n_nhconstraints = sum(constraint.get_n_nonholonomic() for constraint in self.constraints)<br>
        return n_dofs + n_hconstraints + n_nhconstraints<br>
<br>
    def simulation_step_dynamic_with_constraints(self,<br>
            dt: float,<br>
            check_conditioning: bool = True,<br>
            use_least_squares: bool = False) -&gt; np.ndarray:<br>
        &quot;&quot;&quot;<br>
        Выполнить шаг динамического решения с учетом связей<br>
        Args:<br>
            dt: Шаг времени<br>
            check_conditioning: Проверить обусловленность матрицы и выдать предупреждение<br>
            use_least_squares: Использовать lstsq вместо solve (робастнее, но медленнее)<br>
        &quot;&quot;&quot;<br>
        self._q_ext_ddot, A, C, K, b, H, N, dH, dN = (<br>
            self.solve_Ad2x_Cdx_Kx_b_with_constraints(<br>
                check_conditioning=check_conditioning,<br>
                use_least_squares=use_least_squares<br>
        ))<br>
<br>
        self._q_ddot = self._q_ext_ddot[:self.total_dofs()]<br>
        self._lambdas_holonomic = self._q_ext_ddot[self.total_dofs():<br>
                                                  self.total_dofs() + sum(constraint.get_n_holonomic() for constraint in self.constraints)]<br>
        self._lambdas_nonholonomic = self._q_ext_ddot[self.total_dofs() + sum(constraint.get_n_holonomic() for constraint in self.constraints):]<br>
<br>
        # Обновить переменные<br>
        self._q_dot += self._q_ddot * dt<br>
        H_add_N_T = H.T + N.T<br>
<br>
        q_dot_violation = termin.linalg.subspaces.rowspace(H_add_N_T) @ self._q_dot<br>
        self._q_dot -= q_dot_violation<br>
<br>
        self._q += self._q_dot * dt + 0.5 * self._q_ddot * dt * dt<br>
        q_violation = termin.linalg.subspaces.rowspace(H) @ self._q<br>
        self._q -= q_violation<br>
<br>
        self._update_variables_from_state_vectors()<br>
<br>
<br>
    # def _update_variables_from_state_vectors(self):<br>
    #     &quot;&quot;&quot;Обновить значения переменных из внутренних векторов состояния q и q_dot&quot;&quot;&quot;<br>
    #     index_map = self.index_map()<br>
    #     for var in self.variables:<br>
    #         indices = index_map[var]<br>
    #         var.value = self._q[indices]<br>
    #         var.value_dot = self._q_dot[indices]<br>
    #         var.nonlinear_integral()<br>
<br>
<br>
    def _solve_system(self, A, b, <br>
                      check_conditioning: bool = True, <br>
              use_least_squares: bool = False) -&gt; np.ndarray:<br>
        &quot;&quot;&quot;<br>
        Решить систему A*x = b<br>
        Args:<br>
            A: Матрица системы<br>
            b: Вектор правой части<br>
            check_conditioning: Проверить обусловленность матрицы и выдать предупреждение<br>
            use_least_squares: Использовать lstsq вместо solve (робастнее, но медленнее)<br>
        Returns:<br>
            x: Вектор решения<br>
        &quot;&quot;&quot;<br>
        # Проверка обусловленности<br>
        if check_conditioning:<br>
            cond_number = np.linalg.cond(A)<br>
            if cond_number &gt; 1e10:<br>
                import warnings<br>
                warnings.warn(<br>
                    f&quot;Матрица плохо обусловлена: cond(A) = {cond_number:.2e}. &quot;<br>
                    f&quot;Это может быть из-за penalty method в граничных условиях. &quot;<br>
                    f&quot;Рассмотрите использование use_least_squares=True&quot;,<br>
                    RuntimeWarning<br>
                )<br>
            elif cond_number &gt; 1e6:<br>
                import warnings<br>
                warnings.warn(<br>
                    f&quot;Матрица имеет высокое число обусловленности: cond(A) = {cond_number:.2e}&quot;,<br>
                    RuntimeWarning<br>
                )<br>
<br>
        # Решение системы<br>
        if use_least_squares:<br>
            # Метод наименьших квадратов - более робастный<br>
            x, residuals, rank, s = np.linalg.lstsq(A, b, rcond=None)<br>
            if check_conditioning and rank &lt; len(b):<br>
                import warnings<br>
                warnings.warn(<br>
                    f&quot;Матрица вырожденная или близка к вырожденной: &quot;<br>
                    f&quot;rank(A) = {rank}, expected {len(b)}&quot;,<br>
                    RuntimeWarning<br>
                )<br>
            elif check_conditioning and rank &lt; len(b):<br>
                import warnings<br>
                warnings.warn(<br>
                    f&quot;Матрица вырожденная или близка к вырожденной: &quot;<br>
                    f&quot;rank(A) = {rank}, expected {len(b)}&quot;,<br>
                    RuntimeWarning<br>
                )<br>
<br>
        else:<br>
            # Прямое решение - быстрее, но менее робастное<br>
            try:<br>
                x = np.linalg.solve(A, b)<br>
            except np.linalg.LinAlgError as e:<br>
                raise RuntimeError(<br>
                    f&quot;Не удалось решить систему: {e}. &quot;<br>
                    f&quot;Возможно, матрица вырожденная (не хватает граничных условий?) &quot;<br>
                    f&quot;или плохо обусловлена. Попробуйте use_least_squares=True&quot;<br>
                ) from e<br>
        <br>
        return x<br>
<br>
    # def state_vectors(self) -&gt; Tuple[np.ndarray, np.ndarray]:<br>
    #     &quot;&quot;&quot;<br>
    #     Собрать векторы состояния x и x_dot из текущих значений переменных<br>
        <br>
    #     Returns:<br>
    #         x: Вектор состояний<br>
    #         x_dot: Вектор скоростей состояний<br>
    #     &quot;&quot;&quot;<br>
    #     if self._index_map is None:<br>
    #         raise RuntimeError(&quot;Система не собрана. Вызовите assemble() перед получением векторов состояния.&quot;)<br>
        <br>
    #     n_dofs = self.total_dofs()<br>
    #     x = np.zeros(n_dofs)<br>
    #     x_dot = np.zeros(n_dofs)<br>
        <br>
    #     for var in self.variables:<br>
    #         indices = self._index_map[var]<br>
    #         value, value_dot = var.state_for_assembler()<br>
    #         x[indices] = value<br>
    #         x_dot[indices] = value_dot<br>
        <br>
    #     return x, x_dot<br>
<br>
    def solve_Adxx_Cdx_Kx_b(self, x_dot: np.ndarray, x: np.ndarray,<br>
                            check_conditioning: bool = True,<br>
                            use_least_squares: bool = False) -&gt; np.ndarray:<br>
        &quot;&quot;&quot;<br>
        Решить систему Ad·x'' + C·x' + K·x = b<br>
<br>
        Args:<br>
            x_dot: Вектор скоростей состояний<br>
            x: Вектор состояний<br>
            check_conditioning: Проверить обусловленность матрицы<br>
            use_least_squares: Использовать lstsq вместо solve<br>
            b: Вектор правой части<br>
            &quot;&quot;&quot;<br>
<br>
        Ad, C, K, b = self.assemble_Adxx_Cdx_Kx_b()<br>
        v, v_dot = self.state_vectors()<br>
<br>
        # Собрать левую часть<br>
        A_eff = Ad<br>
        A_eff += C @ x_dot<br>
        A_eff += K @ x<br>
<br>
        # Правая часть<br>
        b_eff = b<br>
<br>
        return self.solve(check_conditioning=check_conditioning,<br>
                          use_least_squares=use_least_squares,<br>
                          use_constraints=False)<br>
<br>
    <br>
    def set_solution_to_variables(self, x: np.ndarray):<br>
        &quot;&quot;&quot;<br>
        Сохранить решение в объекты Variable<br>
        <br>
        После вызова этого метода каждая переменная будет иметь атрибут value<br>
        с решением (скаляр или numpy array).<br>
        <br>
        Args:<br>
            x: Вектор решения<br>
        &quot;&quot;&quot;<br>
        if self._index_map is None:<br>
            raise RuntimeError(&quot;Система не собрана. Вызовите assemble() или solve()&quot;)<br>
        <br>
        for var in self.variables:<br>
            indices = self._index_map[var]<br>
            if len(indices) &gt; 1:<br>
                var.value = x[indices]<br>
            else:<br>
                var.value = x[indices[0]]<br>
    <br>
    def solve_stiffness_problem(self, check_conditioning: bool = True, <br>
                      use_least_squares: bool = False,<br>
                      use_constraints: bool = True) -&gt; np.ndarray:<br>
        &quot;&quot;&quot;<br>
        Решить систему и сохранить результат в переменные<br>
        <br>
        Удобный метод, который объединяет solve() и set_solution_to_variables().<br>
        <br>
        Args:<br>
            check_conditioning: Проверить обусловленность матрицы<br>
            use_least_squares: Использовать lstsq вместо solve<br>
            use_constraints: Использовать множители Лагранжа для связей<br>
        <br>
        Returns:<br>
            x: Вектор решения (также сохранен в переменных)<br>
        &quot;&quot;&quot;<br>
        # x = self.solve(check_conditioning=check_conditioning, <br>
        #                use_least_squares=use_least_squares,<br>
        #                use_constraints=use_constraints)<br>
<br>
        K, b = self.assemble_stiffness_problem()<br>
<br>
        x = self._solve_system(A=K, b=b, check_conditioning=check_conditioning,<br>
                                use_least_squares=use_least_squares)<br>
<br>
        self.set_solution_to_variables(x)<br>
        return x<br>
    <br>
    def get_lagrange_multipliers(self) -&gt; Optional[np.ndarray]:<br>
        &quot;&quot;&quot;<br>
        Получить множители Лагранжа после решения системы с связями<br>
        <br>
        Множители Лагранжа представляют собой силы реакции связей.<br>
        <br>
        Returns:<br>
            Массив множителей Лагранжа или None, если система решалась без связей<br>
        &quot;&quot;&quot;<br>
        return getattr(self, '_lagrange_multipliers', None)<br>
    <br>
    def diagnose_matrix(self) -&gt; Dict[str, any]:<br>
        &quot;&quot;&quot;<br>
        Диагностика собранной матрицы системы<br>
        <br>
        Returns:<br>
            Словарь с информацией о матрице:<br>
            - condition_number: число обусловленности<br>
            - is_symmetric: симметричность<br>
            - is_positive_definite: положительная определённость<br>
            - rank: ранг матрицы<br>
            - min_eigenvalue: минимальное собственное значение<br>
            - max_eigenvalue: максимальное собственное значение<br>
        &quot;&quot;&quot;<br>
        A, b = self.assemble()<br>
        <br>
        info = {}<br>
        <br>
        # Число обусловленности<br>
        info['condition_number'] = np.linalg.cond(A)<br>
        <br>
        # Симметричность<br>
        info['is_symmetric'] = np.allclose(A, A.T)<br>
        <br>
        # Ранг<br>
        info['rank'] = np.linalg.matrix_rank(A)<br>
        info['expected_rank'] = len(A)<br>
        info['is_full_rank'] = info['rank'] == info['expected_rank']<br>
        <br>
        # Собственные значения (только для небольших матриц)<br>
        if len(A) &lt;= 100:<br>
            eigenvalues = np.linalg.eigvalsh(A) if info['is_symmetric'] else np.linalg.eigvals(A)<br>
            eigenvalues = np.real(eigenvalues)<br>
            info['min_eigenvalue'] = np.min(eigenvalues)<br>
            info['max_eigenvalue'] = np.max(eigenvalues)<br>
            info['is_positive_definite'] = np.all(eigenvalues &gt; 0)<br>
        else:<br>
            info['eigenvalues'] = 'Skipped (matrix too large)'<br>
            info['is_positive_definite'] = None<br>
        <br>
        # Оценка качества<br>
        cond = info['condition_number']<br>
        if cond &lt; 100:<br>
            info['quality'] = 'excellent'<br>
        elif cond &lt; 1e4:<br>
            info['quality'] = 'good'<br>
        elif cond &lt; 1e8:<br>
            info['quality'] = 'acceptable'<br>
        elif cond &lt; 1e12:<br>
            info['quality'] = 'poor'<br>
        else:<br>
            info['quality'] = 'very_poor'<br>
        <br>
        return info<br>
    <br>
    @staticmethod<br>
    def system_to_human_readable(<br>
        A_ext: np.ndarray, <br>
        b_ext: np.ndarray, <br>
        variables: List[Variable]) -&gt; str:<br>
        &quot;&quot;&quot;<br>
        Преобразовать расширенную систему в человекочитаемый формат<br>
        <br>
        Args:<br>
            A_ext: Расширенная матрица системы<br>
            b_ext: Расширенный вектор правой части<br>
            variables: Список переменных системы<br>
            <br>
        Returns:<br>
            Строковое представление системы<br>
        &quot;&quot;&quot;<br>
        lines = []<br>
        n_vars = len(variables)<br>
        <br>
        for i in range(A_ext.shape[0]):<br>
            row_terms = []<br>
<br>
            count_of_nonzero = 0<br>
            for j in range(A_ext.shape[1]):<br>
                coeff = A_ext[i, j]<br>
                if abs(coeff) &gt; 1e-12:<br>
                    var_name = variables[j]<br>
                    count_of_nonzero += 1<br>
<br>
                    if (np.isclose(coeff, 1.0)):<br>
                        row_terms.append(f&quot;{var_name}&quot;)<br>
                    elif (np.isclose(coeff, -1.0)):<br>
                        row_terms.append(f&quot;-{var_name}&quot;)<br>
                    else:<br>
                        row_terms.append(f&quot;{coeff}*{var_name}&quot;)<br>
            row_str = &quot; &quot;<br>
            row_str += &quot; + &quot;.join(row_terms)<br>
            row_str += f&quot; = {b_ext[i]}&quot;<br>
<br>
            if count_of_nonzero == 0:<br>
                row_str = f&quot; 0 = {b_ext[i]}&quot;<br>
<br>
            lines.append(row_str)<br>
        <br>
        return &quot;\n&quot;.join(lines)<br>
<br>
    def result_to_human_readable(self, x_ext: np.ndarray, variables: List[Variable]) -&gt; str:<br>
        &quot;&quot;&quot;<br>
        Преобразовать вектор решения в человекочитаемый формат<br>
<br>
        Args:<br>
            x_ext: Вектор решения<br>
            variables: Список переменных системы<br>
<br>
        Returns:<br>
            Строковое представление решения<br>
        &quot;&quot;&quot;<br>
        lines = []<br>
<br>
        for i, var in enumerate(variables):<br>
            lines.append(f&quot; {var} = {x_ext[i]}&quot;)<br>
        return &quot;\n&quot;.join(lines)<br>
<br>
    @staticmethod<br>
    def matrix_diagnosis(A, tol=1e-10):<br>
        &quot;&quot;&quot;<br>
        Анализирует матрицу A_ext:<br>
        - вычисляет ранг<br>
        - определяет нулевое подпространство<br>
        - сообщает, какая часть системы линейно зависима<br>
        &quot;&quot;&quot;<br>
        import numpy as np<br>
<br>
        U, S, Vt = np.linalg.svd(A)<br>
        rank = np.sum(S &gt; tol)<br>
        nullity = A.shape[0] - rank<br>
<br>
        return {<br>
            &quot;size&quot;: A.shape,<br>
            &quot;rank&quot;: rank,<br>
            &quot;nullity&quot;: nullity,<br>
            &quot;singular&quot;: nullity &gt; 0,<br>
            &quot;small_singular_values&quot;: S[S &lt; tol],<br>
            &quot;condition_number&quot;: S.max() / S.min() if S.min() &gt; 0 else np.inf<br>
        }<br>
<br>
    def print_diagnose(self):<br>
        &quot;&quot;&quot;<br>
        Print human-readable matrix diagnostics<br>
        &quot;&quot;&quot;<br>
        info = self.diagnose_matrix()<br>
        <br>
        print(&quot;=&quot; * 70)<br>
        print(&quot;MATRIX SYSTEM DIAGNOSTICS&quot;)<br>
        print(&quot;=&quot; * 70)<br>
        <br>
        # Dimensions<br>
        print(f&quot;\nSystem dimensions:&quot;)<br>
        print(f&quot;  Number of variables: {len(self.variables)}&quot;)<br>
        print(f&quot;  Degrees of freedom (DOF): {self.total_dofs()}&quot;)<br>
        <br>
        # Matrix rank<br>
        print(f&quot;\nMatrix rank:&quot;)<br>
        print(f&quot;  Current rank: {info['rank']}&quot;)<br>
        print(f&quot;  Expected rank: {info['expected_rank']}&quot;)<br>
        if info['is_full_rank']:<br>
            print(f&quot;  [OK] Matrix has full rank&quot;)<br>
        else:<br>
            print(f&quot;  [PROBLEM] Matrix is singular (rank deficient)&quot;)<br>
            print(f&quot;    Possibly missing boundary conditions&quot;)<br>
        <br>
        # Symmetry<br>
        print(f&quot;\nSymmetry:&quot;)<br>
        if info['is_symmetric']:<br>
            print(f&quot;  [OK] Matrix is symmetric&quot;)<br>
        else:<br>
            print(f&quot;  [PROBLEM] Matrix is not symmetric&quot;)<br>
            print(f&quot;    This may indicate an error in contributions&quot;)<br>
        <br>
        # Conditioning<br>
        print(f&quot;\nConditioning:&quot;)<br>
        print(f&quot;  Condition number: {info['condition_number']:.2e}&quot;)<br>
        print(f&quot;  Quality assessment: {info['quality']}&quot;)<br>
        <br>
        quality_desc = {<br>
            'excellent': '[OK] Excellent - matrix is very well conditioned',<br>
            'good': '[OK] Good - matrix is well conditioned',<br>
            'acceptable': '[WARNING] Acceptable - may have small numerical errors',<br>
            'poor': '[PROBLEM] Poor - high risk of numerical errors',<br>
            'very_poor': '[PROBLEM] Very poor - solution may be inaccurate'<br>
        }<br>
        print(f&quot;  {quality_desc.get(info['quality'], '')}&quot;)<br>
        <br>
        if info['quality'] in ['poor', 'very_poor']:<br>
            print(f&quot;\n  Recommendations:&quot;)<br>
            print(f&quot;    - Reduce penalty in boundary conditions (try 1e8)&quot;)<br>
            print(f&quot;    - Use use_least_squares=True when solving&quot;)<br>
            print(f&quot;    - Check the scales of quantities in the problem&quot;)<br>
        <br>
        # Eigenvalues<br>
        if info.get('min_eigenvalue') is not None:<br>
            print(f&quot;\nEigenvalues:&quot;)<br>
            print(f&quot;  Minimum: {info['min_eigenvalue']:.2e}&quot;)<br>
            print(f&quot;  Maximum: {info['max_eigenvalue']:.2e}&quot;)<br>
            <br>
            if info.get('is_positive_definite'):<br>
                print(f&quot;  [OK] Matrix is positive definite&quot;)<br>
            else:<br>
                print(f&quot;  [PROBLEM] Matrix is not positive definite&quot;)<br>
                if info['min_eigenvalue'] &lt;= 0:<br>
                    print(f&quot;    Has non-positive eigenvalues&quot;)<br>
        <br>
        # Final recommendation<br>
        print(f&quot;\n&quot; + &quot;=&quot; * 70)<br>
        if info['is_full_rank'] and info['is_symmetric'] and info['quality'] in ['excellent', 'good', 'acceptable']:<br>
            print(&quot;SUMMARY: [OK] System is ready to solve&quot;)<br>
        else:<br>
            print(&quot;SUMMARY: [WARNING] Problems detected, attention required&quot;)<br>
        print(&quot;=&quot; * 70)<br>
<br>
<br>
<br>
<br>
# ============================================================================<br>
# Примеры конкретных вкладов<br>
# ============================================================================<br>
<br>
class BilinearContribution(Contribution):<br>
    &quot;&quot;&quot;<br>
    Билинейный вклад: связь двух переменных через локальную матрицу<br>
    <br>
    Пример: стержень, пружина, резистор<br>
    Вклад в A: A[i,j] += K_local[i,j] для пар индексов переменных<br>
    &quot;&quot;&quot;<br>
    <br>
    def __init__(self, variables: List[Variable], K_local: np.ndarray):<br>
        &quot;&quot;&quot;<br>
        Args:<br>
            variables: Список переменных (например, [u1, u2] для стержня)<br>
            K_local: Локальная матрица вклада<br>
        &quot;&quot;&quot;<br>
        self.variables = variables<br>
        self.K_local = np.array(K_local)<br>
        <br>
        # Проверка размерности<br>
        expected_size = sum(v.size for v in variables)<br>
        if self.K_local.shape != (expected_size, expected_size):<br>
            raise ValueError(f&quot;Размер K_local {self.K_local.shape} не соответствует &quot;<br>
                           f&quot;суммарному размеру переменных {expected_size}&quot;)<br>
        <br>
    def contribute_to_stiffness(self, A: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
        # Собрать глобальные индексы всех переменных<br>
        global_indices = []<br>
        for var in self.variables:<br>
            global_indices.extend(index_map[var])<br>
        <br>
        # Добавить локальную матрицу в глобальную<br>
        for i, gi in enumerate(global_indices):<br>
            for j, gj in enumerate(global_indices):<br>
                A[gi, gj] += self.K_local[i, j]<br>
    <br>
    def contribute_to_load(self, b: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
        # Этот тип вклада не влияет на правую часть<br>
        pass<br>
<br>
<br>
class LoadContribution(Contribution):<br>
    &quot;&quot;&quot;<br>
    Вклад нагрузки/источника в правую часть<br>
    <br>
    Пример: приложенная сила, источник тока, тепловой источник<br>
    Вклад в b: b[i] += F[i]<br>
    &quot;&quot;&quot;<br>
    <br>
    def __init__(self, variable: Variable, load: np.ndarray):<br>
        &quot;&quot;&quot;<br>
        Args:<br>
            variable: Переменная, к которой приложена нагрузка<br>
            load: Вектор нагрузки (размера variable.size)<br>
        &quot;&quot;&quot;<br>
        self.variable = variable<br>
        self.load = np.atleast_1d(load)<br>
        <br>
        if len(self.load) != variable.size:<br>
            raise ValueError(f&quot;Размер нагрузки {len(self.load)} не соответствует &quot;<br>
                           f&quot;размеру переменной {variable.size}&quot;)<br>
    <br>
    def get_variables(self) -&gt; List[Variable]:<br>
        return [self.variable]<br>
    <br>
    def contribute_to_stiffness(self, A: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
        # Не влияет на матрицу<br>
        pass<br>
    <br>
    def contribute_to_load(self, b: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
        indices = index_map[self.variable]<br>
        for i, idx in enumerate(indices):<br>
            b[idx] += self.load[i]<br>
<br>
<br>
class ConstraintContribution(Contribution):<br>
    &quot;&quot;&quot;<br>
    Граничное условие: фиксированное значение переменной<br>
    <br>
    Пример: u1 = 0 (закрепленный узел), V1 = 5 (источник напряжения)<br>
    <br>
    Реализовано через penalty method:<br>
    A[i,i] += penalty<br>
    b[i] += penalty * prescribed_value<br>
    &quot;&quot;&quot;<br>
    <br>
    def __init__(self, variable: Variable, value: float, <br>
                 component: int = 0, penalty: float = 1e10):<br>
        &quot;&quot;&quot;<br>
        Args:<br>
            variable: Переменная для ограничения<br>
            value: Предписанное значение<br>
            component: Компонента переменной (0 для скаляра)<br>
            penalty: Штрафной коэффициент (большое число)<br>
        &quot;&quot;&quot;<br>
        self.variable = variable<br>
        self.value = value<br>
        self.component = component<br>
        self.penalty = penalty<br>
        <br>
        if component &gt;= variable.size:<br>
            raise ValueError(f&quot;Компонента {component} вне диапазона для переменной &quot;<br>
                           f&quot;размера {variable.size}&quot;)<br>
    <br>
    def get_variables(self) -&gt; List[Variable]:<br>
        return [self.variable]<br>
    <br>
    def contribute_to_stiffness(self, A: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
        indices = index_map[self.variable]<br>
        idx = indices[self.component]<br>
        A[idx, idx] += self.penalty<br>
    <br>
    def contribute_to_load(self, b: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
        indices = index_map[self.variable]<br>
        idx = indices[self.component]<br>
        b[idx] += self.penalty * self.value<br>
<br>
<br>
class LagrangeConstraint(Constraint):<br>
    &quot;&quot;&quot;<br>
    Голономная связь, реализованная через множители Лагранжа.<br>
    <br>
    Связь имеет вид: C·x = d<br>
    <br>
    где C - матрица коэффициентов связи, d - правая часть.<br>
    <br>
    Для решения системы с связями используется расширенная матрица:<br>
    [ A   C^T ] [ x ]   [ b ]<br>
    [ C    0  ] [ λ ] = [ d ]<br>
    <br>
    Примеры:<br>
    - Фиксация точки: vx = 0, vy = 0<br>
    - Шарнирная связь: v + ω × r = 0<br>
    - Равенство переменных: u1 = u2<br>
    &quot;&quot;&quot;<br>
    <br>
    def __init__(self, variables: List[Variable], <br>
                 coefficients: List[np.ndarray], <br>
                 rhs: np.ndarray = None):<br>
        &quot;&quot;&quot;<br>
        Args:<br>
            variables: Список переменных, участвующих в связи<br>
            coefficients: Список матриц коэффициентов для каждой переменной<br>
                         coefficients[i] имеет форму (n_constraints, variables[i].size)<br>
            rhs: Правая часть связи (вектор размера n_constraints), по умолчанию 0<br>
        &quot;&quot;&quot;<br>
        self.variables = variables<br>
        self.coefficients = [np.atleast_2d(c) for c in coefficients]<br>
        <br>
        # Проверка размерностей<br>
        n_constraints = self.coefficients[0].shape[0]<br>
        for i, (var, coef) in enumerate(zip(variables, self.coefficients)):<br>
            if coef.shape[0] != n_constraints:<br>
                raise ValueError(f&quot;Все матрицы коэффициентов должны иметь одинаковое &quot;<br>
                               f&quot;количество строк (связей)&quot;)<br>
            if coef.shape[1] != var.size:<br>
                raise ValueError(f&quot;Матрица коэффициентов {i} имеет {coef.shape[1]} столбцов, &quot;<br>
                               f&quot;ожидалось {var.size}&quot;)<br>
        <br>
        self.n_constraints = n_constraints<br>
<br>
        self.lambdas = Variable(name=&quot;lambda_constraint&quot;, size=n_constraints)<br>
        super().__init__([self.variables[0]], [self.lambdas], [])  # Инициализация базового класса Constraint<br>
        <br>
        if rhs is None:<br>
            self.rhs = np.zeros(n_constraints)<br>
        else:<br>
            self.rhs = np.atleast_1d(rhs)<br>
            if len(self.rhs) != n_constraints:<br>
                raise ValueError(f&quot;Размер правой части {len(self.rhs)} не соответствует &quot;<br>
                               f&quot;количеству связей {n_constraints}&quot;)<br>
    <br>
<br>
    def contribute_to_holonomic(self, C: np.ndarray, <br>
                       index_map: Dict[Variable, List[int]],<br>
                       lambdas_index_map: Dict[Variable, List[int]]):<br>
        &quot;&quot;&quot;<br>
        Добавить вклад в матрицу связей C<br>
        <br>
        Args:<br>
            C: Матрица связей (n_constraints_total × n_dofs)<br>
            index_map: Отображение Variable -&gt; список глобальных индексов<br>
        &quot;&quot;&quot;<br>
        # for var, coef in zip(self.variables, self.coefficients):<br>
        #     var_indices = index_map[var]<br>
        #     for i in range(self.n_constraints):<br>
        #         for j, global_idx in enumerate(var_indices):<br>
        #             C[i, global_idx] += coef[i, j]<br>
        indices = index_map[self.variables[0]]<br>
        contr_indicies = lambdas_index_map[self.lambdas]<br>
        for i in range(self.n_constraints):<br>
            for var, coef in zip(self.variables, self.coefficients):<br>
                var_indices = index_map[var]<br>
                for j, global_idx in enumerate(var_indices):<br>
                    C[contr_indicies[i], global_idx] += coef[i, j]<br>
<br>
    def contribute_to_holonomic_load(self, d: np.ndarray,  holonomic_index_map: Dict[Variable, List[int]]):<br>
        &quot;&quot;&quot;<br>
        Добавить вклад в правую часть связей d<br>
        <br>
        Args:<br>
            d: Вектор правой части связей<br>
        &quot;&quot;&quot;<br>
        for var in self.variables:<br>
            index = holonomic_index_map[var][0]<br>
            d[index] += self.rhs<br>
<br>
# ============================================================================<br>
# Вспомогательные функции для удобства<br>
# ============================================================================<br>
<br>
def spring_element(u1: Variable, u2: Variable, stiffness: float) -&gt; BilinearContribution:<br>
    &quot;&quot;&quot;<br>
    Создать вклад пружины/стержня между двумя скалярными переменными<br>
    <br>
    Уравнение: F = k*(u2-u1)<br>
    Матрица:  [[k, -k],<br>
               [-k, k]]<br>
    &quot;&quot;&quot;<br>
    K = stiffness * np.array([<br>
        [ 1, -1],<br>
        [-1,  1]<br>
    ])<br>
    return BilinearContribution([u1, u2], K)<br>
<br>
<br>
def conductance_element(V1: Variable, V2: Variable, conductance: float) -&gt; BilinearContribution:<br>
    &quot;&quot;&quot;<br>
    Создать вклад проводимости (резистор) между двумя узлами<br>
    <br>
    То же самое что spring_element, но с другим физическим смыслом<br>
    &quot;&quot;&quot;<br>
    return spring_element(V1, V2, conductance)<br>
<!-- END SCAT CODE -->
</body>
</html>
