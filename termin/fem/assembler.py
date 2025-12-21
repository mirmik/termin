#!/usr/bin/env python3
"""
Универсальная система сборки матриц для МКЭ и других задач.

Основная идея: 
- Система уравнений собирается из вкладов (contributions)
- Каждый вклад знает, какие переменные он затрагивает
- Итоговая система: A*x = b
"""

import numpy as np
from typing import List, Dict, Tuple, Optional
import numpy
from termin.geombase import Pose3

import termin.linalg.subspaces


class Variable:
    """
    Переменная (неизвестная величина) в системе уравнений.
    
    Может представлять:
    - Перемещение узла в механике
    - Напряжение в узле электрической цепи
    - Температуру в узле тепловой задачи
    - И т.д.
    """

    def __init__(self, name: str, size: int = 1, tag = None):
        """
        Args:
            name: Имя переменной (для отладки)
            size: Размерность
        """
        
        self.size = size
        self.global_indices = []  # будет заполнено при сборке
        self.tag = tag  # произвольный тег для пользователя
        self._assembler = None  # ссылка на assembler, в котором зарегистрирована переменная
        self.value = np.zeros(size)         # текущее значение переменной (обновляется после решения)

        self.name_list = []
        if size == 1:
            self.name_list.append(name)
        else:
            lst = ["x", "y", "z", "a", "b", "c", "w"]
            for i in range(size):
                vname = name + "_" + lst[i]
                self.name_list.append(vname)

    def __str__(self):
        return f"{self.name_list}"

    def __repr__(self):
        return f"{self.name_list} (size={self.size})"

    def names(self) -> List[str]:
        """Вернуть список имен компонент переменной"""
        return self.name_list

    def set_value(self, value: np.ndarray):
        """
        Установить значение переменной
        
        Args:
            value: Значение для установки
        """

        if isinstance(value, list):
            self.value = np.array(value)
        elif isinstance(value, (int, float)):
            self.value = np.array([value])
        else:
            if value.shape != (self.size,):
                raise ValueError(f"Размер входного значения {value.shape} не соответствует размеру переменной {self.size}")
            self.value = value 
            
    



class Contribution:
    """
    Базовый класс для вклада в систему уравнений.
    
    Вклад - это что-то, что добавляет элементы в матрицу A и/или вектор b.
    Примеры:
    - Уравнение стержня в механике
    - Резистор в электрической цепи
    - Граничное условие
    - Уравнение связи между переменными
    """
    
    def __init__(self, variables: List[Variable], domain = "mechanic", assembler=None):
        self.variables = variables
        self._assembler = assembler  # ссылка на assembler, в котором зарегистрирован вклад
        self.assembler = assembler
        self.domain = domain
        if assembler is not None:
            assembler.add_contribution(self)
        self._rank = self._evaluate_rank()

        if self.domain is None:
            raise ValueError(f"Domain must be specified for {type(self)}")

    def _evaluate_rank(self) -> int:
        """Возвращает размерность вклада (число уравнений, которые он добавляет)"""
        total_size = sum(var.size for var in self.variables)
        return total_size

    def get_variables(self) -> List[Variable]:
        """Возвращает список переменных, которые затрагивает этот вклад"""
        return self.variables

    def contribute_to_matrices(self, matrices, index_map: Dict[Variable, List[int]]):
        """
        Добавить вклад в матрицы
        """
        pass  
    
    def contribute_to_mass(self, A: np.ndarray, index_map: Dict[Variable, List[int]]):
        """
        Добавить вклад в матрицу A
        Уравнение: A*x_d2 + B*x_d + C*x = b
        
        Args:
            A: Глобальная матрица (изменяется in-place)
            index_map: Отображение Variable -> список глобальных индексов
        """
        return np.zeros((self._rank, self._rank))
    
    def contribute_to_stiffness(self, K: np.ndarray, index_map: Dict[Variable, List[int]]):
        """
        Добавить вклад в матрицу K
        
        Args:
            A: Глобальная матрица (изменяется in-place)
            index_map: Отображение Variable -> список глобальных индексов
        """
        return np.zeros((self._rank, self._rank))

    def contribute_to_damping(self, C: np.ndarray, index_map: Dict[Variable, List[int]]):
        """
        Добавить вклад в матрицу C
        
        Args:
            A: Глобальная матрица (изменяется in-place)
            index_map: Отображение Variable -> список глобальных индексов
        """
        return np.zeros((self._rank, self._rank))
    
    def contribute_to_load(self, b: np.ndarray, index_map: Dict[Variable, List[int]]):
        """
        Добавить вклад в вектор правой части b
        
        Args:
            b: Глобальный вектор (изменяется in-place)
            index_map: Отображение Variable -> список глобальных индексов
        """
        return np.zeros(self._rank)

    def finish_timestep(self, dt: float):
        """
        Завершить шаг по времени (обновить внутренние состояния, если нужно)
        
        Args:
            dt: Шаг по времени
        """
        pass


