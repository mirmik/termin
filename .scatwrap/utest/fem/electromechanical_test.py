<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>utest/fem/electromechanical_test.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
#!/usr/bin/env&nbsp;python3<br>
&quot;&quot;&quot;<br>
Тесты&nbsp;для&nbsp;электромеханических&nbsp;элементов&nbsp;(fem/electromechanical.py)<br>
<br>
Содержит&nbsp;тесты&nbsp;только&nbsp;для&nbsp;DCMotor&nbsp;-&nbsp;класса,&nbsp;связывающего&nbsp;электрическую<br>
и&nbsp;механическую&nbsp;подсистемы.<br>
&quot;&quot;&quot;<br>
<br>
import&nbsp;unittest<br>
import&nbsp;numpy&nbsp;as&nbsp;np<br>
import&nbsp;sys<br>
import&nbsp;os<br>
<br>
#&nbsp;Добавить&nbsp;путь&nbsp;к&nbsp;модулю<br>
sys.path.insert(0,&nbsp;os.path.join(os.path.dirname(__file__),&nbsp;'..'))<br>
<br>
from&nbsp;termin.fem.multibody2d_3&nbsp;import&nbsp;RigidBody2D<br>
from&nbsp;termin.fem.electromechanic_2&nbsp;import&nbsp;DCMotor<br>
from&nbsp;termin.fem.electrical_2&nbsp;import&nbsp;VoltageSource,&nbsp;Ground,&nbsp;ElectricalNode,&nbsp;Resistor<br>
from&nbsp;termin.fem.dynamic_assembler&nbsp;import&nbsp;Variable,&nbsp;DynamicMatrixAssembler<br>
from&nbsp;termin.fem.inertia2d&nbsp;import&nbsp;SpatialInertia2D<br>
<br>
<br>
class&nbsp;TestDCMotor(unittest.TestCase):<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;test_dc_motor_creation(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Создание&nbsp;электромеханического&nbsp;двигателя&nbsp;постоянного&nbsp;тока&quot;&quot;&quot;<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler&nbsp;=&nbsp;DynamicMatrixAssembler()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body&nbsp;=&nbsp;RigidBody2D(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;SpatialInertia2D(mass=2.0,&nbsp;inertia=0.5,&nbsp;com=np.array([0.0,&nbsp;0.0])),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;gravity=np.array([0.0,&nbsp;0.0]),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body.velocity_var.set_value(np.array([0,&nbsp;0,&nbsp;1.0]))<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v1&nbsp;=&nbsp;ElectricalNode(&quot;V1&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v2&nbsp;=&nbsp;ElectricalNode(&quot;V2&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v0&nbsp;=&nbsp;ElectricalNode(&quot;V0&quot;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;vs&nbsp;=&nbsp;VoltageSource(v1,&nbsp;v0,&nbsp;U=12.0,&nbsp;assembler=assembler)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;r&nbsp;=&nbsp;Resistor(v1,&nbsp;v2,&nbsp;R=5.0,&nbsp;assembler=assembler)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;gnd&nbsp;=&nbsp;Ground(v0,&nbsp;assembler=assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;dcmotor&nbsp;=&nbsp;DCMotor(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;node1=v2,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;node2=v0,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;connected_body=body,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;k_e=0.1,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;k_t=0.1,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=assembler)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;matrices&nbsp;=&nbsp;assembler.assemble_electromechanic_domain()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;A_ext,&nbsp;b_ext,&nbsp;variables&nbsp;=&nbsp;assembler.assemble_extended_system_for_electromechanic(matrices)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
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
<!-- END SCAT CODE -->
</body>
</html>
