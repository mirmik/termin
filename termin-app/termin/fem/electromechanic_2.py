
from termin.fem.assembler import Contribution, Variable
from termin.fem.electrical_2 import ElectricalNode, CurrentVariable

class DCMotor(Contribution):
    """
    Идеальный электродвигатель постоянного тока:

        Электрическая сторона:
            V1 - V2 = k_e * omega

        Механическая сторона:
            torque = k_t * i_motor

        Где:
            i_motor — ток, протекающий через двигатель
            omega   — угловая скорость в механическом домене
    """

    def __init__(self, node1, node2, connected_body, k_e=0.1, k_t=0.1, assembler=None):
        """
        Args:
            node1, node2:   электрические узлы
            omega_var:      Variable(omega) — угловая скорость
            k_e:            коэффициент обратной ЭДС (вольт на рад/с)
            k_t:            коэффициент момента (ньютон-метр на ампер)
        """
        self.node1 = node1
        self.node2 = node2
        self.connected_body = connected_body
        self.k_e = float(k_e)
        self.k_t = float(k_t)

        # ток двигателя — как у источников/индуктора
        self.i = CurrentVariable("i_motor")

        super().__init__([node1, node2, self.i, self.connected_body.acceleration_var], 
            domain="electromechanical", 
            assembler=assembler)

    def contribute(self, matrices, index_maps):
        """
        Вкладывает уравнения в матрицы электрического и механического доменов.
        """
        # Матрицы
        G   = matrices["conductance"]              # KCL
        H   = matrices["electric_holonomic"]       # KVL
        rhs = matrices["electric_holonomic_rhs"]   # KVL правая часть
        EM = matrices["electromechanic_coupling"]  # электромеханическая связь
        EM_damping = matrices["electromechanic_coupling_damping"]  # электромеханическая связь (в демпфирование)

        b_rhs = matrices["load"]         # правая часть сил на ускорения
        
        # Индексы
        vmap = index_maps["voltage"]
        cmap = index_maps["current"]
        amap = index_maps["acceleration"]

        v1 = vmap[self.node1][0]
        v2 = vmap[self.node2][0]
        i  = cmap[self.i][0]
        angaccel  = amap[self.connected_body.acceleration_var][2]
        #tau_idx = mmap[self.torque][0]

        # ---------------------------------------------------------
        # 1) Электрическое уравнение двигателя (KVL):
        #       V1 - V2 = k_e * omega
        #
        # В матричной форме:
        #       H[row, v1] +=  1
        #       H[row, v2] += -1
        #       H[row, w ] += -k_e
        #       rhs[row] +=  0
        # ---------------------------------------------------------
        H[i, v1] +=  1.0
        H[i, v2] += -1.0
        EM_damping[angaccel, i] += self.k_e # Тут должна быть угловая скорость

        # ---------------------------------------------------------
        # 2) KCL: ток через двигатель
        # ток входит в node1, выходит из node2
        # ---------------------------------------------------------
        # G[v1, i] +=  1.0
        # G[i, v1] +=  1.0

        # G[v2, i] += -1.0
        # G[i, v2] += -1.0
        EM[angaccel, i] += -self.k_t

        # ---------------------------------------------------------
        # 3) Механика: момент двигателя
        #       tau_motor = k_t * i
        # Просто добавляем момент в мех. RHS
        # ---------------------------------------------------------
        # b_rhs[w] += (self.k_t * self.i.get_current()).item()

    def contribute_for_constraints_correction(self, matrices, index_maps):
        # та же логика (как у источника напряжения и индуктивности)
        self.contribute(matrices, index_maps)