class Constraint:
    """
    Базовый класс для голономных связей (constraints).
    
    Связь ограничивает движение системы: C·x = d
    
    В отличие от Contribution (который добавляет вклад в A и b),
    Constraint реализуется через множители Лагранжа и добавляет
    строки в расширенную систему.
    
    Примеры:
    - Фиксация точки в пространстве
    - Шарнирное соединение тел
    - Равенство переменных
    - Кинематические ограничения
    """
    
    def __init__(self, variables: List[Variable], 
                 holonomic_lambdas: List[Variable], 
                 nonholonomic_lambdas: List[Variable], 
                 assembler=None):
        self.variables = variables
        self.holonomic_lambdas = holonomic_lambdas  # переменные для множителей Лагранжа
        self.nonholonomic_lambdas = nonholonomic_lambdas  # переменные для множителей Лагранжа
        self._assembler = assembler  # ссылка на assembler, в котором зарегистрирована связь
        if assembler is not None:
            assembler.add_constraint(self)
        self._rank = self._evaluate_rank()

        self._rank_holonomic = sum(var.size for var in self.holonomic_lambdas)
        self._rank_nonholonomic = sum(var.size for var in self.nonholonomic_lambdas)

    def _evaluate_rank(self) -> int:
        return sum(var.size for var in self.variables)

    def get_variables(self) -> List[Variable]:
        """Возвращает список переменных, участвующих в связи"""
        return self.variables

    def get_holonomic_lambdas(self) -> List[Variable]:
        """Возвращает список переменных-множителей Лагранжа"""
        return self.holonomic_lambdas

    def get_nonholonomic_lambdas(self) -> List[Variable]:
        """Возвращает список переменных-множителей Лагранжа для неоголономных связей"""
        return self.nonholonomic_lambdas
    
    def get_n_holonomic(self) -> int:
        """Возвращает количество голономных уравнений связи"""
        return self._rank_holonomic

    def get_n_nonholonomic(self) -> int:
        """Возвращает количество неоголономных уравнений связи"""
        return self._rank_nonholonomic

    def contribute_to_holonomic(self, H: np.ndarray, 
                       index_map: Dict[Variable, List[int]]):
        """
        Добавить вклад в матрицу связей
        
        Args:
            H: Матрица связей (n_constraints_total × n_dofs)
            index_map: Отображение Variable -> список глобальных индексов
        """
        return np.zeros((self.get_n_holonomic(), H.shape[1]))
    
    def contribute_to_nonholonomic(self, N: np.ndarray,                                    
                                     vars_index_map: Dict[Variable, List[int]],
                                     lambdas_index_map: Dict[Variable, List[int]]):
        """
        Добавить вклад в матрицу связей для неограниченных связей

        Args:
            N: Матрица связей (n_constraints_total × n_dofs)
            index_map: Отображение Variable -> список глобальных индексов
        """
        return np.zeros((self.get_n_nonholonomic(), N.shape[1]))

    def contribute_to_holonomic_load(self, d: np.ndarray,  holonomic_index_map: Dict[Variable, List[int]]):
        """
        Добавить вклад в правую часть связей d
        
        Args:
            d: Вектор правой части связей
        """
        return np.zeros(self.get_n_holonomic())

    def contribute_to_nonholonomic_load(self, d: np.ndarray,  lambdas_index_map: Dict[Variable, List[int]]):
        """
        Добавить вклад в правую часть связей d для неограниченных связей

        Args:
            d: Вектор правой части связей
        """
        return np.zeros(self.get_n_nonholonomic())
    



