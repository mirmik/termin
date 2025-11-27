<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>utest/fem/mbody3d_test.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
#!/usr/bin/env&nbsp;python3<br>
#&nbsp;coding:utf-8<br>
<br>
import&nbsp;unittest<br>
import&nbsp;numpy&nbsp;as&nbsp;np<br>
import&nbsp;warnings<br>
from&nbsp;termin.fem.dynamic_assembler&nbsp;import&nbsp;DynamicMatrixAssembler<br>
from&nbsp;termin.fem.multibody3d_3&nbsp;import&nbsp;(<br>
&nbsp;&nbsp;&nbsp;&nbsp;RigidBody3D,&nbsp;FixedRotationJoint3D&nbsp;#ForceOnBody3D,&nbsp;,&nbsp;RevoluteJoint3D<br>
)<br>
from&nbsp;termin.geombase.pose3&nbsp;import&nbsp;Pose3<br>
from&nbsp;numpy&nbsp;import&nbsp;linalg<br>
from&nbsp;termin.fem.inertia3d&nbsp;import&nbsp;SpatialInertia3D<br>
<br>
<br>
class&nbsp;TestIntegrationMultibody3D(unittest.TestCase):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Интеграционные&nbsp;тесты&nbsp;для&nbsp;многотельной&nbsp;системы&quot;&quot;&quot;<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;test_rigid_body_with_gravity(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Создание&nbsp;простой&nbsp;системы&nbsp;с&nbsp;одним&nbsp;твердым&nbsp;телом&nbsp;и&nbsp;гравитацией&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler&nbsp;=&nbsp;DynamicMatrixAssembler()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body&nbsp;=&nbsp;RigidBody3D(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;inertia=SpatialInertia3D(mass=2.0,&nbsp;inertia=np.diag([1.0,&nbsp;1.0,&nbsp;1.0]),&nbsp;com=np.zeros(3)),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;gravity=np.array([0.0,&nbsp;0.0,&nbsp;-9.81]),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;index_map&nbsp;=&nbsp;assembler.index_map()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.assertIn(body.acceleration_var,&nbsp;index_map)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;matrices&nbsp;=&nbsp;assembler.assemble()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.assertIn(&quot;mass&quot;,&nbsp;matrices)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.assertIn(&quot;load&quot;,&nbsp;matrices)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.assertIn(&quot;stiffness&quot;,&nbsp;matrices)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.assertIn(&quot;damping&quot;,&nbsp;matrices)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;A_ext,&nbsp;b_ext,&nbsp;variables&nbsp;=&nbsp;assembler.assemble_extended_system(matrices)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;x&nbsp;=&nbsp;linalg.solve(A_ext,&nbsp;b_ext)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[0],&nbsp;0.0)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[1],&nbsp;0.0)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[2],&nbsp;-9.81)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;test_rigid_body_with_gravity_noncentral_x(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Создание&nbsp;простой&nbsp;системы&nbsp;с&nbsp;одним&nbsp;твердым&nbsp;телом&nbsp;и&nbsp;гравитацией&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler&nbsp;=&nbsp;DynamicMatrixAssembler()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body&nbsp;=&nbsp;RigidBody3D(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;inertia=SpatialInertia3D(mass=2.0,&nbsp;inertia=np.diag([1.0,&nbsp;1.0,&nbsp;1.0]),&nbsp;com=np.array([1.5,&nbsp;0.0,&nbsp;0.0])),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;gravity=np.array([0.0,&nbsp;0.0,&nbsp;-9.81]),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;index_map&nbsp;=&nbsp;assembler.index_map()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.assertIn(body.acceleration_var,&nbsp;index_map)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;matrices&nbsp;=&nbsp;assembler.assemble()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.assertIn(&quot;mass&quot;,&nbsp;matrices)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.assertIn(&quot;load&quot;,&nbsp;matrices)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.assertIn(&quot;stiffness&quot;,&nbsp;matrices)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.assertIn(&quot;damping&quot;,&nbsp;matrices)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;A_ext,&nbsp;b_ext,&nbsp;variables&nbsp;=&nbsp;assembler.assemble_extended_system(matrices)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;x&nbsp;=&nbsp;linalg.solve(A_ext,&nbsp;b_ext)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;A_ext:&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(A_ext)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;b_ext:&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(b_ext)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;variables:&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(variables)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;x&nbsp;=&nbsp;linalg.solve(A_ext,&nbsp;b_ext)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;Result:&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(x)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;diagnosis&nbsp;=&nbsp;assembler.matrix_diagnosis(A_ext)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;Matrix&nbsp;Diagnosis:&nbsp;&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;for&nbsp;key,&nbsp;value&nbsp;in&nbsp;diagnosis.items():<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(f&quot;&nbsp;&nbsp;{key}:&nbsp;{value}&quot;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;Equations:&nbsp;&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;eqs&nbsp;=&nbsp;assembler.system_to_human_readable(A_ext,&nbsp;b_ext,&nbsp;variables)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(eqs)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#assert&nbsp;False<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[0],&nbsp;0.0)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[1],&nbsp;0.0)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[2],&nbsp;-9.81)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[3],&nbsp;0.0)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[4],&nbsp;0.0)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[5],&nbsp;0.0)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;test_rigid_body_with_gravity_noncentral_y(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Создание&nbsp;простой&nbsp;системы&nbsp;с&nbsp;одним&nbsp;твердым&nbsp;телом&nbsp;и&nbsp;гравитацией&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler&nbsp;=&nbsp;DynamicMatrixAssembler()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body&nbsp;=&nbsp;RigidBody3D(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;inertia=SpatialInertia3D(mass=2.0,&nbsp;inertia=np.diag([1.0,&nbsp;1.0,&nbsp;1.0]),&nbsp;com=np.array([0.0,&nbsp;1.5,&nbsp;0.0])),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;gravity=np.array([0.0,&nbsp;0.0,&nbsp;-9.81]),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;index_map&nbsp;=&nbsp;assembler.index_map()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.assertIn(body.acceleration_var,&nbsp;index_map)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;matrices&nbsp;=&nbsp;assembler.assemble()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.assertIn(&quot;mass&quot;,&nbsp;matrices)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.assertIn(&quot;load&quot;,&nbsp;matrices)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.assertIn(&quot;stiffness&quot;,&nbsp;matrices)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.assertIn(&quot;damping&quot;,&nbsp;matrices)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;A_ext,&nbsp;b_ext,&nbsp;variables&nbsp;=&nbsp;assembler.assemble_extended_system(matrices)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;x&nbsp;=&nbsp;linalg.solve(A_ext,&nbsp;b_ext)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;A_ext:&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(A_ext)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;b_ext:&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(b_ext)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;variables:&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(variables)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;x&nbsp;=&nbsp;linalg.solve(A_ext,&nbsp;b_ext)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;Result:&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(x)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;diagnosis&nbsp;=&nbsp;assembler.matrix_diagnosis(A_ext)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;Matrix&nbsp;Diagnosis:&nbsp;&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;for&nbsp;key,&nbsp;value&nbsp;in&nbsp;diagnosis.items():<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(f&quot;&nbsp;&nbsp;{key}:&nbsp;{value}&quot;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;Equations:&nbsp;&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;eqs&nbsp;=&nbsp;assembler.system_to_human_readable(A_ext,&nbsp;b_ext,&nbsp;variables)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(eqs)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[0],&nbsp;0.0)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[1],&nbsp;0.0)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[2],&nbsp;-9.81)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[3],&nbsp;0.0)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[4],&nbsp;0.0)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[5],&nbsp;0.0)<br>
&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;test_rigid_body_with_fixed_rotation_joint(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Создание&nbsp;простой&nbsp;системы&nbsp;с&nbsp;одним&nbsp;твердым&nbsp;телом&nbsp;и&nbsp;фиксированным&nbsp;шарниром&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler&nbsp;=&nbsp;DynamicMatrixAssembler()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body&nbsp;=&nbsp;RigidBody3D(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;inertia=SpatialInertia3D(mass=5.0,&nbsp;inertia=np.diag([5.0,&nbsp;5.0,&nbsp;5.0]),&nbsp;com=np.zeros(3)),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;gravity=np.array([0.0,&nbsp;0.0,&nbsp;-10.00]),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body.set_pose(Pose3(lin=np.array([1.0,&nbsp;0.0,&nbsp;0.0])))<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;joint&nbsp;=&nbsp;FixedRotationJoint3D(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body=body,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=assembler,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;coords_of_joint&nbsp;=&nbsp;np.array([0.0,&nbsp;0.0,&nbsp;0.0]))<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;joint.radius&nbsp;is&nbsp;not&nbsp;None<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;joint.radius()[0]&nbsp;==&nbsp;-1.0<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;joint.radius()[1]&nbsp;==&nbsp;0.0<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;assembler.total_variables_by_tag(&quot;acceleration&quot;)&nbsp;==&nbsp;6<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;assembler.total_variables_by_tag(&quot;force&quot;)&nbsp;==&nbsp;3<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;index_maps&nbsp;=&nbsp;assembler.index_maps()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.assertIn(&quot;acceleration&quot;,&nbsp;index_maps)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.assertIn(&quot;force&quot;,&nbsp;index_maps)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.assertEqual(len(index_maps[&quot;force&quot;]),&nbsp;1)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.assertEqual(len(index_maps[&quot;acceleration&quot;]),&nbsp;1)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.assertIn(body.acceleration_var,&nbsp;index_maps[&quot;acceleration&quot;])<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.assertIn(joint.internal_force,&nbsp;index_maps[&quot;force&quot;])<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;matrices&nbsp;=&nbsp;assembler.assemble()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;A_ext,&nbsp;b_ext,&nbsp;variables&nbsp;=&nbsp;assembler.assemble_extended_system(matrices)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;A_ext:&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(A_ext)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;b_ext:&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(b_ext)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;variables:&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(variables)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;x&nbsp;=&nbsp;linalg.solve(A_ext,&nbsp;b_ext)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;Result:&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(x)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;diagnosis&nbsp;=&nbsp;assembler.matrix_diagnosis(A_ext)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;Matrix&nbsp;Diagnosis:&nbsp;&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;for&nbsp;key,&nbsp;value&nbsp;in&nbsp;diagnosis.items():<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(f&quot;&nbsp;&nbsp;{key}:&nbsp;{value}&quot;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;Equations:&nbsp;&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;eqs&nbsp;=&nbsp;assembler.system_to_human_readable(A_ext,&nbsp;b_ext,&nbsp;variables)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(eqs)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#assert&nbsp;False<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[0],&nbsp;0.0)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[1],&nbsp;0.0)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[2],&nbsp;-5.0)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;test_rigid_body_with_fixed_rotation_joint_outcenter(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Создание&nbsp;простой&nbsp;системы&nbsp;с&nbsp;одним&nbsp;твердым&nbsp;телом&nbsp;и&nbsp;фиксированным&nbsp;шарниром&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler&nbsp;=&nbsp;DynamicMatrixAssembler()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body&nbsp;=&nbsp;RigidBody3D(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;inertia=SpatialInertia3D(mass=5.0,&nbsp;inertia=np.diag([5.0,&nbsp;5.0,&nbsp;5.0]),&nbsp;com=np.array([0.75,&nbsp;0.0,&nbsp;0.0])),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;gravity=np.array([0.0,&nbsp;0.0,&nbsp;-10.00]),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body.set_pose(Pose3(lin=np.array([0.25,&nbsp;0.0,&nbsp;0.0])))<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#body.acceleration_var.set_value_by_rank(np.array([0.0,&nbsp;0.0,&nbsp;1.0,&nbsp;0.0,&nbsp;0.0,&nbsp;0.0]),&nbsp;rank=1)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;joint&nbsp;=&nbsp;FixedRotationJoint3D(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body=body,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=assembler,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;coords_of_joint&nbsp;=&nbsp;np.array([0.0,&nbsp;0.0,&nbsp;0.0]))<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#joint.update_radius()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;joint.radius&nbsp;is&nbsp;not&nbsp;None<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#assert&nbsp;joint.radius[0]&nbsp;==&nbsp;-1.0<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#assert&nbsp;joint.radius[1]&nbsp;==&nbsp;0.0<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;assembler.total_variables_by_tag(&quot;acceleration&quot;)&nbsp;==&nbsp;6<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;assembler.total_variables_by_tag(&quot;force&quot;)&nbsp;==&nbsp;3<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;index_maps&nbsp;=&nbsp;assembler.index_maps()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.assertIn(&quot;acceleration&quot;,&nbsp;index_maps)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.assertIn(&quot;force&quot;,&nbsp;index_maps)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.assertEqual(len(index_maps[&quot;force&quot;]),&nbsp;1)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.assertEqual(len(index_maps[&quot;acceleration&quot;]),&nbsp;1)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.assertIn(body.acceleration_var,&nbsp;index_maps[&quot;acceleration&quot;])<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.assertIn(joint.internal_force,&nbsp;index_maps[&quot;force&quot;])<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;matrices&nbsp;=&nbsp;assembler.assemble()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;A_ext,&nbsp;b_ext,&nbsp;variables&nbsp;=&nbsp;assembler.assemble_extended_system(matrices)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;A_ext:&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(A_ext)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;b_ext:&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(b_ext)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;variables:&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(variables)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;x&nbsp;=&nbsp;linalg.solve(A_ext,&nbsp;b_ext)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;Result:&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(x)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;diagnosis&nbsp;=&nbsp;assembler.matrix_diagnosis(A_ext)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;Matrix&nbsp;Diagnosis:&nbsp;&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;for&nbsp;key,&nbsp;value&nbsp;in&nbsp;diagnosis.items():<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(f&quot;&nbsp;&nbsp;{key}:&nbsp;{value}&quot;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;Equations:&nbsp;&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;eqs&nbsp;=&nbsp;assembler.system_to_human_readable(A_ext,&nbsp;b_ext,&nbsp;variables)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(eqs)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#assert&nbsp;np.isclose(x[0],&nbsp;0.0)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#assert&nbsp;np.isclose(x[1],&nbsp;0.0)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#assert&nbsp;np.isclose(x[2],&nbsp;-5.0)<br>
<!-- END SCAT CODE -->
</body>
</html>
