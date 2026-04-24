import numpy as np
from typing import List, Dict
from .assembler import Contribution, Variable, Constraint   


class ElectricalContribution(Contribution):
    """
    Базовый класс для электрических элементов.
    """
    def __init__(self, variables: List[Variable], assembler=None):
        super().__init__(variables, domain="electric", assembler=assembler)

class ElectricalNode(Variable):
    """
    Узел электрической цепи с потенциалом (напряжением).
    """
    def __init__(self, name: str, size: int=1, tag: str="voltage"):
        super().__init__(name, size, tag)

    def get_voltage(self) -> np.ndarray:
        """
        Получить текущее значение потенциала узла.
        """
        return self.value

class CurrentVariable(Variable):
    """
    Переменная тока в электрической цепи.
    """
    def __init__(self, name: str, size: int=1, tag: str="current"):
        super().__init__(name, size, tag)

    def get_current(self) -> np.ndarray:
        """
        Получить текущее значение тока.
        """
        return self.value

    def set_current(self, current: np.ndarray):
        """
        Установить значение тока.
        """
        self.set_value_by_rank(current, rank=0)

class Resistor(ElectricalContribution):
    """
    Резистор - линейный элемент.
    
    Закон Ома: U = I * R, или I = (V1 - V2) / R = (V1 - V2) * G
    где G = 1/R - проводимость
    
    Матрица проводимости (аналог матрицы жесткости):
    G_matrix = G * [[ 1, -1],
                    [-1,  1]]
    
    Уравнение: [I1]   = G * [[ 1, -1]] * [V1]
               [I2]         [[-1,  1]]   [V2]
    """
    
    def __init__(self, 
                 node1: Variable,  # потенциал узла 1
                 node2: Variable,  # потенциал узла 2
                 R: float,         # сопротивление [Ом]
                 assembler=None):  # ассемблер для автоматической регистрации
        """
        Args:
            node1: Переменная потенциала первого узла (скаляр)
            node2: Переменная потенциала второго узла (скаляр)
            R: Сопротивление [Ом]
            assembler: MatrixAssembler для автоматической регистрации переменных
        """
        if node1.tag != "voltage" or node2.tag != "voltage":
            raise ValueError("Узлы резистора должны иметь тег 'voltage'")

        if node1.size != 1 or node2.size != 1:
            raise ValueError("Узлы должны быть скалярами (потенциалы)")
        
        if R <= 0:
            raise ValueError("Сопротивление должно быть положительным")
        
        super().__init__([node1, node2], assembler)
        
        self.node1 = node1
        self.node2 = node2
        self.R = R
        self.G = 1.0 / R  # проводимость
        self.G_matrix = np.array([
            [ 1, -1],
            [-1,  1]
        ]) * self.G
    
    def contribute(self, matrices, index_maps: Dict[Variable, List[int]]):
        """
        Добавляет вклад резистора в матрицу проводимости
        """
        G = matrices["conductance"]
        index_map = index_maps["voltage"]
        
        idx1 = index_map[self.node1][0]
        idx2 = index_map[self.node2][0]
        global_indices = [idx1, idx2]
        
        for i, gi in enumerate(global_indices):
            for j, gj in enumerate(global_indices):
                G[gi, gj] += self.G_matrix[i, j]


class VoltageSource(ElectricalContribution):
    """
    Идеальный источник напряжения: V1 - V2 = U
    """

    def __init__(self, node1, node2, U, assembler=None):
        self.node1 = node1
        self.node2 = node2
        self.U = float(U)

        # вводим ток как лагранжевый множитель
        self.i = Variable("i_vs", size=1, tag="current")

        super().__init__([node1, node2, self.i], assembler)

    def contribute(self, matrices, index_maps):
        H = matrices["electric_holonomic"]   # матрица ограничений
        rhs = matrices["electric_holonomic_rhs"]

        vmap = index_maps["voltage"]
        cmap = index_maps["current"]

        row = cmap[self.i][0]
        v1 = vmap[self.node1][0]
        v2 = vmap[self.node2][0]

        # V1 - V2 = U
        H[row, v1] += -1.0
        H[row, v2] += 1.0

        rhs[row] += -self.U


class Ground(ElectricalContribution):
    """
    Электрическая земля — фиксирует потенциал узла:
        V_node = 0

    Делается через голономное ограничение.
    """

    def __init__(self, node: Variable, assembler=None):
        """
        Args:
            node: Variable — потенциал узла (скаляр)
        """
        if node.size != 1:
            raise ValueError("Ground может быть подключён только к скалярному потенциалу узла")

        self.node = node

        # Множитель Лагранжа на 1 ограничение
        self.lmbd = Variable("lambda_ground", size=1, tag="current")

        # Регистрируем node (но он уже зарегистрирован в схеме) и lambda
        super().__init__([self.node, self.lmbd], assembler)

    def contribute(self, matrices, index_maps):
        """
        Добавить вклад в матрицы ускорений (точнее: в систему ограничений)
        """
        H = matrices["electric_holonomic"]
        rhs = matrices["electric_holonomic_rhs"]

        # индексы
        cmap = index_maps["current"]
        vmap = index_maps["voltage"]  # узлы — это группа voltage

        row = cmap[self.lmbd][0]
        col = vmap[self.node][0]

        # Ограничение: V_node = 0
        H[row, col] += 1.0

        # rhs = 0
        # rhs[row] += 0.0
    

