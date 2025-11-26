<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/fem/electrical_2.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
import numpy as np<br>
from typing import List, Dict<br>
from .assembler import Contribution, Variable, Constraint   <br>
<br>
<br>
class ElectricalContribution(Contribution):<br>
    &quot;&quot;&quot;<br>
    Базовый класс для электрических элементов.<br>
    &quot;&quot;&quot;<br>
    def __init__(self, variables: List[Variable], assembler=None):<br>
        super().__init__(variables, domain=&quot;electric&quot;, assembler=assembler)<br>
<br>
class ElectricalNode(Variable):<br>
    &quot;&quot;&quot;<br>
    Узел электрической цепи с потенциалом (напряжением).<br>
    &quot;&quot;&quot;<br>
    def __init__(self, name: str, size: int=1, tag: str=&quot;voltage&quot;):<br>
        super().__init__(name, size, tag)<br>
<br>
    def get_voltage(self) -&gt; np.ndarray:<br>
        &quot;&quot;&quot;<br>
        Получить текущее значение потенциала узла.<br>
        &quot;&quot;&quot;<br>
        return self.value<br>
<br>
class CurrentVariable(Variable):<br>
    &quot;&quot;&quot;<br>
    Переменная тока в электрической цепи.<br>
    &quot;&quot;&quot;<br>
    def __init__(self, name: str, size: int=1, tag: str=&quot;current&quot;):<br>
        super().__init__(name, size, tag)<br>
<br>
    def get_current(self) -&gt; np.ndarray:<br>
        &quot;&quot;&quot;<br>
        Получить текущее значение тока.<br>
        &quot;&quot;&quot;<br>
        return self.value<br>
<br>
    def set_current(self, current: np.ndarray):<br>
        &quot;&quot;&quot;<br>
        Установить значение тока.<br>
        &quot;&quot;&quot;<br>
        self.set_value_by_rank(current, rank=0)<br>
<br>
class Resistor(ElectricalContribution):<br>
    &quot;&quot;&quot;<br>
    Резистор - линейный элемент.<br>
    <br>
    Закон Ома: U = I * R, или I = (V1 - V2) / R = (V1 - V2) * G<br>
    где G = 1/R - проводимость<br>
    <br>
    Матрица проводимости (аналог матрицы жесткости):<br>
    G_matrix = G * [[ 1, -1],<br>
                    [-1,  1]]<br>
    <br>
    Уравнение: [I1]   = G * [[ 1, -1]] * [V1]<br>
               [I2]         [[-1,  1]]   [V2]<br>
    &quot;&quot;&quot;<br>
    <br>
    def __init__(self, <br>
                 node1: Variable,  # потенциал узла 1<br>
                 node2: Variable,  # потенциал узла 2<br>
                 R: float,         # сопротивление [Ом]<br>
                 assembler=None):  # ассемблер для автоматической регистрации<br>
        &quot;&quot;&quot;<br>
        Args:<br>
            node1: Переменная потенциала первого узла (скаляр)<br>
            node2: Переменная потенциала второго узла (скаляр)<br>
            R: Сопротивление [Ом]<br>
            assembler: MatrixAssembler для автоматической регистрации переменных<br>
        &quot;&quot;&quot;<br>
        if node1.tag != &quot;voltage&quot; or node2.tag != &quot;voltage&quot;:<br>
            raise ValueError(&quot;Узлы резистора должны иметь тег 'voltage'&quot;)<br>
<br>
        if node1.size != 1 or node2.size != 1:<br>
            raise ValueError(&quot;Узлы должны быть скалярами (потенциалы)&quot;)<br>
        <br>
        if R &lt;= 0:<br>
            raise ValueError(&quot;Сопротивление должно быть положительным&quot;)<br>
        <br>
        super().__init__([node1, node2], assembler)<br>
        <br>
        self.node1 = node1<br>
        self.node2 = node2<br>
        self.R = R<br>
        self.G = 1.0 / R  # проводимость<br>
        self.G_matrix = np.array([<br>
            [ 1, -1],<br>
            [-1,  1]<br>
        ]) * self.G<br>
    <br>
    def contribute(self, matrices, index_maps: Dict[Variable, List[int]]):<br>
        &quot;&quot;&quot;<br>
        Добавляет вклад резистора в матрицу проводимости<br>
        &quot;&quot;&quot;<br>
        G = matrices[&quot;conductance&quot;]<br>
        index_map = index_maps[&quot;voltage&quot;]<br>
        <br>
        idx1 = index_map[self.node1][0]<br>
        idx2 = index_map[self.node2][0]<br>
        global_indices = [idx1, idx2]<br>
        <br>
        for i, gi in enumerate(global_indices):<br>
            for j, gj in enumerate(global_indices):<br>
                G[gi, gj] += self.G_matrix[i, j]<br>
