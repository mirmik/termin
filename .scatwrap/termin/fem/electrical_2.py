<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/fem/electrical_2.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
import&nbsp;numpy&nbsp;as&nbsp;np<br>
from&nbsp;typing&nbsp;import&nbsp;List,&nbsp;Dict<br>
from&nbsp;.assembler&nbsp;import&nbsp;Contribution,&nbsp;Variable,&nbsp;Constraint&nbsp;&nbsp;&nbsp;<br>
<br>
<br>
class&nbsp;ElectricalContribution(Contribution):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;Базовый&nbsp;класс&nbsp;для&nbsp;электрических&nbsp;элементов.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(self,&nbsp;variables:&nbsp;List[Variable],&nbsp;assembler=None):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;super().__init__(variables,&nbsp;domain=&quot;electric&quot;,&nbsp;assembler=assembler)<br>
<br>
class&nbsp;ElectricalNode(Variable):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;Узел&nbsp;электрической&nbsp;цепи&nbsp;с&nbsp;потенциалом&nbsp;(напряжением).<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(self,&nbsp;name:&nbsp;str,&nbsp;size:&nbsp;int=1,&nbsp;tag:&nbsp;str=&quot;voltage&quot;):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;super().__init__(name,&nbsp;size,&nbsp;tag)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;get_voltage(self)&nbsp;-&gt;&nbsp;np.ndarray:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Получить&nbsp;текущее&nbsp;значение&nbsp;потенциала&nbsp;узла.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;self.value<br>
<br>
class&nbsp;CurrentVariable(Variable):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;Переменная&nbsp;тока&nbsp;в&nbsp;электрической&nbsp;цепи.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(self,&nbsp;name:&nbsp;str,&nbsp;size:&nbsp;int=1,&nbsp;tag:&nbsp;str=&quot;current&quot;):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;super().__init__(name,&nbsp;size,&nbsp;tag)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;get_current(self)&nbsp;-&gt;&nbsp;np.ndarray:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Получить&nbsp;текущее&nbsp;значение&nbsp;тока.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;self.value<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;set_current(self,&nbsp;current:&nbsp;np.ndarray):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Установить&nbsp;значение&nbsp;тока.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.set_value_by_rank(current,&nbsp;rank=0)<br>
<br>
class&nbsp;Resistor(ElectricalContribution):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;Резистор&nbsp;-&nbsp;линейный&nbsp;элемент.<br>
&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;Закон&nbsp;Ома:&nbsp;U&nbsp;=&nbsp;I&nbsp;*&nbsp;R,&nbsp;или&nbsp;I&nbsp;=&nbsp;(V1&nbsp;-&nbsp;V2)&nbsp;/&nbsp;R&nbsp;=&nbsp;(V1&nbsp;-&nbsp;V2)&nbsp;*&nbsp;G<br>
&nbsp;&nbsp;&nbsp;&nbsp;где&nbsp;G&nbsp;=&nbsp;1/R&nbsp;-&nbsp;проводимость<br>
&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;Матрица&nbsp;проводимости&nbsp;(аналог&nbsp;матрицы&nbsp;жесткости):<br>
&nbsp;&nbsp;&nbsp;&nbsp;G_matrix&nbsp;=&nbsp;G&nbsp;*&nbsp;[[&nbsp;1,&nbsp;-1],<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[-1,&nbsp;&nbsp;1]]<br>
&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;Уравнение:&nbsp;[I1]&nbsp;&nbsp;&nbsp;=&nbsp;G&nbsp;*&nbsp;[[&nbsp;1,&nbsp;-1]]&nbsp;*&nbsp;[V1]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[I2]&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[[-1,&nbsp;&nbsp;1]]&nbsp;&nbsp;&nbsp;[V2]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(self,&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;node1:&nbsp;Variable,&nbsp;&nbsp;#&nbsp;потенциал&nbsp;узла&nbsp;1<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;node2:&nbsp;Variable,&nbsp;&nbsp;#&nbsp;потенциал&nbsp;узла&nbsp;2<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;R:&nbsp;float,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;сопротивление&nbsp;[Ом]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=None):&nbsp;&nbsp;#&nbsp;ассемблер&nbsp;для&nbsp;автоматической&nbsp;регистрации<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Args:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;node1:&nbsp;Переменная&nbsp;потенциала&nbsp;первого&nbsp;узла&nbsp;(скаляр)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;node2:&nbsp;Переменная&nbsp;потенциала&nbsp;второго&nbsp;узла&nbsp;(скаляр)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;R:&nbsp;Сопротивление&nbsp;[Ом]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler:&nbsp;MatrixAssembler&nbsp;для&nbsp;автоматической&nbsp;регистрации&nbsp;переменных<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;node1.tag&nbsp;!=&nbsp;&quot;voltage&quot;&nbsp;or&nbsp;node2.tag&nbsp;!=&nbsp;&quot;voltage&quot;:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;raise&nbsp;ValueError(&quot;Узлы&nbsp;резистора&nbsp;должны&nbsp;иметь&nbsp;тег&nbsp;'voltage'&quot;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;node1.size&nbsp;!=&nbsp;1&nbsp;or&nbsp;node2.size&nbsp;!=&nbsp;1:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;raise&nbsp;ValueError(&quot;Узлы&nbsp;должны&nbsp;быть&nbsp;скалярами&nbsp;(потенциалы)&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;R&nbsp;&lt;=&nbsp;0:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;raise&nbsp;ValueError(&quot;Сопротивление&nbsp;должно&nbsp;быть&nbsp;положительным&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;super().__init__([node1,&nbsp;node2],&nbsp;assembler)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.node1&nbsp;=&nbsp;node1<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.node2&nbsp;=&nbsp;node2<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.R&nbsp;=&nbsp;R<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.G&nbsp;=&nbsp;1.0&nbsp;/&nbsp;R&nbsp;&nbsp;#&nbsp;проводимость<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.G_matrix&nbsp;=&nbsp;np.array([<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[&nbsp;1,&nbsp;-1],<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[-1,&nbsp;&nbsp;1]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;])&nbsp;*&nbsp;self.G<br>
&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute(self,&nbsp;matrices,&nbsp;index_maps:&nbsp;Dict[Variable,&nbsp;List[int]]):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Добавляет&nbsp;вклад&nbsp;резистора&nbsp;в&nbsp;матрицу&nbsp;проводимости<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;G&nbsp;=&nbsp;matrices[&quot;conductance&quot;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;index_map&nbsp;=&nbsp;index_maps[&quot;voltage&quot;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;idx1&nbsp;=&nbsp;index_map[self.node1][0]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;idx2&nbsp;=&nbsp;index_map[self.node2][0]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;global_indices&nbsp;=&nbsp;[idx1,&nbsp;idx2]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;for&nbsp;i,&nbsp;gi&nbsp;in&nbsp;enumerate(global_indices):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;for&nbsp;j,&nbsp;gj&nbsp;in&nbsp;enumerate(global_indices):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;G[gi,&nbsp;gj]&nbsp;+=&nbsp;self.G_matrix[i,&nbsp;j]<br>
<br>
<br>
class&nbsp;VoltageSource(ElectricalContribution):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;Идеальный&nbsp;источник&nbsp;напряжения:&nbsp;V1&nbsp;-&nbsp;V2&nbsp;=&nbsp;U<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(self,&nbsp;node1,&nbsp;node2,&nbsp;U,&nbsp;assembler=None):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.node1&nbsp;=&nbsp;node1<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.node2&nbsp;=&nbsp;node2<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.U&nbsp;=&nbsp;float(U)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;вводим&nbsp;ток&nbsp;как&nbsp;лагранжевый&nbsp;множитель<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.i&nbsp;=&nbsp;Variable(&quot;i_vs&quot;,&nbsp;size=1,&nbsp;tag=&quot;current&quot;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;super().__init__([node1,&nbsp;node2,&nbsp;self.i],&nbsp;assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute(self,&nbsp;matrices,&nbsp;index_maps):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H&nbsp;=&nbsp;matrices[&quot;electric_holonomic&quot;]&nbsp;&nbsp;&nbsp;#&nbsp;матрица&nbsp;ограничений<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;rhs&nbsp;=&nbsp;matrices[&quot;electric_holonomic_rhs&quot;]<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;vmap&nbsp;=&nbsp;index_maps[&quot;voltage&quot;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;cmap&nbsp;=&nbsp;index_maps[&quot;current&quot;]<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;row&nbsp;=&nbsp;cmap[self.i][0]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v1&nbsp;=&nbsp;vmap[self.node1][0]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v2&nbsp;=&nbsp;vmap[self.node2][0]<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;V1&nbsp;-&nbsp;V2&nbsp;=&nbsp;U<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H[row,&nbsp;v1]&nbsp;+=&nbsp;-1.0<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H[row,&nbsp;v2]&nbsp;+=&nbsp;1.0<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;rhs[row]&nbsp;+=&nbsp;-self.U<br>
<br>
<br>
class&nbsp;Ground(ElectricalContribution):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;Электрическая&nbsp;земля&nbsp;—&nbsp;фиксирует&nbsp;потенциал&nbsp;узла:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;V_node&nbsp;=&nbsp;0<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;Делается&nbsp;через&nbsp;голономное&nbsp;ограничение.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(self,&nbsp;node:&nbsp;Variable,&nbsp;assembler=None):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Args:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;node:&nbsp;Variable&nbsp;—&nbsp;потенциал&nbsp;узла&nbsp;(скаляр)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;node.size&nbsp;!=&nbsp;1:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;raise&nbsp;ValueError(&quot;Ground&nbsp;может&nbsp;быть&nbsp;подключён&nbsp;только&nbsp;к&nbsp;скалярному&nbsp;потенциалу&nbsp;узла&quot;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.node&nbsp;=&nbsp;node<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Множитель&nbsp;Лагранжа&nbsp;на&nbsp;1&nbsp;ограничение<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.lmbd&nbsp;=&nbsp;Variable(&quot;lambda_ground&quot;,&nbsp;size=1,&nbsp;tag=&quot;current&quot;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Регистрируем&nbsp;node&nbsp;(но&nbsp;он&nbsp;уже&nbsp;зарегистрирован&nbsp;в&nbsp;схеме)&nbsp;и&nbsp;lambda<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;super().__init__([self.node,&nbsp;self.lmbd],&nbsp;assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute(self,&nbsp;matrices,&nbsp;index_maps):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Добавить&nbsp;вклад&nbsp;в&nbsp;матрицы&nbsp;ускорений&nbsp;(точнее:&nbsp;в&nbsp;систему&nbsp;ограничений)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H&nbsp;=&nbsp;matrices[&quot;electric_holonomic&quot;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;rhs&nbsp;=&nbsp;matrices[&quot;electric_holonomic_rhs&quot;]<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;индексы<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;cmap&nbsp;=&nbsp;index_maps[&quot;current&quot;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;vmap&nbsp;=&nbsp;index_maps[&quot;voltage&quot;]&nbsp;&nbsp;#&nbsp;узлы&nbsp;—&nbsp;это&nbsp;группа&nbsp;voltage<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;row&nbsp;=&nbsp;cmap[self.lmbd][0]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;col&nbsp;=&nbsp;vmap[self.node][0]<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Ограничение:&nbsp;V_node&nbsp;=&nbsp;0<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H[row,&nbsp;col]&nbsp;+=&nbsp;1.0<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;rhs&nbsp;=&nbsp;0<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;rhs[row]&nbsp;+=&nbsp;0.0<br>
&nbsp;&nbsp;&nbsp;&nbsp;<br>
<br>
class&nbsp;Capacitor(ElectricalContribution):<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(self,&nbsp;node1,&nbsp;node2,&nbsp;C,&nbsp;assembler=None):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;super().__init__([node1,&nbsp;node2],&nbsp;assembler)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.node1&nbsp;=&nbsp;node1<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.node2&nbsp;=&nbsp;node2<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.C&nbsp;=&nbsp;float(C)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;состояние&nbsp;на&nbsp;шаге&nbsp;n-1<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.v_prev&nbsp;=&nbsp;0.0&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;v_{n-1}<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.i_prev&nbsp;=&nbsp;0.0&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;i_{n-1}<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute(self,&nbsp;matrices,&nbsp;index_maps):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;dt&nbsp;=&nbsp;self.assembler.time_step<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Geq&nbsp;=&nbsp;2.0&nbsp;*&nbsp;self.C&nbsp;/&nbsp;dt<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Ieq&nbsp;=&nbsp;Geq&nbsp;*&nbsp;self.v_prev&nbsp;+&nbsp;self.i_prev&nbsp;<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;G&nbsp;=&nbsp;matrices[&quot;conductance&quot;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;I&nbsp;=&nbsp;matrices[&quot;rhs&quot;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;vmap&nbsp;=&nbsp;index_maps[&quot;voltage&quot;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;n1&nbsp;=&nbsp;vmap[self.node1][0]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;n2&nbsp;=&nbsp;vmap[self.node2][0]<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;эквивалентная&nbsp;проводимость&nbsp;(как&nbsp;резистор)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;G[n1,&nbsp;n1]&nbsp;+=&nbsp;Geq<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;G[n1,&nbsp;n2]&nbsp;-=&nbsp;Geq<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;G[n2,&nbsp;n1]&nbsp;-=&nbsp;Geq<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;G[n2,&nbsp;n2]&nbsp;+=&nbsp;Geq<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;эквивалентный&nbsp;источнику&nbsp;ток<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;I[n1]&nbsp;+=&nbsp;Ieq<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;I[n2]&nbsp;-=&nbsp;Ieq<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;finish_timestep(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;вызывать&nbsp;ПОСЛЕ&nbsp;solver'а&nbsp;и&nbsp;set_solution<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;dt&nbsp;=&nbsp;self.assembler.time_step<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v_now&nbsp;=&nbsp;(self.node1.get_voltage()&nbsp;-&nbsp;self.node2.get_voltage()).item()&nbsp;&nbsp;#&nbsp;v_n<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;сначала&nbsp;считаем&nbsp;i_n&nbsp;из&nbsp;v_n&nbsp;и&nbsp;v_{n-1}<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;i_now&nbsp;=&nbsp;self.C&nbsp;*&nbsp;(v_now&nbsp;-&nbsp;self.v_prev)&nbsp;/&nbsp;dt<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;затем&nbsp;передвигаем&nbsp;«историю»:&nbsp;(n&nbsp;←&nbsp;n-1)&nbsp;для&nbsp;следующего&nbsp;шага<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.v_prev&nbsp;=&nbsp;v_now<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.i_prev&nbsp;=&nbsp;i_now<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;voltage_difference(self)&nbsp;-&gt;&nbsp;np.ndarray:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Разность&nbsp;потенциалов&nbsp;на&nbsp;конденсаторе:&nbsp;V_node1&nbsp;-&nbsp;V_node2<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;self.node1.get_voltage()&nbsp;-&nbsp;self.node2.get_voltage()<br>
<br>
<br>
class&nbsp;Inductor(ElectricalContribution):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;Идеальная&nbsp;индуктивность&nbsp;(TRAP):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v&nbsp;=&nbsp;L&nbsp;di/dt<br>
&nbsp;&nbsp;&nbsp;&nbsp;TRAP&nbsp;даёт:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v_n&nbsp;=&nbsp;R_eq&nbsp;*&nbsp;i_n&nbsp;+&nbsp;V_eq<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;где:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;R_eq&nbsp;=&nbsp;2L&nbsp;/&nbsp;dt<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;V_eq&nbsp;=&nbsp;-R_eq&nbsp;*&nbsp;i_prev&nbsp;-&nbsp;v_prev<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(self,&nbsp;node1,&nbsp;node2,&nbsp;L,&nbsp;assembler=None):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.node1&nbsp;=&nbsp;node1<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.node2&nbsp;=&nbsp;node2<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.L&nbsp;=&nbsp;float(L)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;переменная&nbsp;тока&nbsp;через&nbsp;индуктивность<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.i_var&nbsp;=&nbsp;CurrentVariable(&quot;i_L&quot;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;super().__init__([node1,&nbsp;node2,&nbsp;self.i_var],&nbsp;assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;состояние&nbsp;TRAP<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.i_prev&nbsp;=&nbsp;0.0&nbsp;&nbsp;#&nbsp;ток&nbsp;в&nbsp;момент&nbsp;времени&nbsp;n-1<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.v_prev&nbsp;=&nbsp;0.0&nbsp;&nbsp;#&nbsp;напряжение&nbsp;в&nbsp;момент&nbsp;времени&nbsp;n-1&nbsp;(v1&nbsp;-&nbsp;v2)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute(self,&nbsp;matrices,&nbsp;index_maps):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;dt&nbsp;=&nbsp;self.assembler.time_step<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;R_eq&nbsp;=&nbsp;2.0&nbsp;*&nbsp;self.L&nbsp;/&nbsp;dt<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;эквивалентный&nbsp;источник&nbsp;TRAP<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Veq&nbsp;=&nbsp;-R_eq&nbsp;*&nbsp;self.i_prev&nbsp;-&nbsp;self.v_prev<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H&nbsp;=&nbsp;matrices[&quot;electric_holonomic&quot;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;C&nbsp;=&nbsp;matrices[&quot;current_to_current&quot;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;rhs&nbsp;=&nbsp;matrices[&quot;electric_holonomic_rhs&quot;]<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;vmap&nbsp;=&nbsp;index_maps[&quot;voltage&quot;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;cmap&nbsp;=&nbsp;index_maps[&quot;current&quot;]<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v1&nbsp;=&nbsp;vmap[self.node1][0]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v2&nbsp;=&nbsp;vmap[self.node2][0]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;irow&nbsp;=&nbsp;cmap[self.i_var][0]<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;KVL:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;&nbsp;&nbsp;v1&nbsp;-&nbsp;v2&nbsp;-&nbsp;R_eq&nbsp;*&nbsp;i&nbsp;=&nbsp;Veq<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H[irow,&nbsp;v1]&nbsp;+=&nbsp;&nbsp;1.0<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H[irow,&nbsp;v2]&nbsp;+=&nbsp;-1.0<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;C[irow,&nbsp;irow]&nbsp;+=&nbsp;-R_eq<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;rhs[irow]&nbsp;+=&nbsp;Veq<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;finish_timestep(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;новое&nbsp;напряжение<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v_now&nbsp;=&nbsp;(self.node1.get_voltage()&nbsp;-&nbsp;self.node2.get_voltage()).item()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;новое&nbsp;решение&nbsp;тока<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;i_now&nbsp;=&nbsp;self.i_var.get_current().item()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;обновление&nbsp;состояния<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.i_prev&nbsp;=&nbsp;i_now<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.v_prev&nbsp;=&nbsp;v_now<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;current(self)&nbsp;-&gt;&nbsp;np.ndarray:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Ток&nbsp;через&nbsp;индуктивность<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;self.i_var.get_current()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
<br>
class&nbsp;CurrentSource(ElectricalContribution):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;Идеальный&nbsp;источник&nbsp;тока:&nbsp;+I&nbsp;в&nbsp;node1,&nbsp;-I&nbsp;в&nbsp;node2<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(self,&nbsp;node1,&nbsp;node2,&nbsp;I,&nbsp;assembler=None):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.node1&nbsp;=&nbsp;node1<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.node2&nbsp;=&nbsp;node2<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.I&nbsp;=&nbsp;float(I)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;super().__init__([node1,&nbsp;node2],&nbsp;assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute(self,&nbsp;matrices,&nbsp;index_maps):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;b&nbsp;=&nbsp;matrices[&quot;rhs&quot;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;vmap&nbsp;=&nbsp;index_maps[&quot;voltage&quot;]<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;i1&nbsp;=&nbsp;vmap[self.node1][0]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;i2&nbsp;=&nbsp;vmap[self.node2][0]<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;b[i1]&nbsp;+=&nbsp;&nbsp;self.I<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;b[i2]&nbsp;+=&nbsp;-self.I<br>
<!-- END SCAT CODE -->
</body>
</html>
