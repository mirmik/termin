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
&#9;&quot;&quot;&quot;<br>
&#9;Базовый класс для электрических элементов.<br>
&#9;&quot;&quot;&quot;<br>
&#9;def __init__(self, variables: List[Variable], assembler=None):<br>
&#9;&#9;super().__init__(variables, domain=&quot;electric&quot;, assembler=assembler)<br>
<br>
class ElectricalNode(Variable):<br>
&#9;&quot;&quot;&quot;<br>
&#9;Узел электрической цепи с потенциалом (напряжением).<br>
&#9;&quot;&quot;&quot;<br>
&#9;def __init__(self, name: str, size: int=1, tag: str=&quot;voltage&quot;):<br>
&#9;&#9;super().__init__(name, size, tag)<br>
<br>
&#9;def get_voltage(self) -&gt; np.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Получить текущее значение потенциала узла.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;return self.value<br>
<br>
class CurrentVariable(Variable):<br>
&#9;&quot;&quot;&quot;<br>
&#9;Переменная тока в электрической цепи.<br>
&#9;&quot;&quot;&quot;<br>
&#9;def __init__(self, name: str, size: int=1, tag: str=&quot;current&quot;):<br>
&#9;&#9;super().__init__(name, size, tag)<br>
<br>
&#9;def get_current(self) -&gt; np.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Получить текущее значение тока.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;return self.value<br>
<br>
&#9;def set_current(self, current: np.ndarray):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Установить значение тока.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;self.set_value_by_rank(current, rank=0)<br>
<br>
class Resistor(ElectricalContribution):<br>
&#9;&quot;&quot;&quot;<br>
&#9;Резистор - линейный элемент.<br>
&#9;<br>
&#9;Закон Ома: U = I * R, или I = (V1 - V2) / R = (V1 - V2) * G<br>
&#9;где G = 1/R - проводимость<br>
&#9;<br>
&#9;Матрица проводимости (аналог матрицы жесткости):<br>
&#9;G_matrix = G * [[ 1, -1],<br>
&#9;&#9;&#9;&#9;&#9;[-1,  1]]<br>
&#9;<br>
&#9;Уравнение: [I1]   = G * [[ 1, -1]] * [V1]<br>
&#9;&#9;&#9;[I2]         [[-1,  1]]   [V2]<br>
&#9;&quot;&quot;&quot;<br>
&#9;<br>
&#9;def __init__(self, <br>
&#9;&#9;&#9;&#9;node1: Variable,  # потенциал узла 1<br>
&#9;&#9;&#9;&#9;node2: Variable,  # потенциал узла 2<br>
&#9;&#9;&#9;&#9;R: float,         # сопротивление [Ом]<br>
&#9;&#9;&#9;&#9;assembler=None):  # ассемблер для автоматической регистрации<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;node1: Переменная потенциала первого узла (скаляр)<br>
&#9;&#9;&#9;node2: Переменная потенциала второго узла (скаляр)<br>
&#9;&#9;&#9;R: Сопротивление [Ом]<br>
&#9;&#9;&#9;assembler: MatrixAssembler для автоматической регистрации переменных<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;if node1.tag != &quot;voltage&quot; or node2.tag != &quot;voltage&quot;:<br>
&#9;&#9;&#9;raise ValueError(&quot;Узлы резистора должны иметь тег 'voltage'&quot;)<br>
<br>
&#9;&#9;if node1.size != 1 or node2.size != 1:<br>
&#9;&#9;&#9;raise ValueError(&quot;Узлы должны быть скалярами (потенциалы)&quot;)<br>
&#9;&#9;<br>
&#9;&#9;if R &lt;= 0:<br>
&#9;&#9;&#9;raise ValueError(&quot;Сопротивление должно быть положительным&quot;)<br>
&#9;&#9;<br>
&#9;&#9;super().__init__([node1, node2], assembler)<br>
&#9;&#9;<br>
&#9;&#9;self.node1 = node1<br>
&#9;&#9;self.node2 = node2<br>
&#9;&#9;self.R = R<br>
&#9;&#9;self.G = 1.0 / R  # проводимость<br>
&#9;&#9;self.G_matrix = np.array([<br>
&#9;&#9;&#9;[ 1, -1],<br>
&#9;&#9;&#9;[-1,  1]<br>
&#9;&#9;]) * self.G<br>
&#9;<br>
&#9;def contribute(self, matrices, index_maps: Dict[Variable, List[int]]):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Добавляет вклад резистора в матрицу проводимости<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;G = matrices[&quot;conductance&quot;]<br>
&#9;&#9;index_map = index_maps[&quot;voltage&quot;]<br>
&#9;&#9;<br>
&#9;&#9;idx1 = index_map[self.node1][0]<br>
&#9;&#9;idx2 = index_map[self.node2][0]<br>
&#9;&#9;global_indices = [idx1, idx2]<br>
&#9;&#9;<br>
&#9;&#9;for i, gi in enumerate(global_indices):<br>
&#9;&#9;&#9;for j, gj in enumerate(global_indices):<br>
&#9;&#9;&#9;&#9;G[gi, gj] += self.G_matrix[i, j]<br>
<br>
<br>
class VoltageSource(ElectricalContribution):<br>
&#9;&quot;&quot;&quot;<br>
&#9;Идеальный источник напряжения: V1 - V2 = U<br>
&#9;&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self, node1, node2, U, assembler=None):<br>
&#9;&#9;self.node1 = node1<br>
&#9;&#9;self.node2 = node2<br>
&#9;&#9;self.U = float(U)<br>
<br>
&#9;&#9;# вводим ток как лагранжевый множитель<br>
&#9;&#9;self.i = Variable(&quot;i_vs&quot;, size=1, tag=&quot;current&quot;)<br>
<br>
&#9;&#9;super().__init__([node1, node2, self.i], assembler)<br>
<br>
&#9;def contribute(self, matrices, index_maps):<br>
&#9;&#9;H = matrices[&quot;electric_holonomic&quot;]   # матрица ограничений<br>
&#9;&#9;rhs = matrices[&quot;electric_holonomic_rhs&quot;]<br>
<br>
&#9;&#9;vmap = index_maps[&quot;voltage&quot;]<br>
&#9;&#9;cmap = index_maps[&quot;current&quot;]<br>
<br>
&#9;&#9;row = cmap[self.i][0]<br>
&#9;&#9;v1 = vmap[self.node1][0]<br>
&#9;&#9;v2 = vmap[self.node2][0]<br>
<br>
&#9;&#9;# V1 - V2 = U<br>
&#9;&#9;H[row, v1] += -1.0<br>
&#9;&#9;H[row, v2] += 1.0<br>
<br>
&#9;&#9;rhs[row] += -self.U<br>
<br>
<br>
class Ground(ElectricalContribution):<br>
&#9;&quot;&quot;&quot;<br>
&#9;Электрическая земля — фиксирует потенциал узла:<br>
&#9;&#9;V_node = 0<br>
<br>
&#9;Делается через голономное ограничение.<br>
&#9;&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self, node: Variable, assembler=None):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;node: Variable — потенциал узла (скаляр)<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;if node.size != 1:<br>
&#9;&#9;&#9;raise ValueError(&quot;Ground может быть подключён только к скалярному потенциалу узла&quot;)<br>
<br>
&#9;&#9;self.node = node<br>
<br>
&#9;&#9;# Множитель Лагранжа на 1 ограничение<br>
&#9;&#9;self.lmbd = Variable(&quot;lambda_ground&quot;, size=1, tag=&quot;current&quot;)<br>
<br>
&#9;&#9;# Регистрируем node (но он уже зарегистрирован в схеме) и lambda<br>
&#9;&#9;super().__init__([self.node, self.lmbd], assembler)<br>
<br>
&#9;def contribute(self, matrices, index_maps):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Добавить вклад в матрицы ускорений (точнее: в систему ограничений)<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;H = matrices[&quot;electric_holonomic&quot;]<br>
&#9;&#9;rhs = matrices[&quot;electric_holonomic_rhs&quot;]<br>
<br>
&#9;&#9;# индексы<br>
&#9;&#9;cmap = index_maps[&quot;current&quot;]<br>
&#9;&#9;vmap = index_maps[&quot;voltage&quot;]  # узлы — это группа voltage<br>
<br>
&#9;&#9;row = cmap[self.lmbd][0]<br>
&#9;&#9;col = vmap[self.node][0]<br>
<br>
&#9;&#9;# Ограничение: V_node = 0<br>
&#9;&#9;H[row, col] += 1.0<br>
<br>
&#9;&#9;# rhs = 0<br>
&#9;&#9;# rhs[row] += 0.0<br>
&#9;<br>
<br>
class Capacitor(ElectricalContribution):<br>
&#9;def __init__(self, node1, node2, C, assembler=None):<br>
&#9;&#9;super().__init__([node1, node2], assembler)<br>
&#9;&#9;self.node1 = node1<br>
&#9;&#9;self.node2 = node2<br>
&#9;&#9;self.C = float(C)<br>
<br>
&#9;&#9;# состояние на шаге n-1<br>
&#9;&#9;self.v_prev = 0.0     # v_{n-1}<br>
&#9;&#9;self.i_prev = 0.0     # i_{n-1}<br>
<br>
&#9;def contribute(self, matrices, index_maps):<br>
&#9;&#9;dt = self.assembler.time_step<br>
&#9;&#9;Geq = 2.0 * self.C / dt<br>
&#9;&#9;Ieq = Geq * self.v_prev + self.i_prev <br>
<br>
&#9;&#9;G = matrices[&quot;conductance&quot;]<br>
&#9;&#9;I = matrices[&quot;rhs&quot;]<br>
&#9;&#9;vmap = index_maps[&quot;voltage&quot;]<br>
&#9;&#9;n1 = vmap[self.node1][0]<br>
&#9;&#9;n2 = vmap[self.node2][0]<br>
<br>
&#9;&#9;# эквивалентная проводимость (как резистор)<br>
&#9;&#9;G[n1, n1] += Geq<br>
&#9;&#9;G[n1, n2] -= Geq<br>
&#9;&#9;G[n2, n1] -= Geq<br>
&#9;&#9;G[n2, n2] += Geq<br>
<br>
&#9;&#9;# эквивалентный источнику ток<br>
&#9;&#9;I[n1] += Ieq<br>
&#9;&#9;I[n2] -= Ieq<br>
<br>
&#9;def finish_timestep(self):<br>
&#9;&#9;# вызывать ПОСЛЕ solver'а и set_solution<br>
&#9;&#9;dt = self.assembler.time_step<br>
&#9;&#9;v_now = (self.node1.get_voltage() - self.node2.get_voltage()).item()  # v_n<br>
<br>
&#9;&#9;# сначала считаем i_n из v_n и v_{n-1}<br>
&#9;&#9;i_now = self.C * (v_now - self.v_prev) / dt<br>
<br>
&#9;&#9;# затем передвигаем «историю»: (n ← n-1) для следующего шага<br>
&#9;&#9;self.v_prev = v_now<br>
&#9;&#9;self.i_prev = i_now<br>
<br>
&#9;def voltage_difference(self) -&gt; np.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Разность потенциалов на конденсаторе: V_node1 - V_node2<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;return self.node1.get_voltage() - self.node2.get_voltage()<br>
<br>
<br>
class Inductor(ElectricalContribution):<br>
&#9;&quot;&quot;&quot;<br>
&#9;Идеальная индуктивность (TRAP):<br>
&#9;&#9;v = L di/dt<br>
&#9;TRAP даёт:<br>
&#9;&#9;v_n = R_eq * i_n + V_eq<br>
<br>
&#9;где:<br>
&#9;&#9;R_eq = 2L / dt<br>
&#9;&#9;V_eq = -R_eq * i_prev - v_prev<br>
&#9;&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self, node1, node2, L, assembler=None):<br>
&#9;&#9;self.node1 = node1<br>
&#9;&#9;self.node2 = node2<br>
&#9;&#9;self.L = float(L)<br>
<br>
&#9;&#9;# переменная тока через индуктивность<br>
&#9;&#9;self.i_var = CurrentVariable(&quot;i_L&quot;)<br>
<br>
&#9;&#9;super().__init__([node1, node2, self.i_var], assembler)<br>
<br>
&#9;&#9;# состояние TRAP<br>
&#9;&#9;self.i_prev = 0.0  # ток в момент времени n-1<br>
&#9;&#9;self.v_prev = 0.0  # напряжение в момент времени n-1 (v1 - v2)<br>
<br>
&#9;def contribute(self, matrices, index_maps):<br>
&#9;&#9;dt = self.assembler.time_step<br>
&#9;&#9;R_eq = 2.0 * self.L / dt<br>
<br>
&#9;&#9;# эквивалентный источник TRAP<br>
&#9;&#9;Veq = -R_eq * self.i_prev - self.v_prev<br>
<br>
&#9;&#9;H = matrices[&quot;electric_holonomic&quot;]<br>
&#9;&#9;C = matrices[&quot;current_to_current&quot;]<br>
&#9;&#9;rhs = matrices[&quot;electric_holonomic_rhs&quot;]<br>
<br>
&#9;&#9;vmap = index_maps[&quot;voltage&quot;]<br>
&#9;&#9;cmap = index_maps[&quot;current&quot;]<br>
<br>
&#9;&#9;v1 = vmap[self.node1][0]<br>
&#9;&#9;v2 = vmap[self.node2][0]<br>
&#9;&#9;irow = cmap[self.i_var][0]<br>
<br>
&#9;&#9;# KVL:<br>
&#9;&#9;#   v1 - v2 - R_eq * i = Veq<br>
&#9;&#9;H[irow, v1] +=  1.0<br>
&#9;&#9;H[irow, v2] += -1.0<br>
&#9;&#9;C[irow, irow] += -R_eq<br>
&#9;&#9;rhs[irow] += Veq<br>
<br>
&#9;def finish_timestep(self):<br>
&#9;&#9;# новое напряжение<br>
&#9;&#9;v_now = (self.node1.get_voltage() - self.node2.get_voltage()).item()<br>
<br>
&#9;&#9;# новое решение тока<br>
&#9;&#9;i_now = self.i_var.get_current().item()<br>
<br>
&#9;&#9;# обновление состояния<br>
&#9;&#9;self.i_prev = i_now<br>
&#9;&#9;self.v_prev = v_now<br>
<br>
&#9;def current(self) -&gt; np.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Ток через индуктивность<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;return self.i_var.get_current()<br>
&#9;&#9;<br>
<br>
class CurrentSource(ElectricalContribution):<br>
&#9;&quot;&quot;&quot;<br>
&#9;Идеальный источник тока: +I в node1, -I в node2<br>
&#9;&quot;&quot;&quot;<br>
&#9;def __init__(self, node1, node2, I, assembler=None):<br>
&#9;&#9;self.node1 = node1<br>
&#9;&#9;self.node2 = node2<br>
&#9;&#9;self.I = float(I)<br>
&#9;&#9;super().__init__([node1, node2], assembler)<br>
<br>
&#9;def contribute(self, matrices, index_maps):<br>
&#9;&#9;b = matrices[&quot;rhs&quot;]<br>
&#9;&#9;vmap = index_maps[&quot;voltage&quot;]<br>
<br>
&#9;&#9;i1 = vmap[self.node1][0]<br>
&#9;&#9;i2 = vmap[self.node2][0]<br>
<br>
&#9;&#9;b[i1] +=  self.I<br>
&#9;&#9;b[i2] += -self.I<br>
<!-- END SCAT CODE -->
</body>
</html>