<br>
<br>
class VoltageSource(ElectricalContribution):<br>
    &quot;&quot;&quot;<br>
    Идеальный источник напряжения: V1 - V2 = U<br>
    &quot;&quot;&quot;<br>
<br>
    def __init__(self, node1, node2, U, assembler=None):<br>
        self.node1 = node1<br>
        self.node2 = node2<br>
        self.U = float(U)<br>
<br>
        # вводим ток как лагранжевый множитель<br>
        self.i = Variable(&quot;i_vs&quot;, size=1, tag=&quot;current&quot;)<br>
<br>
        super().__init__([node1, node2, self.i], assembler)<br>
<br>
    def contribute(self, matrices, index_maps):<br>
        H = matrices[&quot;electric_holonomic&quot;]   # матрица ограничений<br>
        rhs = matrices[&quot;electric_holonomic_rhs&quot;]<br>
<br>
        vmap = index_maps[&quot;voltage&quot;]<br>
        cmap = index_maps[&quot;current&quot;]<br>
<br>
        row = cmap[self.i][0]<br>
        v1 = vmap[self.node1][0]<br>
        v2 = vmap[self.node2][0]<br>
<br>
        # V1 - V2 = U<br>
        H[row, v1] += -1.0<br>
        H[row, v2] += 1.0<br>
<br>
        rhs[row] += -self.U<br>
<br>
<br>
class Ground(ElectricalContribution):<br>
    &quot;&quot;&quot;<br>
    Электрическая земля — фиксирует потенциал узла:<br>
        V_node = 0<br>
<br>
    Делается через голономное ограничение.<br>
    &quot;&quot;&quot;<br>
<br>
    def __init__(self, node: Variable, assembler=None):<br>
        &quot;&quot;&quot;<br>
        Args:<br>
            node: Variable — потенциал узла (скаляр)<br>
        &quot;&quot;&quot;<br>
        if node.size != 1:<br>
            raise ValueError(&quot;Ground может быть подключён только к скалярному потенциалу узла&quot;)<br>
<br>
        self.node = node<br>
<br>
        # Множитель Лагранжа на 1 ограничение<br>
        self.lmbd = Variable(&quot;lambda_ground&quot;, size=1, tag=&quot;current&quot;)<br>
<br>
        # Регистрируем node (но он уже зарегистрирован в схеме) и lambda<br>
        super().__init__([self.node, self.lmbd], assembler)<br>
<br>
    def contribute(self, matrices, index_maps):<br>
        &quot;&quot;&quot;<br>
        Добавить вклад в матрицы ускорений (точнее: в систему ограничений)<br>
        &quot;&quot;&quot;<br>
        H = matrices[&quot;electric_holonomic&quot;]<br>
        rhs = matrices[&quot;electric_holonomic_rhs&quot;]<br>
<br>
        # индексы<br>
        cmap = index_maps[&quot;current&quot;]<br>
        vmap = index_maps[&quot;voltage&quot;]  # узлы — это группа voltage<br>
<br>
        row = cmap[self.lmbd][0]<br>
        col = vmap[self.node][0]<br>
<br>
        # Ограничение: V_node = 0<br>
        H[row, col] += 1.0<br>
<br>
        # rhs = 0<br>
        # rhs[row] += 0.0<br>
    <br>
<br>
class Capacitor(ElectricalContribution):<br>
    def __init__(self, node1, node2, C, assembler=None):<br>
        super().__init__([node1, node2], assembler)<br>
        self.node1 = node1<br>
        self.node2 = node2<br>
        self.C = float(C)<br>
<br>
        # состояние на шаге n-1<br>
        self.v_prev = 0.0     # v_{n-1}<br>
        self.i_prev = 0.0     # i_{n-1}<br>
<br>
    def contribute(self, matrices, index_maps):<br>
        dt = self.assembler.time_step<br>
        Geq = 2.0 * self.C / dt<br>
        Ieq = Geq * self.v_prev + self.i_prev <br>
<br>
        G = matrices[&quot;conductance&quot;]<br>
        I = matrices[&quot;rhs&quot;]<br>
        vmap = index_maps[&quot;voltage&quot;]<br>
        n1 = vmap[self.node1][0]<br>
        n2 = vmap[self.node2][0]<br>
<br>
        # эквивалентная проводимость (как резистор)<br>
        G[n1, n1] += Geq<br>
        G[n1, n2] -= Geq<br>
        G[n2, n1] -= Geq<br>
        G[n2, n2] += Geq<br>