class MatrixAssembler:
    """
    Сборщик матриц из вкладов.
    
    Основной класс системы - собирает глобальную матрицу A и вектор b
    из множества локальных вкладов.
    """
    
    def __init__(self):
        self._dirty_index_map = True
        self.variables: List[Variable] = []
        self.contributions: List[Contribution] = []
        self.constraints: List[Constraint] = []  # Связи через множители Лагранжа

        self._full_index_map : Optional[Dict[Variable, List[int]]] = None
        self._variables_index_map: Optional[Dict[Variable, List[int]]] = None
        self._holonomic_index_map: Optional[Dict[Variable, List[int]]] = None
        self._nonholonomic_index_map: Optional[Dict[Variable, List[int]]] = None

        self._holonomic_constraint_vars: List[Variable] = []  # Переменные для множителей Лагранжа
        self._nonholonomic_constraint_vars: List[Variable] = []  # Переменные для множителей Лагранжа для неоголономных связей

        self._q = None  # Вектор состояний
        self._q_dot = None  # Вектор скоростей состояний
        self._q_ext_ddot = None  # Вектор ускорений состояний (расширенный)
        self._q_ddot = None  # Вектор ускорений состояний
        self._lambdas_holonomic = None  # Множители Лагранжа для голономных связей
        self._lambdas_nonholonomic = None  # Множители Лагранжа для неограниченных связей

        self._variables_by_tag: Dict = {}  # Словарь переменных по тегам для быстрого доступа
        
    def add_variable(self, name: str, size: int = 1) -> Variable:
        """
        Добавить переменную в систему
        
        Args:
            name: Имя переменной
            size: Размерность (1 для скаляра, 2/3 для вектора)
            
        Returns:
            Созданная переменная
        """
        var = Variable(name, size)
        self._register_variable(var)
        return var
    
    def add_holonomic_constraint_variable(self, name: str, size: int = 1) -> Variable:
        """
        Добавить переменную-множитель Лагранжа в систему
        
        Args:
            name: Имя переменной
            size: Размерность (1 для скаляра, 2/3 для вектора)
            
        Returns:
            Созданная переменная
        """
        var = Variable(name, size)
        self._register_holonomic_constraint_variable(var)
        return var
    
    def add_nonholonomic_constraint_variable(self, name: str, size: int = 1) -> Variable:
        """
        Добавить переменную-множитель Лагранжа для неоголономных связей в систему
        
        Args:
            name: Имя переменной
            size: Размерность (1 для скаляра, 2/3 для вектора)
            
        Returns:
            Созданная переменная
        """
        var = Variable(name, size)
        self._register_nonholonomic_constraint_variable(var)
        return var
    
    def _register_variable(self, var: Variable):
        """
        Зарегистрировать переменную в assembler, если она еще не зарегистрирована
        
        Args:
            var: Переменная для регистрации
        """
        if var._assembler is None:
            var._assembler = self
            self.variables.append(var)
            self._dirty_index_map = True
            if var.tag not in self._variables_by_tag:
                self._variables_by_tag[var.tag] = []
            self._variables_by_tag[var.tag].append(var)
        elif var._assembler is not self:
            raise ValueError(f"Переменная {var.name} уже зарегистрирована в другом assembler")

    def total_variables_by_tag(self, tag) -> int:
        """Вернуть количество переменных с заданным тегом"""
        if tag in self._variables_by_tag:
            return sum(var.size for var in self._variables_by_tag[tag])
        return 0
        
    def _register_holonomic_constraint_variable(self, var: Variable):
        """
        Зарегистрировать переменную-множитель Лагранжа в assembler, если она еще не зарегистрирована
        
        Args:
            var: Переменная для регистрации
        """
        if var._assembler is None:
            var._assembler = self
            self._holonomic_constraint_vars.append(var)
            self._dirty_index_map = True
        elif var._assembler is not self:
            raise ValueError(f"Переменная {var.name} уже зарегистрирована в другом assembler")
        
    def _register_nonholonomic_constraint_variable(self, var: Variable):
        """
        Зарегистрировать переменную-множитель Лагранжа в assembler, если она еще не зарегистрирована
        
        Args:
            var: Переменная для регистрации
        """
        if var._assembler is None:
            var._assembler = self
            self._nonholonomic_constraint_vars.append(var)
            self._dirty_index_map = True
        elif var._assembler is not self:
            raise ValueError(f"Переменная {var.name} уже зарегистрирована в другом assembler")
    
    def add_contribution(self, contribution: Contribution):
        """
        Добавить вклад в систему
        
        Args:
            contribution: Вклад (уравнение, граничное условие, и т.д.)
        """
        # Проверяем и регистрируем все переменные, используемые вкладом
        for var in contribution.get_variables():
            self._register_variable(var)
        
        contribution._assembler = self  # регистрируем assembler
        self.contributions.append(contribution)
    
    def add_constraint(self, constraint: Constraint):
        """
        Добавить связь в систему
        
        Args:
            constraint: Связь (кинематическое ограничение, и т.д.)
        """
        # Проверяем и регистрируем все переменные, используемые связью
        for lvar in constraint.get_holonomic_lambdas():
            self._register_holonomic_constraint_variable(lvar)

        for nvar in constraint.get_nonholonomic_lambdas():
            self._register_nonholonomic_constraint_variable(nvar)

        constraint._assembler = self  # регистрируем assembler
        self.constraints.append(constraint)

    def _build_index_map(self, variables) -> Dict[Variable, List[int]]:
        """
        Построить отображение: Variable -> глобальные индексы DOF
        
        Назначает каждой компоненте каждой переменной уникальный
        глобальный индекс в системе.
        """
        index_map = {}
        current_index = 0
        
        for var in variables:
            indices = list(range(current_index, current_index + var.size))
            index_map[var] = indices
            var.global_indices = indices
            current_index += var.size
        
        return index_map

    def _build_full_index_map(self) -> Dict[Variable, List[int]]:
        """
        Построить полное отображение: Variable -> глобальные индексы DOF
        включая все переменные и переменные связей
        """
        full_variables = self.variables + self._holonomic_constraint_vars + self._nonholonomic_constraint_vars
        full_index_map = {}
        current_index = 0
        
        for var in full_variables:
            indices = list(range(current_index, current_index + var.size))
            full_index_map[var] = indices
            current_index += var.size
        
        return full_index_map

    def _build_index_maps(self) -> Dict[Variable, List[int]]:
        """
        Построить отображение: Variable -> глобальные индексы DOF
        
        Назначает каждой компоненте каждой переменной уникальный
        глобальный индекс в системе.
        """
        self._index_map = self._build_index_map(self.variables)
        self._holonomic_index_map = self._build_index_map(self._holonomic_constraint_vars)
        self._nonholonomic_index_map = self._build_index_map(self._nonholonomic_constraint_vars)

        self._full_index_map = self._build_full_index_map()

        self._dirty_index_map = False
        #self._rebuild_state_vectors()
    
    def index_map(self) -> Dict[Variable, List[int]]:
        """
        Получить текущее отображение Variable -> глобальные индексы DOF
        """
        if self._dirty_index_map:
            self._build_index_maps()
        return self._index_map
    
    def total_dofs(self) -> int:
        """Общее количество степеней свободы в системе"""
        return sum(var.size for var in self.variables)
    
    def assemble(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Собрать глобальную систему A*x = b
        
        Returns:
            (A, b): Матрица и вектор правой части
        """
        # Построить карту индексов
        index_map = self.index_map()
        
        # Создать глобальные матрицу и вектор
        n_dofs = self.total_dofs()
        A = np.zeros((n_dofs, n_dofs))
        b = np.zeros(n_dofs)
        
        # Собрать вклады
        for contribution in self.contributions:
            contribution.contribute_to_stiffness(A, index_map)
            contribution.contribute_to_load(b, index_map)
        
        return A, b

    def assemble_dynamic_system(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Собрать глобальную систему A*x'' + C*x' + K*x = b
        
        Returns:
            (A, C, K, b): Матрицы и вектор правой части
        """
        # Построить карту индексов
        index_map = self.index_map()

        # Создать глобальные матрицы и вектор
        n_dofs = self.total_dofs()
        
        A = np.zeros((n_dofs, n_dofs))
        C = np.zeros((n_dofs, n_dofs))
        K = np.zeros((n_dofs, n_dofs))
        b = np.zeros(n_dofs)

        matrices = {
            "mass": A,
            "damping": C,
            "stiffness": K,
            "load": b
        }

        for contribution in self.contributions:
            contribution.contribute(matrices, index_map)

        return matrices


    def assemble_stiffness_problem(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Собрать глобальную систему K*x = b

        Returns:
            (K, b): Матрица и вектор правой части
        """
        # Построить карту индексов
        index_map = self.index_map()
        
        # Создать глобальные матрицу и вектор
        n_dofs = self.total_dofs()
        K = np.zeros((n_dofs, n_dofs))
        b = np.zeros(n_dofs)
        
        # Собрать вклады
        for contribution in self.contributions:
            contribution.contribute_to_stiffness(K, index_map)
            contribution.contribute_to_load(b, index_map)
        
        return K, b
    
    def assemble_static_problem(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Собрать глобальную систему K*x = b

        Returns:
            (K, b): Матрица и вектор правой части
        """
        # Построить карту индексов
        index_map = self.index_map()
        
        # Создать глобальные матрицу и вектор
        n_dofs = self.total_dofs()
        K = np.zeros((n_dofs, n_dofs))
        b = np.zeros(n_dofs)
        
        # Собрать вклады
        for contribution in self.contributions:
            contribution.contribute_to_mass(K, index_map)
            contribution.contribute_to_load(b, index_map)
        
        return K, b
    
    def assemble_dynamic_problem(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Собрать глобальную систему Ad·x'' + C·x' + K·x = b
        
        Returns:
            (Ad, C, K, b): Матрицы и вектор правой части
        """
        # Построить карту индексов
        index_map = self.index_map()

        # Создать глобальные матрицы и вектор
        n_dofs = self.total_dofs()
        A = np.zeros((n_dofs, n_dofs))
        C = np.zeros((n_dofs, n_dofs))
        K = np.zeros((n_dofs, n_dofs))
        b = np.zeros(n_dofs)
        
        # Собрать вклады
        for contribution in self.contributions:
            contribution.contribute_to_mass(A, index_map)
            contribution.contribute_to_damping(C, index_map)
            contribution.contribute_to_stiffness(K, index_map)
            contribution.contribute_to_load(b, index_map)

        return A, C, K, b

    def assemble_constraints(self) -> Tuple[np.ndarray, np.ndarray]:    
        index_map = self.index_map()

        # Подсчитать общее количество связей
        n_hconstraints = sum(constraint.get_n_holonomic() for constraint in self.constraints)
        n_nhconstraints = sum(constraint.get_n_nonholonomic() for constraint in self.constraints)
        n_dofs = self.total_dofs()

        # Создать матрицу связей (n_constraints × n_dofs)
        H = np.zeros((n_hconstraints, n_dofs))
        N = np.zeros((n_nhconstraints, n_dofs))
        dH = np.zeros(n_hconstraints)
        dN = np.zeros(n_nhconstraints)

        # Заполнить матрицу связей
        for constraint in self.constraints:
            constraint.contribute_to_holonomic(H, index_map, self._holonomic_index_map)
            constraint.contribute_to_nonholonomic(N, index_map, self._nonholonomic_index_map)
            constraint.contribute_to_holonomic_load(dH, self._holonomic_index_map)

        return H, N, dH, dN

    def make_extended_system(
            self, A, C, K, b, H, N, dH, dN, q, q_d) -> Tuple[np.ndarray, np.ndarray]:
        """
        Собрать расширенную систему с множителями Лагранжа
        """
        n_dofs = A.shape[0] + H.shape[0] + N.shape[0]

        A_ext = np.zeros((n_dofs, n_dofs))
        b_ext = np.zeros(n_dofs)

        #[ A H.T N.T ]
        #[ H 0   0   ]
        #[ N 0   0   ]

        r0 = A.shape[0]
        r1 = A.shape[0] + H.shape[0]
        r2 = A.shape[0] + H.shape[0] + N.shape[0]

        c0 = A.shape[1]
        c1 = A.shape[1] + H.shape[0]
        c2 = A.shape[1] + H.shape[0] + N.shape[0]

        A_ext[0:r0, 0:c0] = A
        A_ext[0:r0, c0:c1] = H.T
        A_ext[0:r0, c1:c2] = N.T

        A_ext[r0:r1, 0:c0] = H
        A_ext[r1:r2, 0:c0] = N

        b_ext[0:r0] = b - C @ q_d - K @ q
        b_ext[r0:r1] = dH
        b_ext[r1:r2] = dN

        return A_ext, b_ext

    def extended_dynamic_system_size(self) -> int:
        """
        Получить размер расширенной системы с учетом связей
        Returns:
            Размер расширенной системы
        """
        n_dofs = self.total_dofs()
        n_hconstraints = sum(constraint.get_n_holonomic() for constraint in self.constraints)
        n_nhconstraints = sum(constraint.get_n_nonholonomic() for constraint in self.constraints)
        return n_dofs + n_hconstraints + n_nhconstraints

    def simulation_step_dynamic_with_constraints(self,
            dt: float,
            check_conditioning: bool = True,
            use_least_squares: bool = False) -> np.ndarray:
        """
        Выполнить шаг динамического решения с учетом связей
        Args:
            dt: Шаг времени
            check_conditioning: Проверить обусловленность матрицы и выдать предупреждение
            use_least_squares: Использовать lstsq вместо solve (робастнее, но медленнее)
        """
        self._q_ext_ddot, A, C, K, b, H, N, dH, dN = (
            self.solve_Ad2x_Cdx_Kx_b_with_constraints(
                check_conditioning=check_conditioning,
                use_least_squares=use_least_squares
        ))

        self._q_ddot = self._q_ext_ddot[:self.total_dofs()]
        self._lambdas_holonomic = self._q_ext_ddot[self.total_dofs():
                                                  self.total_dofs() + sum(constraint.get_n_holonomic() for constraint in self.constraints)]
        self._lambdas_nonholonomic = self._q_ext_ddot[self.total_dofs() + sum(constraint.get_n_holonomic() for constraint in self.constraints):]

        # Обновить переменные
        self._q_dot += self._q_ddot * dt
        H_add_N_T = H.T + N.T

        q_dot_violation = termin.linalg.subspaces.rowspace(H_add_N_T) @ self._q_dot
        self._q_dot -= q_dot_violation

        self._q += self._q_dot * dt + 0.5 * self._q_ddot * dt * dt
        q_violation = termin.linalg.subspaces.rowspace(H) @ self._q
        self._q -= q_violation

        self._update_variables_from_state_vectors()


    # def _update_variables_from_state_vectors(self):
    #     """Обновить значения переменных из внутренних векторов состояния q и q_dot"""
    #     index_map = self.index_map()
    #     for var in self.variables:
    #         indices = index_map[var]
    #         var.value = self._q[indices]
    #         var.value_dot = self._q_dot[indices]
    #         var.nonlinear_integral()


    def _solve_system(self, A, b, 
                      check_conditioning: bool = True, 
              use_least_squares: bool = False) -> np.ndarray:
        """
        Решить систему A*x = b
        Args:
            A: Матрица системы
            b: Вектор правой части
            check_conditioning: Проверить обусловленность матрицы и выдать предупреждение
            use_least_squares: Использовать lstsq вместо solve (робастнее, но медленнее)
        Returns:
            x: Вектор решения
        """
        # Проверка обусловленности
        if check_conditioning:
            cond_number = np.linalg.cond(A)
            if cond_number > 1e10:
                import warnings
                warnings.warn(
                    f"Матрица плохо обусловлена: cond(A) = {cond_number:.2e}. "
                    f"Это может быть из-за penalty method в граничных условиях. "
                    f"Рассмотрите использование use_least_squares=True",
                    RuntimeWarning
                )
            elif cond_number > 1e6:
                import warnings
                warnings.warn(
                    f"Матрица имеет высокое число обусловленности: cond(A) = {cond_number:.2e}",
                    RuntimeWarning
                )

        # Решение системы
        if use_least_squares:
            # Метод наименьших квадратов - более робастный
            x, residuals, rank, s = np.linalg.lstsq(A, b, rcond=None)
            if check_conditioning and rank < len(b):
                import warnings
                warnings.warn(
                    f"Матрица вырожденная или близка к вырожденной: "
                    f"rank(A) = {rank}, expected {len(b)}",
                    RuntimeWarning
                )
            elif check_conditioning and rank < len(b):
                import warnings
                warnings.warn(
                    f"Матрица вырожденная или близка к вырожденной: "
                    f"rank(A) = {rank}, expected {len(b)}",
                    RuntimeWarning
                )

        else:
            # Прямое решение - быстрее, но менее робастное
            try:
                x = np.linalg.solve(A, b)
            except np.linalg.LinAlgError as e:
                raise RuntimeError(
                    f"Не удалось решить систему: {e}. "
                    f"Возможно, матрица вырожденная (не хватает граничных условий?) "
                    f"или плохо обусловлена. Попробуйте use_least_squares=True"
                ) from e
        
        return x

    # def state_vectors(self) -> Tuple[np.ndarray, np.ndarray]:
    #     """
    #     Собрать векторы состояния x и x_dot из текущих значений переменных
        
    #     Returns:
    #         x: Вектор состояний
    #         x_dot: Вектор скоростей состояний
    #     """
    #     if self._index_map is None:
    #         raise RuntimeError("Система не собрана. Вызовите assemble() перед получением векторов состояния.")
        
    #     n_dofs = self.total_dofs()
    #     x = np.zeros(n_dofs)
    #     x_dot = np.zeros(n_dofs)
        
    #     for var in self.variables:
    #         indices = self._index_map[var]
    #         value, value_dot = var.state_for_assembler()
    #         x[indices] = value
    #         x_dot[indices] = value_dot
        
    #     return x, x_dot

    def solve_Adxx_Cdx_Kx_b(self, x_dot: np.ndarray, x: np.ndarray,
                            check_conditioning: bool = True,
                            use_least_squares: bool = False) -> np.ndarray:
        """
        Решить систему Ad·x'' + C·x' + K·x = b

        Args:
            x_dot: Вектор скоростей состояний
            x: Вектор состояний
            check_conditioning: Проверить обусловленность матрицы
            use_least_squares: Использовать lstsq вместо solve
            b: Вектор правой части
            """

        Ad, C, K, b = self.assemble_Adxx_Cdx_Kx_b()
        v, v_dot = self.state_vectors()

        # Собрать левую часть
        A_eff = Ad
        A_eff += C @ x_dot
        A_eff += K @ x

        # Правая часть
        b_eff = b

        return self.solve(check_conditioning=check_conditioning,
                          use_least_squares=use_least_squares,
                          use_constraints=False)

    
    def set_solution_to_variables(self, x: np.ndarray):
        """
        Сохранить решение в объекты Variable
        
        После вызова этого метода каждая переменная будет иметь атрибут value
        с решением (скаляр или numpy array).
        
        Args:
            x: Вектор решения
        """
        if self._index_map is None:
            raise RuntimeError("Система не собрана. Вызовите assemble() или solve()")
        
        for var in self.variables:
            indices = self._index_map[var]
            if len(indices) > 1:
                var.value = x[indices]
            else:
                var.value = x[indices[0]]
    
    def solve_stiffness_problem(self, check_conditioning: bool = True, 
                      use_least_squares: bool = False,
                      use_constraints: bool = True) -> np.ndarray:
        """
        Решить систему и сохранить результат в переменные
        
        Удобный метод, который объединяет solve() и set_solution_to_variables().
        
        Args:
            check_conditioning: Проверить обусловленность матрицы
            use_least_squares: Использовать lstsq вместо solve
            use_constraints: Использовать множители Лагранжа для связей
        
        Returns:
            x: Вектор решения (также сохранен в переменных)
        """
        # x = self.solve(check_conditioning=check_conditioning, 
        #                use_least_squares=use_least_squares,
        #                use_constraints=use_constraints)

        K, b = self.assemble_stiffness_problem()

        x = self._solve_system(A=K, b=b, check_conditioning=check_conditioning,
                                use_least_squares=use_least_squares)

        self.set_solution_to_variables(x)
        return x
    
    def get_lagrange_multipliers(self) -> Optional[np.ndarray]:
        """
        Получить множители Лагранжа после решения системы с связями
        
        Множители Лагранжа представляют собой силы реакции связей.
        
        Returns:
            Массив множителей Лагранжа или None, если система решалась без связей
        """
        return getattr(self, '_lagrange_multipliers', None)
    
    def diagnose_matrix(self) -> Dict[str, any]:
        """
        Диагностика собранной матрицы системы
        
        Returns:
            Словарь с информацией о матрице:
            - condition_number: число обусловленности
            - is_symmetric: симметричность
            - is_positive_definite: положительная определённость
            - rank: ранг матрицы
            - min_eigenvalue: минимальное собственное значение
            - max_eigenvalue: максимальное собственное значение
        """
        A, b = self.assemble()
        
        info = {}
        
        # Число обусловленности
        info['condition_number'] = np.linalg.cond(A)
        
        # Симметричность
        info['is_symmetric'] = np.allclose(A, A.T)
        
        # Ранг
        info['rank'] = np.linalg.matrix_rank(A)
        info['expected_rank'] = len(A)
        info['is_full_rank'] = info['rank'] == info['expected_rank']
        
        # Собственные значения (только для небольших матриц)
        if len(A) <= 100:
            eigenvalues = np.linalg.eigvalsh(A) if info['is_symmetric'] else np.linalg.eigvals(A)
            eigenvalues = np.real(eigenvalues)
            info['min_eigenvalue'] = np.min(eigenvalues)
            info['max_eigenvalue'] = np.max(eigenvalues)
            info['is_positive_definite'] = np.all(eigenvalues > 0)
        else:
            info['eigenvalues'] = 'Skipped (matrix too large)'
            info['is_positive_definite'] = None
        
        # Оценка качества
        cond = info['condition_number']
        if cond < 100:
            info['quality'] = 'excellent'
        elif cond < 1e4:
            info['quality'] = 'good'
        elif cond < 1e8:
            info['quality'] = 'acceptable'
        elif cond < 1e12:
            info['quality'] = 'poor'
        else:
            info['quality'] = 'very_poor'
        
        return info
    
    @staticmethod
    def system_to_human_readable(
        A_ext: np.ndarray, 
        b_ext: np.ndarray, 
        variables: List[Variable]) -> str:
        """
        Преобразовать расширенную систему в человекочитаемый формат
        
        Args:
            A_ext: Расширенная матрица системы
            b_ext: Расширенный вектор правой части
            variables: Список переменных системы
            
        Returns:
            Строковое представление системы
        """
        lines = []
        n_vars = len(variables)
        
        for i in range(A_ext.shape[0]):
            row_terms = []

            count_of_nonzero = 0
            for j in range(A_ext.shape[1]):
                coeff = A_ext[i, j]
                if abs(coeff) > 1e-12:
                    var_name = variables[j]
                    count_of_nonzero += 1

                    if (np.isclose(coeff, 1.0)):
                        row_terms.append(f"{var_name}")
                    elif (np.isclose(coeff, -1.0)):
                        row_terms.append(f"-{var_name}")
                    else:
                        row_terms.append(f"{coeff}*{var_name}")
            row_str = " "
            row_str += " + ".join(row_terms)
            row_str += f" = {b_ext[i]}"

            if count_of_nonzero == 0:
                row_str = f" 0 = {b_ext[i]}"

            lines.append(row_str)
        
        return "\n".join(lines)

    def result_to_human_readable(self, x_ext: np.ndarray, variables: List[Variable]) -> str:
        """
        Преобразовать вектор решения в человекочитаемый формат

        Args:
            x_ext: Вектор решения
            variables: Список переменных системы

        Returns:
            Строковое представление решения
        """
        lines = []

        for i, var in enumerate(variables):
            lines.append(f" {var} = {x_ext[i]}")
        return "\n".join(lines)

    @staticmethod
    def matrix_diagnosis(A, tol=1e-10):
        """
        Анализирует матрицу A_ext:
        - вычисляет ранг
        - определяет нулевое подпространство
        - сообщает, какая часть системы линейно зависима
        """
        import numpy as np

        U, S, Vt = np.linalg.svd(A)
        rank = np.sum(S > tol)
        nullity = A.shape[0] - rank

        return {
            "size": A.shape,
            "rank": rank,
            "nullity": nullity,
            "singular": nullity > 0,
            "small_singular_values": S[S < tol],
            "condition_number": S.max() / S.min() if S.min() > 0 else np.inf
        }

    def print_diagnose(self):
        """
        Print human-readable matrix diagnostics
        """
        info = self.diagnose_matrix()
        
        print("=" * 70)
        print("MATRIX SYSTEM DIAGNOSTICS")
        print("=" * 70)
        
        # Dimensions
        print(f"\nSystem dimensions:")
        print(f"  Number of variables: {len(self.variables)}")
        print(f"  Degrees of freedom (DOF): {self.total_dofs()}")
        
        # Matrix rank
        print(f"\nMatrix rank:")
        print(f"  Current rank: {info['rank']}")
        print(f"  Expected rank: {info['expected_rank']}")
        if info['is_full_rank']:
            print(f"  [OK] Matrix has full rank")
        else:
            print(f"  [PROBLEM] Matrix is singular (rank deficient)")
            print(f"    Possibly missing boundary conditions")
        
        # Symmetry
        print(f"\nSymmetry:")
        if info['is_symmetric']:
            print(f"  [OK] Matrix is symmetric")
        else:
            print(f"  [PROBLEM] Matrix is not symmetric")
            print(f"    This may indicate an error in contributions")
        
        # Conditioning
        print(f"\nConditioning:")
        print(f"  Condition number: {info['condition_number']:.2e}")
        print(f"  Quality assessment: {info['quality']}")
        
        quality_desc = {
            'excellent': '[OK] Excellent - matrix is very well conditioned',
            'good': '[OK] Good - matrix is well conditioned',
            'acceptable': '[WARNING] Acceptable - may have small numerical errors',
            'poor': '[PROBLEM] Poor - high risk of numerical errors',
            'very_poor': '[PROBLEM] Very poor - solution may be inaccurate'
        }
        print(f"  {quality_desc.get(info['quality'], '')}")
        
        if info['quality'] in ['poor', 'very_poor']:
            print(f"\n  Recommendations:")
            print(f"    - Reduce penalty in boundary conditions (try 1e8)")
            print(f"    - Use use_least_squares=True when solving")
            print(f"    - Check the scales of quantities in the problem")
        
        # Eigenvalues
        if info.get('min_eigenvalue') is not None:
            print(f"\nEigenvalues:")
            print(f"  Minimum: {info['min_eigenvalue']:.2e}")
            print(f"  Maximum: {info['max_eigenvalue']:.2e}")
            
            if info.get('is_positive_definite'):
                print(f"  [OK] Matrix is positive definite")
            else:
                print(f"  [PROBLEM] Matrix is not positive definite")
                if info['min_eigenvalue'] <= 0:
                    print(f"    Has non-positive eigenvalues")
        
        # Final recommendation
        print(f"\n" + "=" * 70)
        if info['is_full_rank'] and info['is_symmetric'] and info['quality'] in ['excellent', 'good', 'acceptable']:
            print("SUMMARY: [OK] System is ready to solve")
        else:
            print("SUMMARY: [WARNING] Problems detected, attention required")
        print("=" * 70)




# ============================================================================
# Примеры конкретных вкладов
# ============================================================================

class BilinearContribution(Contribution):
    """
    Билинейный вклад: связь двух переменных через локальную матрицу
    
    Пример: стержень, пружина, резистор
    Вклад в A: A[i,j] += K_local[i,j] для пар индексов переменных
    """
    
    def __init__(self, variables: List[Variable], K_local: np.ndarray):
        """
        Args:
            variables: Список переменных (например, [u1, u2] для стержня)
            K_local: Локальная матрица вклада
        """
        self.variables = variables
        self.K_local = np.array(K_local)
        
        # Проверка размерности
        expected_size = sum(v.size for v in variables)
        if self.K_local.shape != (expected_size, expected_size):
            raise ValueError(f"Размер K_local {self.K_local.shape} не соответствует "
                           f"суммарному размеру переменных {expected_size}")
        
    def contribute_to_stiffness(self, A: np.ndarray, index_map: Dict[Variable, List[int]]):
        # Собрать глобальные индексы всех переменных
        global_indices = []
        for var in self.variables:
            global_indices.extend(index_map[var])
        
        # Добавить локальную матрицу в глобальную
        for i, gi in enumerate(global_indices):
            for j, gj in enumerate(global_indices):
                A[gi, gj] += self.K_local[i, j]
    
    def contribute_to_load(self, b: np.ndarray, index_map: Dict[Variable, List[int]]):
        # Этот тип вклада не влияет на правую часть
        pass


class LoadContribution(Contribution):
    """
    Вклад нагрузки/источника в правую часть
    
    Пример: приложенная сила, источник тока, тепловой источник
    Вклад в b: b[i] += F[i]
    """
    
    def __init__(self, variable: Variable, load: np.ndarray):
        """
        Args:
            variable: Переменная, к которой приложена нагрузка
            load: Вектор нагрузки (размера variable.size)
        """
        self.variable = variable
        self.load = np.atleast_1d(load)
        
        if len(self.load) != variable.size:
            raise ValueError(f"Размер нагрузки {len(self.load)} не соответствует "
                           f"размеру переменной {variable.size}")
    
    def get_variables(self) -> List[Variable]:
        return [self.variable]
    
    def contribute_to_stiffness(self, A: np.ndarray, index_map: Dict[Variable, List[int]]):
        # Не влияет на матрицу
        pass
    
    def contribute_to_load(self, b: np.ndarray, index_map: Dict[Variable, List[int]]):
        indices = index_map[self.variable]
        for i, idx in enumerate(indices):
            b[idx] += self.load[i]


class ConstraintContribution(Contribution):
    """
    Граничное условие: фиксированное значение переменной
    
    Пример: u1 = 0 (закрепленный узел), V1 = 5 (источник напряжения)
    
    Реализовано через penalty method:
    A[i,i] += penalty
    b[i] += penalty * prescribed_value
    """
    
    def __init__(self, variable: Variable, value: float, 
                 component: int = 0, penalty: float = 1e10):
        """
        Args:
            variable: Переменная для ограничения
            value: Предписанное значение
            component: Компонента переменной (0 для скаляра)
            penalty: Штрафной коэффициент (большое число)
        """
        self.variable = variable
        self.value = value
        self.component = component
        self.penalty = penalty
        
        if component >= variable.size:
            raise ValueError(f"Компонента {component} вне диапазона для переменной "
                           f"размера {variable.size}")
    
    def get_variables(self) -> List[Variable]:
        return [self.variable]
    
    def contribute_to_stiffness(self, A: np.ndarray, index_map: Dict[Variable, List[int]]):
        indices = index_map[self.variable]
        idx = indices[self.component]
        A[idx, idx] += self.penalty
    
    def contribute_to_load(self, b: np.ndarray, index_map: Dict[Variable, List[int]]):
        indices = index_map[self.variable]
        idx = indices[self.component]
        b[idx] += self.penalty * self.value


class LagrangeConstraint(Constraint):
    """
    Голономная связь, реализованная через множители Лагранжа.
    
    Связь имеет вид: C·x = d
    
    где C - матрица коэффициентов связи, d - правая часть.
    
    Для решения системы с связями используется расширенная матрица:
    [ A   C^T ] [ x ]   [ b ]
    [ C    0  ] [ λ ] = [ d ]
    
    Примеры:
    - Фиксация точки: vx = 0, vy = 0
    - Шарнирная связь: v + ω × r = 0
    - Равенство переменных: u1 = u2
    """
    
    def __init__(self, variables: List[Variable], 
                 coefficients: List[np.ndarray], 
                 rhs: np.ndarray = None):
        """
        Args:
            variables: Список переменных, участвующих в связи
            coefficients: Список матриц коэффициентов для каждой переменной
                         coefficients[i] имеет форму (n_constraints, variables[i].size)
            rhs: Правая часть связи (вектор размера n_constraints), по умолчанию 0
        """
        self.variables = variables
        self.coefficients = [np.atleast_2d(c) for c in coefficients]
        
        # Проверка размерностей
        n_constraints = self.coefficients[0].shape[0]
        for i, (var, coef) in enumerate(zip(variables, self.coefficients)):
            if coef.shape[0] != n_constraints:
                raise ValueError(f"Все матрицы коэффициентов должны иметь одинаковое "
                               f"количество строк (связей)")
            if coef.shape[1] != var.size:
                raise ValueError(f"Матрица коэффициентов {i} имеет {coef.shape[1]} столбцов, "
                               f"ожидалось {var.size}")
        
        self.n_constraints = n_constraints

        self.lambdas = Variable(name="lambda_constraint", size=n_constraints)
        super().__init__([self.variables[0]], [self.lambdas], [])  # Инициализация базового класса Constraint
        
        if rhs is None:
            self.rhs = np.zeros(n_constraints)
        else:
            self.rhs = np.atleast_1d(rhs)
            if len(self.rhs) != n_constraints:
                raise ValueError(f"Размер правой части {len(self.rhs)} не соответствует "
                               f"количеству связей {n_constraints}")
    

    def contribute_to_holonomic(self, C: np.ndarray, 
                       index_map: Dict[Variable, List[int]],
                       lambdas_index_map: Dict[Variable, List[int]]):
        """
        Добавить вклад в матрицу связей C
        
        Args:
            C: Матрица связей (n_constraints_total × n_dofs)
            index_map: Отображение Variable -> список глобальных индексов
        """
        # for var, coef in zip(self.variables, self.coefficients):
        #     var_indices = index_map[var]
        #     for i in range(self.n_constraints):
        #         for j, global_idx in enumerate(var_indices):
        #             C[i, global_idx] += coef[i, j]
        indices = index_map[self.variables[0]]
        contr_indicies = lambdas_index_map[self.lambdas]
        for i in range(self.n_constraints):
            for var, coef in zip(self.variables, self.coefficients):
                var_indices = index_map[var]
                for j, global_idx in enumerate(var_indices):
                    C[contr_indicies[i], global_idx] += coef[i, j]

    def contribute_to_holonomic_load(self, d: np.ndarray,  holonomic_index_map: Dict[Variable, List[int]]):
        """
        Добавить вклад в правую часть связей d
        
        Args:
            d: Вектор правой части связей
        """
        for var in self.variables:
            index = holonomic_index_map[var][0]
            d[index] += self.rhs

# ============================================================================
# Вспомогательные функции для удобства
# ============================================================================

def spring_element(u1: Variable, u2: Variable, stiffness: float) -> BilinearContribution:
    """
    Создать вклад пружины/стержня между двумя скалярными переменными
    
    Уравнение: F = k*(u2-u1)
    Матрица:  [[k, -k],
               [-k, k]]
    """
    K = stiffness * np.array([
        [ 1, -1],
        [-1,  1]
    ])
    return BilinearContribution([u1, u2], K)


def conductance_element(V1: Variable, V2: Variable, conductance: float) -> BilinearContribution:
    """
    Создать вклад проводимости (резистор) между двумя узлами
    
    То же самое что spring_element, но с другим физическим смыслом
    """
    return spring_element(V1, V2, conductance)