class Capacitor(ElectricalContribution):
    def __init__(self, node1, node2, C, assembler=None):
        super().__init__([node1, node2], assembler)
        self.node1 = node1
        self.node2 = node2
        self.C = float(C)

        # состояние на шаге n-1
        self.v_prev = 0.0     # v_{n-1}
        self.i_prev = 0.0     # i_{n-1}

    def contribute(self, matrices, index_maps):
        dt = self.assembler.time_step
        Geq = 2.0 * self.C / dt
        Ieq = Geq * self.v_prev + self.i_prev 

        G = matrices["conductance"]
        I = matrices["rhs"]
        vmap = index_maps["voltage"]
        n1 = vmap[self.node1][0]
        n2 = vmap[self.node2][0]

        # эквивалентная проводимость (как резистор)
        G[n1, n1] += Geq
        G[n1, n2] -= Geq
        G[n2, n1] -= Geq
        G[n2, n2] += Geq

        # эквивалентный источнику ток
        I[n1] += Ieq
        I[n2] -= Ieq

    def finish_timestep(self):
        # вызывать ПОСЛЕ solver'а и set_solution
        dt = self.assembler.time_step
        v_now = (self.node1.get_voltage() - self.node2.get_voltage()).item()  # v_n

        # сначала считаем i_n из v_n и v_{n-1}
        i_now = self.C * (v_now - self.v_prev) / dt

        # затем передвигаем «историю»: (n ← n-1) для следующего шага
        self.v_prev = v_now
        self.i_prev = i_now

    def voltage_difference(self) -> np.ndarray:
        """
        Разность потенциалов на конденсаторе: V_node1 - V_node2
        """
        return self.node1.get_voltage() - self.node2.get_voltage()


class Inductor(ElectricalContribution):
    """
    Идеальная индуктивность (TRAP):
        v = L di/dt
    TRAP даёт:
        v_n = R_eq * i_n + V_eq

    где:
        R_eq = 2L / dt
        V_eq = -R_eq * i_prev - v_prev
    """

    def __init__(self, node1, node2, L, assembler=None):
        self.node1 = node1
        self.node2 = node2
        self.L = float(L)

        # переменная тока через индуктивность
        self.i_var = CurrentVariable("i_L")

        super().__init__([node1, node2, self.i_var], assembler)

        # состояние TRAP
        self.i_prev = 0.0  # ток в момент времени n-1
        self.v_prev = 0.0  # напряжение в момент времени n-1 (v1 - v2)

    def contribute(self, matrices, index_maps):
        dt = self.assembler.time_step
        R_eq = 2.0 * self.L / dt

        # эквивалентный источник TRAP
        Veq = -R_eq * self.i_prev - self.v_prev

        H = matrices["electric_holonomic"]
        C = matrices["current_to_current"]
        rhs = matrices["electric_holonomic_rhs"]

        vmap = index_maps["voltage"]
        cmap = index_maps["current"]

        v1 = vmap[self.node1][0]
        v2 = vmap[self.node2][0]
        irow = cmap[self.i_var][0]

        # KVL:
        #   v1 - v2 - R_eq * i = Veq
        H[irow, v1] +=  1.0
        H[irow, v2] += -1.0
        C[irow, irow] += -R_eq
        rhs[irow] += Veq

    def finish_timestep(self):
        # новое напряжение
        v_now = (self.node1.get_voltage() - self.node2.get_voltage()).item()

        # новое решение тока
        i_now = self.i_var.get_current().item()

        # обновление состояния
        self.i_prev = i_now
        self.v_prev = v_now

    def current(self) -> np.ndarray:
        """
        Ток через индуктивность
        """
        return self.i_var.get_current()
        

class CurrentSource(ElectricalContribution):
    """
    Идеальный источник тока: +I в node1, -I в node2
    """
    def __init__(self, node1, node2, I, assembler=None):
        self.node1 = node1
        self.node2 = node2
        self.I = float(I)
        super().__init__([node1, node2], assembler)

    def contribute(self, matrices, index_maps):
        b = matrices["rhs"]
        vmap = index_maps["voltage"]

        i1 = vmap[self.node1][0]
        i2 = vmap[self.node2][0]

        b[i1] +=  self.I
        b[i2] += -self.I
