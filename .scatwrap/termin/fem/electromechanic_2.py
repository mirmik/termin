<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/fem/electromechanic_2.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
<br>
from termin.fem.assembler import Contribution, Variable<br>
from termin.fem.electrical_2 import ElectricalNode, CurrentVariable<br>
<br>
class DCMotor(Contribution):<br>
&#9;&quot;&quot;&quot;<br>
&#9;Идеальный электродвигатель постоянного тока:<br>
<br>
&#9;&#9;Электрическая сторона:<br>
&#9;&#9;&#9;V1 - V2 = k_e * omega<br>
<br>
&#9;&#9;Механическая сторона:<br>
&#9;&#9;&#9;torque = k_t * i_motor<br>
<br>
&#9;&#9;Где:<br>
&#9;&#9;&#9;i_motor — ток, протекающий через двигатель<br>
&#9;&#9;&#9;omega   — угловая скорость в механическом домене<br>
&#9;&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self, node1, node2, connected_body, k_e=0.1, k_t=0.1, assembler=None):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;node1, node2:   электрические узлы<br>
&#9;&#9;&#9;omega_var:      Variable(omega) — угловая скорость<br>
&#9;&#9;&#9;k_e:            коэффициент обратной ЭДС (вольт на рад/с)<br>
&#9;&#9;&#9;k_t:            коэффициент момента (ньютон-метр на ампер)<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;self.node1 = node1<br>
&#9;&#9;self.node2 = node2<br>
&#9;&#9;self.connected_body = connected_body<br>
&#9;&#9;self.k_e = float(k_e)<br>
&#9;&#9;self.k_t = float(k_t)<br>
<br>
&#9;&#9;# ток двигателя — как у источников/индуктора<br>
&#9;&#9;self.i = CurrentVariable(&quot;i_motor&quot;)<br>
<br>
&#9;&#9;super().__init__([node1, node2, self.i, self.connected_body.acceleration_var], <br>
&#9;&#9;&#9;domain=&quot;electromechanical&quot;, <br>
&#9;&#9;&#9;assembler=assembler)<br>
<br>
&#9;def contribute(self, matrices, index_maps):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Вкладывает уравнения в матрицы электрического и механического доменов.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;# Матрицы<br>
&#9;&#9;G   = matrices[&quot;conductance&quot;]              # KCL<br>
&#9;&#9;H   = matrices[&quot;electric_holonomic&quot;]       # KVL<br>
&#9;&#9;rhs = matrices[&quot;electric_holonomic_rhs&quot;]   # KVL правая часть<br>
&#9;&#9;EM = matrices[&quot;electromechanic_coupling&quot;]  # электромеханическая связь<br>
&#9;&#9;EM_damping = matrices[&quot;electromechanic_coupling_damping&quot;]  # электромеханическая связь (в демпфирование)<br>
<br>
&#9;&#9;b_rhs = matrices[&quot;load&quot;]         # правая часть сил на ускорения<br>
&#9;&#9;<br>
&#9;&#9;# Индексы<br>
&#9;&#9;vmap = index_maps[&quot;voltage&quot;]<br>
&#9;&#9;cmap = index_maps[&quot;current&quot;]<br>
&#9;&#9;amap = index_maps[&quot;acceleration&quot;]<br>
<br>
&#9;&#9;v1 = vmap[self.node1][0]<br>
&#9;&#9;v2 = vmap[self.node2][0]<br>
&#9;&#9;i  = cmap[self.i][0]<br>
&#9;&#9;angaccel  = amap[self.connected_body.acceleration_var][2]<br>
&#9;&#9;#tau_idx = mmap[self.torque][0]<br>
<br>
&#9;&#9;# ---------------------------------------------------------<br>
&#9;&#9;# 1) Электрическое уравнение двигателя (KVL):<br>
&#9;&#9;#       V1 - V2 = k_e * omega<br>
&#9;&#9;#<br>
&#9;&#9;# В матричной форме:<br>
&#9;&#9;#       H[row, v1] +=  1<br>
&#9;&#9;#       H[row, v2] += -1<br>
&#9;&#9;#       H[row, w ] += -k_e<br>
&#9;&#9;#       rhs[row] +=  0<br>
&#9;&#9;# ---------------------------------------------------------<br>
&#9;&#9;H[i, v1] +=  1.0<br>
&#9;&#9;H[i, v2] += -1.0<br>
&#9;&#9;EM_damping[angaccel, i] += self.k_e # Тут должна быть угловая скорость<br>
<br>
&#9;&#9;# ---------------------------------------------------------<br>
&#9;&#9;# 2) KCL: ток через двигатель<br>
&#9;&#9;# ток входит в node1, выходит из node2<br>
&#9;&#9;# ---------------------------------------------------------<br>
&#9;&#9;# G[v1, i] +=  1.0<br>
&#9;&#9;# G[i, v1] +=  1.0<br>
<br>
&#9;&#9;# G[v2, i] += -1.0<br>
&#9;&#9;# G[i, v2] += -1.0<br>
&#9;&#9;EM[angaccel, i] += -self.k_t<br>
<br>
&#9;&#9;# ---------------------------------------------------------<br>
&#9;&#9;# 3) Механика: момент двигателя<br>
&#9;&#9;#       tau_motor = k_t * i<br>
&#9;&#9;# Просто добавляем момент в мех. RHS<br>
&#9;&#9;# ---------------------------------------------------------<br>
&#9;&#9;# b_rhs[w] += (self.k_t * self.i.get_current()).item()<br>
<br>
&#9;def contribute_for_constraints_correction(self, matrices, index_maps):<br>
&#9;&#9;# та же логика (как у источника напряжения и индуктивности)<br>
&#9;&#9;self.contribute(matrices, index_maps)<br>
<!-- END SCAT CODE -->
</body>
</html>
