<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/fem/electromechanic_2.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
<br>
from&nbsp;termin.fem.assembler&nbsp;import&nbsp;Contribution,&nbsp;Variable<br>
from&nbsp;termin.fem.electrical_2&nbsp;import&nbsp;ElectricalNode,&nbsp;CurrentVariable<br>
<br>
class&nbsp;DCMotor(Contribution):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;Идеальный&nbsp;электродвигатель&nbsp;постоянного&nbsp;тока:<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Электрическая&nbsp;сторона:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;V1&nbsp;-&nbsp;V2&nbsp;=&nbsp;k_e&nbsp;*&nbsp;omega<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Механическая&nbsp;сторона:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;torque&nbsp;=&nbsp;k_t&nbsp;*&nbsp;i_motor<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Где:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;i_motor&nbsp;—&nbsp;ток,&nbsp;протекающий&nbsp;через&nbsp;двигатель<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;omega&nbsp;&nbsp;&nbsp;—&nbsp;угловая&nbsp;скорость&nbsp;в&nbsp;механическом&nbsp;домене<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(self,&nbsp;node1,&nbsp;node2,&nbsp;connected_body,&nbsp;k_e=0.1,&nbsp;k_t=0.1,&nbsp;assembler=None):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Args:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;node1,&nbsp;node2:&nbsp;&nbsp;&nbsp;электрические&nbsp;узлы<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;omega_var:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Variable(omega)&nbsp;—&nbsp;угловая&nbsp;скорость<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;k_e:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;коэффициент&nbsp;обратной&nbsp;ЭДС&nbsp;(вольт&nbsp;на&nbsp;рад/с)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;k_t:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;коэффициент&nbsp;момента&nbsp;(ньютон-метр&nbsp;на&nbsp;ампер)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.node1&nbsp;=&nbsp;node1<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.node2&nbsp;=&nbsp;node2<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.connected_body&nbsp;=&nbsp;connected_body<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.k_e&nbsp;=&nbsp;float(k_e)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.k_t&nbsp;=&nbsp;float(k_t)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;ток&nbsp;двигателя&nbsp;—&nbsp;как&nbsp;у&nbsp;источников/индуктора<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.i&nbsp;=&nbsp;CurrentVariable(&quot;i_motor&quot;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;super().__init__([node1,&nbsp;node2,&nbsp;self.i,&nbsp;self.connected_body.acceleration_var],&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;domain=&quot;electromechanical&quot;,&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute(self,&nbsp;matrices,&nbsp;index_maps):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Вкладывает&nbsp;уравнения&nbsp;в&nbsp;матрицы&nbsp;электрического&nbsp;и&nbsp;механического&nbsp;доменов.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Матрицы<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;G&nbsp;&nbsp;&nbsp;=&nbsp;matrices[&quot;conductance&quot;]&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;KCL<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H&nbsp;&nbsp;&nbsp;=&nbsp;matrices[&quot;electric_holonomic&quot;]&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;KVL<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;rhs&nbsp;=&nbsp;matrices[&quot;electric_holonomic_rhs&quot;]&nbsp;&nbsp;&nbsp;#&nbsp;KVL&nbsp;правая&nbsp;часть<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;EM&nbsp;=&nbsp;matrices[&quot;electromechanic_coupling&quot;]&nbsp;&nbsp;#&nbsp;электромеханическая&nbsp;связь<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;EM_damping&nbsp;=&nbsp;matrices[&quot;electromechanic_coupling_damping&quot;]&nbsp;&nbsp;#&nbsp;электромеханическая&nbsp;связь&nbsp;(в&nbsp;демпфирование)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;b_rhs&nbsp;=&nbsp;matrices[&quot;load&quot;]&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;правая&nbsp;часть&nbsp;сил&nbsp;на&nbsp;ускорения<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Индексы<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;vmap&nbsp;=&nbsp;index_maps[&quot;voltage&quot;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;cmap&nbsp;=&nbsp;index_maps[&quot;current&quot;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;amap&nbsp;=&nbsp;index_maps[&quot;acceleration&quot;]<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v1&nbsp;=&nbsp;vmap[self.node1][0]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v2&nbsp;=&nbsp;vmap[self.node2][0]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;i&nbsp;&nbsp;=&nbsp;cmap[self.i][0]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;angaccel&nbsp;&nbsp;=&nbsp;amap[self.connected_body.acceleration_var][2]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#tau_idx&nbsp;=&nbsp;mmap[self.torque][0]<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;---------------------------------------------------------<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;1)&nbsp;Электрическое&nbsp;уравнение&nbsp;двигателя&nbsp;(KVL):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;V1&nbsp;-&nbsp;V2&nbsp;=&nbsp;k_e&nbsp;*&nbsp;omega<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;В&nbsp;матричной&nbsp;форме:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H[row,&nbsp;v1]&nbsp;+=&nbsp;&nbsp;1<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H[row,&nbsp;v2]&nbsp;+=&nbsp;-1<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H[row,&nbsp;w&nbsp;]&nbsp;+=&nbsp;-k_e<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;rhs[row]&nbsp;+=&nbsp;&nbsp;0<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;---------------------------------------------------------<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H[i,&nbsp;v1]&nbsp;+=&nbsp;&nbsp;1.0<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H[i,&nbsp;v2]&nbsp;+=&nbsp;-1.0<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;EM_damping[angaccel,&nbsp;i]&nbsp;+=&nbsp;self.k_e&nbsp;#&nbsp;Тут&nbsp;должна&nbsp;быть&nbsp;угловая&nbsp;скорость<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;---------------------------------------------------------<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;2)&nbsp;KCL:&nbsp;ток&nbsp;через&nbsp;двигатель<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;ток&nbsp;входит&nbsp;в&nbsp;node1,&nbsp;выходит&nbsp;из&nbsp;node2<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;---------------------------------------------------------<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;G[v1,&nbsp;i]&nbsp;+=&nbsp;&nbsp;1.0<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;G[i,&nbsp;v1]&nbsp;+=&nbsp;&nbsp;1.0<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;G[v2,&nbsp;i]&nbsp;+=&nbsp;-1.0<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;G[i,&nbsp;v2]&nbsp;+=&nbsp;-1.0<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;EM[angaccel,&nbsp;i]&nbsp;+=&nbsp;-self.k_t<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;---------------------------------------------------------<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;3)&nbsp;Механика:&nbsp;момент&nbsp;двигателя<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;tau_motor&nbsp;=&nbsp;k_t&nbsp;*&nbsp;i<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Просто&nbsp;добавляем&nbsp;момент&nbsp;в&nbsp;мех.&nbsp;RHS<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;---------------------------------------------------------<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;b_rhs[w]&nbsp;+=&nbsp;(self.k_t&nbsp;*&nbsp;self.i.get_current()).item()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute_for_constraints_correction(self,&nbsp;matrices,&nbsp;index_maps):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;та&nbsp;же&nbsp;логика&nbsp;(как&nbsp;у&nbsp;источника&nbsp;напряжения&nbsp;и&nbsp;индуктивности)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.contribute(matrices,&nbsp;index_maps)<br>
<!-- END SCAT CODE -->
</body>
</html>
