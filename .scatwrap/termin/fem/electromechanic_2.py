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
    &quot;&quot;&quot;<br>
    Идеальный электродвигатель постоянного тока:<br>
<br>
        Электрическая сторона:<br>
            V1 - V2 = k_e * omega<br>
<br>
        Механическая сторона:<br>
            torque = k_t * i_motor<br>
<br>
        Где:<br>
            i_motor — ток, протекающий через двигатель<br>
            omega   — угловая скорость в механическом домене<br>
    &quot;&quot;&quot;<br>
<br>
    def __init__(self, node1, node2, connected_body, k_e=0.1, k_t=0.1, assembler=None):<br>
        &quot;&quot;&quot;<br>
        Args:<br>
            node1, node2:   электрические узлы<br>
            omega_var:      Variable(omega) — угловая скорость<br>
            k_e:            коэффициент обратной ЭДС (вольт на рад/с)<br>
            k_t:            коэффициент момента (ньютон-метр на ампер)<br>
        &quot;&quot;&quot;<br>
        self.node1 = node1<br>
        self.node2 = node2<br>
        self.connected_body = connected_body<br>
        self.k_e = float(k_e)<br>
        self.k_t = float(k_t)<br>
<br>
        # ток двигателя — как у источников/индуктора<br>
        self.i = CurrentVariable(&quot;i_motor&quot;)<br>
<br>
        super().__init__([node1, node2, self.i, self.connected_body.acceleration_var], <br>
            domain=&quot;electromechanical&quot;, <br>
            assembler=assembler)<br>
<br>
    def contribute(self, matrices, index_maps):<br>
        &quot;&quot;&quot;<br>
        Вкладывает уравнения в матрицы электрического и механического доменов.<br>
        &quot;&quot;&quot;<br>
        # Матрицы<br>
        G   = matrices[&quot;conductance&quot;]              # KCL<br>
        H   = matrices[&quot;electric_holonomic&quot;]       # KVL<br>
        rhs = matrices[&quot;electric_holonomic_rhs&quot;]   # KVL правая часть<br>
        EM = matrices[&quot;electromechanic_coupling&quot;]  # электромеханическая связь<br>
        EM_damping = matrices[&quot;electromechanic_coupling_damping&quot;]  # электромеханическая связь (в демпфирование)<br>
<br>
        b_rhs = matrices[&quot;load&quot;]         # правая часть сил на ускорения<br>
        <br>
        # Индексы<br>
        vmap = index_maps[&quot;voltage&quot;]<br>
        cmap = index_maps[&quot;current&quot;]<br>
        amap = index_maps[&quot;acceleration&quot;]<br>
<br>
        v1 = vmap[self.node1][0]<br>
        v2 = vmap[self.node2][0]<br>
        i  = cmap[self.i][0]<br>
        angaccel  = amap[self.connected_body.acceleration_var][2]<br>
        #tau_idx = mmap[self.torque][0]<br>
<br>
        # ---------------------------------------------------------<br>
        # 1) Электрическое уравнение двигателя (KVL):<br>
        #       V1 - V2 = k_e * omega<br>
        #<br>
        # В матричной форме:<br>
        #       H[row, v1] +=  1<br>
        #       H[row, v2] += -1<br>
        #       H[row, w ] += -k_e<br>
        #       rhs[row] +=  0<br>
        # ---------------------------------------------------------<br>
        H[i, v1] +=  1.0<br>
        H[i, v2] += -1.0<br>
        EM_damping[angaccel, i] += self.k_e # Тут должна быть угловая скорость<br>
<br>
        # ---------------------------------------------------------<br>
        # 2) KCL: ток через двигатель<br>
        # ток входит в node1, выходит из node2<br>
        # ---------------------------------------------------------<br>
        # G[v1, i] +=  1.0<br>
        # G[i, v1] +=  1.0<br>
<br>
        # G[v2, i] += -1.0<br>
        # G[i, v2] += -1.0<br>
        EM[angaccel, i] += -self.k_t<br>
<br>
        # ---------------------------------------------------------<br>
        # 3) Механика: момент двигателя<br>
        #       tau_motor = k_t * i<br>
        # Просто добавляем момент в мех. RHS<br>
        # ---------------------------------------------------------<br>
        # b_rhs[w] += (self.k_t * self.i.get_current()).item()<br>
<br>
    def contribute_for_constraints_correction(self, matrices, index_maps):<br>
        # та же логика (как у источника напряжения и индуктивности)<br>
        self.contribute(matrices, index_maps)<br>
<!-- END SCAT CODE -->
</body>
</html>
