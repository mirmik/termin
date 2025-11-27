<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>utest/fem/electric2_test.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
#!/usr/bin/env&nbsp;python3<br>
&quot;&quot;&quot;<br>
Тесты&nbsp;для&nbsp;электрических&nbsp;элементов&nbsp;(fem/electrical.py)<br>
&quot;&quot;&quot;<br>
<br>
import&nbsp;unittest<br>
import&nbsp;numpy&nbsp;as&nbsp;np<br>
import&nbsp;sys<br>
import&nbsp;os<br>
import&nbsp;math<br>
<br>
<br>
#&nbsp;Добавить&nbsp;путь&nbsp;к&nbsp;модулю<br>
sys.path.insert(0,&nbsp;os.path.join(os.path.dirname(__file__),&nbsp;'..'))<br>
<br>
from&nbsp;termin.fem.electrical_2&nbsp;import&nbsp;(<br>
&nbsp;&nbsp;&nbsp;&nbsp;Resistor,&nbsp;Capacitor,&nbsp;Inductor,&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;VoltageSource,&nbsp;CurrentSource,&nbsp;Ground,&nbsp;ElectricalNode<br>
)<br>
from&nbsp;termin.fem.assembler&nbsp;import&nbsp;Variable,&nbsp;MatrixAssembler<br>
from&nbsp;termin.fem.dynamic_assembler&nbsp;import&nbsp;DynamicMatrixAssembler<br>
<br>
<br>
class&nbsp;TestResistor(unittest.TestCase):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Тесты&nbsp;для&nbsp;резистора&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;test_resistor(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Создание&nbsp;резистора&quot;&quot;&quot;<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v1&nbsp;=&nbsp;ElectricalNode(&quot;V1&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v2&nbsp;=&nbsp;ElectricalNode(&quot;V2&quot;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v1.value&nbsp;=&nbsp;np.array([11.0])<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v2.value&nbsp;=&nbsp;np.array([15.0])<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler&nbsp;=&nbsp;DynamicMatrixAssembler()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;vs&nbsp;=&nbsp;VoltageSource(v1,&nbsp;v2,&nbsp;5.0,&nbsp;assembler)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;r&nbsp;=&nbsp;Resistor(v1,&nbsp;v2,&nbsp;10.0,&nbsp;assembler)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;ground&nbsp;=&nbsp;Ground(v2,&nbsp;assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;index_maps&nbsp;=&nbsp;{<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;voltage&quot;:&nbsp;assembler.index_map_by_tag(&quot;voltage&quot;),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;current&quot;:&nbsp;assembler.index_map_by_tag(&quot;current&quot;),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;}<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(index_maps)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;v1&nbsp;in&nbsp;index_maps[&quot;voltage&quot;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;v2&nbsp;in&nbsp;index_maps[&quot;voltage&quot;]<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;matrices&nbsp;=&nbsp;assembler.assemble_electric_domain()&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;A_ext,&nbsp;b_ext,&nbsp;variables&nbsp;=&nbsp;assembler.assemble_extended_system_for_electric(matrices)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;A_ext:\n&quot;,&nbsp;A_ext)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;b_ext:\n&quot;,&nbsp;b_ext)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;variables:\n&quot;,&nbsp;variables)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;x&nbsp;=&nbsp;np.linalg.solve(A_ext,&nbsp;b_ext)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;result:\n&quot;,&nbsp;x)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[0],&nbsp;5.0)&nbsp;&nbsp;#&nbsp;V1<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[1],&nbsp;0.0)&nbsp;&nbsp;#&nbsp;V2<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[2],&nbsp;0.5)&nbsp;&nbsp;#&nbsp;I_vs<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[3],&nbsp;0.0)&nbsp;&nbsp;#&nbsp;Ground&nbsp;current<br>
<br>
<br>
class&nbsp;TestCapacitor(unittest.TestCase):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Тесты&nbsp;для&nbsp;конденсатора&quot;&quot;&quot;<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;test_capacitor(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v0&nbsp;=&nbsp;ElectricalNode(&quot;V0&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v1&nbsp;=&nbsp;ElectricalNode(&quot;V1&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v2&nbsp;=&nbsp;ElectricalNode(&quot;V2&quot;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler&nbsp;=&nbsp;DynamicMatrixAssembler()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;vs&nbsp;=&nbsp;VoltageSource(v1,&nbsp;v0,&nbsp;5.0,&nbsp;assembler)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;r&nbsp;=&nbsp;Resistor(v1,&nbsp;v2,&nbsp;10.0,&nbsp;assembler)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;c&nbsp;=&nbsp;Capacitor(v2,&nbsp;v0,&nbsp;0.1,&nbsp;assembler)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;ground&nbsp;=&nbsp;Ground(v0,&nbsp;assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;index_maps&nbsp;=&nbsp;{<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;voltage&quot;:&nbsp;assembler.index_map_by_tag(&quot;voltage&quot;),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;current&quot;:&nbsp;assembler.index_map_by_tag(&quot;current&quot;),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;charge&quot;:&nbsp;assembler.index_map_by_tag(&quot;charge&quot;),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;}<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(index_maps)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;v1&nbsp;in&nbsp;index_maps[&quot;voltage&quot;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;v2&nbsp;in&nbsp;index_maps[&quot;voltage&quot;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;v0&nbsp;in&nbsp;index_maps[&quot;voltage&quot;]<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;matrices&nbsp;=&nbsp;assembler.assemble_electric_domain()&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;A_ext,&nbsp;b_ext,&nbsp;variables&nbsp;=&nbsp;assembler.assemble_extended_system_for_electric(matrices)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;A_ext:\n&quot;,&nbsp;A_ext)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;b_ext:\n&quot;,&nbsp;b_ext)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;variables:\n&quot;,&nbsp;variables)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;dt:&quot;,&nbsp;assembler.time_step)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;Equations:&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;equations&nbsp;=&nbsp;assembler.system_to_human_readable(A_ext,&nbsp;b_ext,&nbsp;variables)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(equations)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;x&nbsp;=&nbsp;np.linalg.solve(A_ext,&nbsp;b_ext)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;result:\n&quot;,&nbsp;x)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[0],&nbsp;5.0)&nbsp;&nbsp;#&nbsp;V1<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[1],&nbsp;0.0)&nbsp;&nbsp;#&nbsp;V2<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[3],&nbsp;0.5,&nbsp;atol=0.1)&nbsp;&nbsp;#&nbsp;I_vs<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;test_capacitor_graph(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v0&nbsp;=&nbsp;ElectricalNode(&quot;V0&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v1&nbsp;=&nbsp;ElectricalNode(&quot;V1&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v2&nbsp;=&nbsp;ElectricalNode(&quot;V2&quot;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler&nbsp;=&nbsp;DynamicMatrixAssembler()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;vs&nbsp;=&nbsp;VoltageSource(v1,&nbsp;v0,&nbsp;5.0,&nbsp;assembler)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;r&nbsp;=&nbsp;Resistor(v1,&nbsp;v2,&nbsp;10.0,&nbsp;assembler)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;c&nbsp;=&nbsp;Capacitor(v2,&nbsp;v0,&nbsp;0.1,&nbsp;assembler)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;ground&nbsp;=&nbsp;Ground(v0,&nbsp;assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler.time_step&nbsp;=&nbsp;0.01<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;index_maps&nbsp;=&nbsp;{<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;voltage&quot;:&nbsp;assembler.index_map_by_tag(&quot;voltage&quot;),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;current&quot;:&nbsp;assembler.index_map_by_tag(&quot;current&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;}<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;for&nbsp;i&nbsp;in&nbsp;range(50):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;matrices&nbsp;=&nbsp;assembler.assemble_electric_domain()&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;A_ext,&nbsp;b_ext,&nbsp;variables&nbsp;=&nbsp;assembler.assemble_extended_system_for_electric(matrices)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;x&nbsp;=&nbsp;np.linalg.solve(A_ext,&nbsp;b_ext)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler.upload_solution(variables,&nbsp;x)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;real&nbsp;=&nbsp;c.voltage_difference()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;t&nbsp;=&nbsp;(i)&nbsp;*&nbsp;assembler.time_step<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(f&quot;Time:&nbsp;{t:.3f}&nbsp;s&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;expected&nbsp;=&nbsp;5.0&nbsp;*&nbsp;(1.0&nbsp;-&nbsp;math.exp(-t))<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(f&quot;&nbsp;&nbsp;Capacitor&nbsp;voltage:&nbsp;{real.item():.4f}&nbsp;V,&nbsp;expected:&nbsp;{expected:.4f}&nbsp;V&quot;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;c.finish_timestep()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(real,&nbsp;expected,&nbsp;atol=0.1)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
<br>
class&nbsp;TestInductor(unittest.TestCase):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Тесты&nbsp;для&nbsp;индуктора&quot;&quot;&quot;<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;test_inductor(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v0&nbsp;=&nbsp;ElectricalNode(&quot;V0&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v1&nbsp;=&nbsp;ElectricalNode(&quot;V1&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v2&nbsp;=&nbsp;ElectricalNode(&quot;V2&quot;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler&nbsp;=&nbsp;DynamicMatrixAssembler()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;vs&nbsp;=&nbsp;VoltageSource(v1,&nbsp;v0,&nbsp;10.0,&nbsp;assembler)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;l&nbsp;=&nbsp;Inductor(v1,&nbsp;v2,&nbsp;0.5,&nbsp;assembler)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;r&nbsp;=&nbsp;Resistor(v2,&nbsp;v0,&nbsp;100.0,&nbsp;assembler)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;ground&nbsp;=&nbsp;Ground(v0,&nbsp;assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;index_maps&nbsp;=&nbsp;{<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;voltage&quot;:&nbsp;assembler.index_map_by_tag(&quot;voltage&quot;),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;current&quot;:&nbsp;assembler.index_map_by_tag(&quot;current&quot;),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;}<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;v1&nbsp;in&nbsp;index_maps[&quot;voltage&quot;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;v0&nbsp;in&nbsp;index_maps[&quot;voltage&quot;]<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;matrices&nbsp;=&nbsp;assembler.assemble_electric_domain()&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;A_ext,&nbsp;b_ext,&nbsp;variables&nbsp;=&nbsp;assembler.assemble_extended_system_for_electric(matrices)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;A_ext:\n&quot;,&nbsp;A_ext)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;b_ext:\n&quot;,&nbsp;b_ext)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;variables:\n&quot;,&nbsp;variables)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;dt:&quot;,&nbsp;assembler.time_step)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;Matrix&nbsp;Diagnosis:&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;diagnosis&nbsp;=&nbsp;assembler.matrix_diagnosis(A_ext)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;for&nbsp;key,&nbsp;value&nbsp;in&nbsp;diagnosis.items():<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(f&quot;&nbsp;&nbsp;{key}:&nbsp;{value}&quot;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;Equations:&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;equations&nbsp;=&nbsp;assembler.system_to_human_readable(A_ext,&nbsp;b_ext,&nbsp;variables)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(equations)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;x&nbsp;=&nbsp;np.linalg.solve(A_ext,&nbsp;b_ext)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;result:&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;result_str&nbsp;=&nbsp;assembler.result_to_human_readable(x,&nbsp;variables)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(result_str)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[0],&nbsp;10.0)&nbsp;&nbsp;#&nbsp;V1<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[1],&nbsp;0.0)&nbsp;&nbsp;&nbsp;#&nbsp;V0<br>
<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;test_inductor_graph(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v0&nbsp;=&nbsp;ElectricalNode(&quot;V0&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v1&nbsp;=&nbsp;ElectricalNode(&quot;V1&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v2&nbsp;=&nbsp;ElectricalNode(&quot;V2&quot;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler&nbsp;=&nbsp;DynamicMatrixAssembler()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;vs&nbsp;=&nbsp;VoltageSource(v1,&nbsp;v0,&nbsp;10.0,&nbsp;assembler)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;l&nbsp;=&nbsp;Inductor(v1,&nbsp;v2,&nbsp;10,&nbsp;assembler)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;r&nbsp;=&nbsp;Resistor(v2,&nbsp;v0,&nbsp;100.0,&nbsp;assembler)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;ground&nbsp;=&nbsp;Ground(v0,&nbsp;assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler.time_step&nbsp;=&nbsp;0.01<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;index_maps&nbsp;=&nbsp;{<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;voltage&quot;:&nbsp;assembler.index_map_by_tag(&quot;voltage&quot;),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;current&quot;:&nbsp;assembler.index_map_by_tag(&quot;current&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;}<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;for&nbsp;i&nbsp;in&nbsp;range(50):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;matrices&nbsp;=&nbsp;assembler.assemble_electric_domain()&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;A_ext,&nbsp;b_ext,&nbsp;variables&nbsp;=&nbsp;assembler.assemble_extended_system_for_electric(matrices)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;x&nbsp;=&nbsp;np.linalg.solve(A_ext,&nbsp;b_ext)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler.upload_solution(variables,&nbsp;x)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;real&nbsp;=&nbsp;l.current()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;t&nbsp;=&nbsp;(i)&nbsp;*&nbsp;assembler.time_step<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(f&quot;Time:&nbsp;{t:.3f}&nbsp;s&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;expected&nbsp;=&nbsp;0.1&nbsp;*&nbsp;(1&nbsp;-&nbsp;math.exp(-10&nbsp;*&nbsp;t))<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(f&quot;&nbsp;&nbsp;Inductor&nbsp;current:&nbsp;{real.item():.4f}&nbsp;A,&nbsp;expected:&nbsp;{expected:.4f}&nbsp;A&quot;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;l.finish_timestep()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(real,&nbsp;expected,&nbsp;atol=0.01)<br>
<br>
class&nbsp;TestCurrentSource(unittest.TestCase):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Тесты&nbsp;для&nbsp;источника&nbsp;тока&quot;&quot;&quot;<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;test_current_source(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v0&nbsp;=&nbsp;ElectricalNode(&quot;V0&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v1&nbsp;=&nbsp;ElectricalNode(&quot;V1&quot;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler&nbsp;=&nbsp;DynamicMatrixAssembler()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;cs&nbsp;=&nbsp;CurrentSource(v1,&nbsp;v0,&nbsp;2.0,&nbsp;assembler)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;r&nbsp;=&nbsp;Resistor(v1,&nbsp;v0,&nbsp;5.0,&nbsp;assembler)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;ground&nbsp;=&nbsp;Ground(v0,&nbsp;assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;index_maps&nbsp;=&nbsp;{<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;voltage&quot;:&nbsp;assembler.index_map_by_tag(&quot;voltage&quot;),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;current&quot;:&nbsp;assembler.index_map_by_tag(&quot;current&quot;),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;}<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;v1&nbsp;in&nbsp;index_maps[&quot;voltage&quot;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;v0&nbsp;in&nbsp;index_maps[&quot;voltage&quot;]<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;matrices&nbsp;=&nbsp;assembler.assemble_electric_domain()&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;A_ext,&nbsp;b_ext,&nbsp;variables&nbsp;=&nbsp;assembler.assemble_extended_system_for_electric(matrices)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;A_ext:\n&quot;,&nbsp;A_ext)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;b_ext:\n&quot;,&nbsp;b_ext)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;variables:\n&quot;,&nbsp;variables)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;Matrix&nbsp;Diagnosis:&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;diagnosis&nbsp;=&nbsp;assembler.matrix_diagnosis(A_ext)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;for&nbsp;key,&nbsp;value&nbsp;in&nbsp;diagnosis.items():<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(f&quot;&nbsp;&nbsp;{key}:&nbsp;{value}&quot;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;Equations:&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;equations&nbsp;=&nbsp;assembler.system_to_human_readable(A_ext,&nbsp;b_ext,&nbsp;variables)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(equations)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;x&nbsp;=&nbsp;np.linalg.solve(A_ext,&nbsp;b_ext)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;result:&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;result_str&nbsp;=&nbsp;assembler.result_to_human_readable(x,&nbsp;variables)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(result_str)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[0],&nbsp;10.0)&nbsp;&nbsp;#&nbsp;V1<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[1],&nbsp;0.0)&nbsp;&nbsp;&nbsp;#&nbsp;V0<br>
<!-- END SCAT CODE -->
</body>
</html>