<br>
        # эквивалентный источнику ток<br>
        I[n1] += Ieq<br>
        I[n2] -= Ieq<br>
<br>
    def finish_timestep(self):<br>
        # вызывать ПОСЛЕ solver'а и set_solution<br>
        dt = self.assembler.time_step<br>
        v_now = (self.node1.get_voltage() - self.node2.get_voltage()).item()  # v_n<br>
<br>
        # сначала считаем i_n из v_n и v_{n-1}<br>
        i_now = self.C * (v_now - self.v_prev) / dt<br>
<br>
        # затем передвигаем «историю»: (n ← n-1) для следующего шага<br>
        self.v_prev = v_now<br>
        self.i_prev = i_now<br>
<br>
    def voltage_difference(self) -&gt; np.ndarray:<br>
        &quot;&quot;&quot;<br>
        Разность потенциалов на конденсаторе: V_node1 - V_node2<br>
        &quot;&quot;&quot;<br>
        return self.node1.get_voltage() - self.node2.get_voltage()<br>
<br>
<br>
class Inductor(ElectricalContribution):<br>
    &quot;&quot;&quot;<br>
    Идеальная индуктивность (TRAP):<br>
        v = L di/dt<br>
    TRAP даёт:<br>
        v_n = R_eq * i_n + V_eq<br>
<br>
    где:<br>
        R_eq = 2L / dt<br>
        V_eq = -R_eq * i_prev - v_prev<br>
    &quot;&quot;&quot;<br>
<br>
    def __init__(self, node1, node2, L, assembler=None):<br>
        self.node1 = node1<br>
        self.node2 = node2<br>
        self.L = float(L)<br>
<br>
        # переменная тока через индуктивность<br>
        self.i_var = CurrentVariable(&quot;i_L&quot;)<br>
<br>
        super().__init__([node1, node2, self.i_var], assembler)<br>
<br>
        # состояние TRAP<br>
        self.i_prev = 0.0  # ток в момент времени n-1<br>
        self.v_prev = 0.0  # напряжение в момент времени n-1 (v1 - v2)<br>
<br>
    def contribute(self, matrices, index_maps):<br>
        dt = self.assembler.time_step<br>
        R_eq = 2.0 * self.L / dt<br>
<br>
        # эквивалентный источник TRAP<br>
        Veq = -R_eq * self.i_prev - self.v_prev<br>
<br>
        H = matrices[&quot;electric_holonomic&quot;]<br>
        C = matrices[&quot;current_to_current&quot;]<br>
        rhs = matrices[&quot;electric_holonomic_rhs&quot;]<br>
<br>
        vmap = index_maps[&quot;voltage&quot;]<br>
        cmap = index_maps[&quot;current&quot;]<br>
<br>
        v1 = vmap[self.node1][0]<br>
        v2 = vmap[self.node2][0]<br>
        irow = cmap[self.i_var][0]<br>
<br>
        # KVL:<br>
        #   v1 - v2 - R_eq * i = Veq<br>
        H[irow, v1] +=  1.0<br>
        H[irow, v2] += -1.0<br>
        C[irow, irow] += -R_eq<br>
        rhs[irow] += Veq<br>
<br>
    def finish_timestep(self):<br>
        # новое напряжение<br>
        v_now = (self.node1.get_voltage() - self.node2.get_voltage()).item()<br>
<br>
        # новое решение тока<br>
        i_now = self.i_var.get_current().item()<br>
<br>
        # обновление состояния<br>
        self.i_prev = i_now<br>
        self.v_prev = v_now<br>
<br>
    def current(self) -&gt; np.ndarray:<br>
        &quot;&quot;&quot;<br>
        Ток через индуктивность<br>
        &quot;&quot;&quot;<br>
        return self.i_var.get_current()<br>
        <br>
<br>
class CurrentSource(ElectricalContribution):<br>
    &quot;&quot;&quot;<br>
    Идеальный источник тока: +I в node1, -I в node2<br>
    &quot;&quot;&quot;<br>
    def __init__(self, node1, node2, I, assembler=None):<br>
        self.node1 = node1<br>
        self.node2 = node2<br>
        self.I = float(I)<br>
        super().__init__([node1, node2], assembler)<br>
<br>
    def contribute(self, matrices, index_maps):<br>
        b = matrices[&quot;rhs&quot;]<br>
        vmap = index_maps[&quot;voltage&quot;]<br>
<br>
        i1 = vmap[self.node1][0]<br>
        i2 = vmap[self.node2][0]<br>
<br>
        b[i1] +=  self.I<br>
        b[i2] += -self.I<br>
<!-- END SCAT CODE -->
</body>
</html>
