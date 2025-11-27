<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>utest/fem/mbody2d_test.py</title>
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
from&nbsp;termin.fem.multibody2d_3&nbsp;import&nbsp;(<br>
&nbsp;&nbsp;&nbsp;&nbsp;RigidBody2D,&nbsp;ForceOnBody2D,&nbsp;FixedRotationJoint2D,&nbsp;RevoluteJoint2D<br>
)<br>
from&nbsp;numpy&nbsp;import&nbsp;linalg<br>
from&nbsp;termin.geombase.screw&nbsp;import&nbsp;Screw2<br>
from&nbsp;termin.geombase.pose2&nbsp;import&nbsp;Pose2<br>
from&nbsp;termin.fem.inertia2d&nbsp;import&nbsp;SpatialInertia2D<br>
<br>
<br>
class&nbsp;TestIntegrationMultibody2D(unittest.TestCase):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Интеграционные&nbsp;тесты&nbsp;для&nbsp;многотельной&nbsp;системы&quot;&quot;&quot;<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;test_rigid_body_with_gravity(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Создание&nbsp;простой&nbsp;системы&nbsp;с&nbsp;одним&nbsp;твердым&nbsp;телом&nbsp;и&nbsp;гравитацией&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler&nbsp;=&nbsp;DynamicMatrixAssembler()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body&nbsp;=&nbsp;RigidBody2D(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;inertia=SpatialInertia2D(mass=2.0,&nbsp;inertia=1.0,&nbsp;com=np.zeros(2)),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;gravity=np.array([0.0,&nbsp;-9.81]),<br>
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
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[1],&nbsp;-9.81)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[2],&nbsp;0.0)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;test_noncentral_gravity(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Создание&nbsp;простой&nbsp;системы&nbsp;с&nbsp;одним&nbsp;твердым&nbsp;телом&nbsp;и&nbsp;гравитацией&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler&nbsp;=&nbsp;DynamicMatrixAssembler()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body&nbsp;=&nbsp;RigidBody2D(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;inertia=SpatialInertia2D(mass=2.0,&nbsp;inertia=1.0,&nbsp;com=np.array([0.5,&nbsp;0.0])),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;gravity=np.array([0.0,&nbsp;-9.81]),<br>
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
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;A_ext:&nbsp;\n&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(A_ext)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;b_ext:&nbsp;\n&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(b_ext)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;variables:&nbsp;\n&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(variables)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;Result:&nbsp;\n&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(x)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;diagnosis&nbsp;=&nbsp;assembler.matrix_diagnosis(A_ext)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;Matrix&nbsp;Diagnosis:&nbsp;&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;for&nbsp;key,&nbsp;value&nbsp;in&nbsp;diagnosis.items():<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(f&quot;&nbsp;&nbsp;{key}:&nbsp;{value}&quot;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;eqs&nbsp;=&nbsp;assembler.system_to_human_readable(A_ext,&nbsp;b_ext,&nbsp;variables)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;Equations:&nbsp;&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(eqs)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[0],&nbsp;0.0)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[1],&nbsp;-9.81)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[2],&nbsp;0.0)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;test_rigid_body_with_external_force(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Создание&nbsp;простой&nbsp;системы&nbsp;с&nbsp;одним&nbsp;твердым&nbsp;телом&nbsp;и&nbsp;внешней&nbsp;силой&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler&nbsp;=&nbsp;DynamicMatrixAssembler()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body&nbsp;=&nbsp;RigidBody2D(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;inertia=SpatialInertia2D(mass=3.0,&nbsp;inertia=2.0,&nbsp;com=np.zeros(2)),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;gravity=np.array([0.0,&nbsp;0.0]),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;force&nbsp;=&nbsp;ForceOnBody2D(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body=body,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;wrench=Screw2(ang=0.0,&nbsp;lin=np.array([6.0,&nbsp;0.0])),<br>
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
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[0],&nbsp;2.0)&nbsp;&nbsp;#&nbsp;vx&nbsp;=&nbsp;Fx/m&nbsp;=&nbsp;6/3&nbsp;=&nbsp;2<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[1],&nbsp;0.0)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[2],&nbsp;0.0)&nbsp;<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;test_rigid_body_with_external_torque(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Создание&nbsp;простой&nbsp;системы&nbsp;с&nbsp;одним&nbsp;твердым&nbsp;телом&nbsp;и&nbsp;внешним&nbsp;моментом&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler&nbsp;=&nbsp;DynamicMatrixAssembler()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body&nbsp;=&nbsp;RigidBody2D(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;inertia=SpatialInertia2D(mass=4.0,&nbsp;inertia=8.0,&nbsp;com=np.zeros(2)),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;gravity=np.array([0.0,&nbsp;0.0]),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;force&nbsp;=&nbsp;ForceOnBody2D(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body=body,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;wrench=Screw2(ang=16.0,&nbsp;lin=np.array([0.0,&nbsp;0.0])),<br>
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
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[0],&nbsp;0.0)&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[1],&nbsp;0.0)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[2],&nbsp;2.0)&nbsp;&nbsp;#&nbsp;omega&nbsp;=&nbsp;torque/J&nbsp;=&nbsp;16/8&nbsp;=&nbsp;2<br>
&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;test_rigid_body_with_fixed_rotation_joint(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Создание&nbsp;простой&nbsp;системы&nbsp;с&nbsp;одним&nbsp;твердым&nbsp;телом&nbsp;и&nbsp;фиксированным&nbsp;шарниром&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler&nbsp;=&nbsp;DynamicMatrixAssembler()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body&nbsp;=&nbsp;RigidBody2D(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;inertia=SpatialInertia2D(mass=5.0,&nbsp;inertia=5.0,&nbsp;com=np.zeros(2)),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;gravity=np.array([0.0,&nbsp;-10.00]),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body.set_pose(Pose2(lin=[1.0,&nbsp;0.0],&nbsp;ang=0.0))<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;joint&nbsp;=&nbsp;FixedRotationJoint2D(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body=body,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;coords_of_joint=np.array([0.0,&nbsp;0.0]),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;joint.radius()[0]&nbsp;==&nbsp;-1.0<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;joint.radius()[1]&nbsp;==&nbsp;0.0<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;assembler.total_variables_by_tag(&quot;acceleration&quot;)&nbsp;==&nbsp;3<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;assembler.total_variables_by_tag(&quot;force&quot;)&nbsp;==&nbsp;2<br>
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
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;A_ext,&nbsp;b_ext,&nbsp;variables&nbsp;=&nbsp;assembler.assemble_extended_system(matrices)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;x&nbsp;=&nbsp;linalg.solve(A_ext,&nbsp;b_ext)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[0],&nbsp;0.0)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[1],&nbsp;-5.0)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[2],&nbsp;-5.0)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;test_rigid_body_with_fixed_rotation_joint_nonnull_angvel(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Создание&nbsp;простой&nbsp;системы&nbsp;с&nbsp;одним&nbsp;твердым&nbsp;телом&nbsp;и&nbsp;фиксированным&nbsp;шарниром&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler&nbsp;=&nbsp;DynamicMatrixAssembler()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body&nbsp;=&nbsp;RigidBody2D(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;inertia=SpatialInertia2D(mass=5.0,&nbsp;inertia=5.0,&nbsp;com=np.zeros(2)),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;gravity=np.array([0.0,&nbsp;0.0]),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body.set_pose(Pose2(lin=[1.0,&nbsp;0.0],&nbsp;ang=0.0))<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body.velocity_var.set_value([0.0,&nbsp;6.0,&nbsp;6.0])&nbsp;<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;joint&nbsp;=&nbsp;FixedRotationJoint2D(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body=body,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;coords_of_joint=np.array([0.0,&nbsp;0.0]),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;matrices&nbsp;=&nbsp;assembler.assemble()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;A_ext,&nbsp;b_ext,&nbsp;variables&nbsp;=&nbsp;assembler.assemble_extended_system(matrices)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;x&nbsp;=&nbsp;linalg.solve(A_ext,&nbsp;b_ext)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;A_ext:&nbsp;\n&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(A_ext)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;b_ext:&nbsp;\n&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(b_ext)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print&nbsp;(&quot;variables:&nbsp;\n&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(variables)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;Result:&nbsp;\n&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(x)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;diagnosis&nbsp;=&nbsp;assembler.matrix_diagnosis(A_ext)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;Matrix&nbsp;Diagnosis:&nbsp;&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;for&nbsp;key,&nbsp;value&nbsp;in&nbsp;diagnosis.items():<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(f&quot;&nbsp;&nbsp;{key}:&nbsp;{value}&quot;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;eqs&nbsp;=&nbsp;assembler.system_to_human_readable(A_ext,&nbsp;b_ext,&nbsp;variables)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;Equations:&nbsp;&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(eqs)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;assert&nbsp;False<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[0],&nbsp;-36.0)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[1],&nbsp;0.0)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[2],&nbsp;0.0)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[3],&nbsp;-360)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(x[4],&nbsp;0.0)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;test_simple_pendulum_in_bottom_position(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Создание&nbsp;простой&nbsp;системы&nbsp;с&nbsp;одним&nbsp;твердым&nbsp;телом&nbsp;и&nbsp;фиксированным&nbsp;шарниром&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler&nbsp;=&nbsp;DynamicMatrixAssembler()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body&nbsp;=&nbsp;RigidBody2D(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;inertia=SpatialInertia2D(mass=5.0,&nbsp;inertia=5.0,&nbsp;com=np.zeros(2)),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;gravity=np.array([0.0,&nbsp;-10.00]),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body.set_pose(Pose2(lin=[0.0,&nbsp;-1.0],&nbsp;ang=0.0))<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;joint&nbsp;=&nbsp;FixedRotationJoint2D(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body=body,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler.time_step&nbsp;=&nbsp;0.01&nbsp;&nbsp;#&nbsp;временной&nbsp;шаг<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;matrices&nbsp;=&nbsp;assembler.assemble()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;A_ext,&nbsp;b_ext,&nbsp;variables&nbsp;=&nbsp;assembler.assemble_extended_system(matrices)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;x&nbsp;=&nbsp;linalg.solve(A_ext,&nbsp;b_ext)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;q_ddot,&nbsp;holonomic_lambdas,&nbsp;nonholonomic_lambdas&nbsp;=&nbsp;assembler.sort_results(x)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(body.acceleration_var.value[0],&nbsp;0.0)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(body.acceleration_var.value[1],&nbsp;0.0)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(body.acceleration_var.value[2],&nbsp;0.0)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;rotation_symmetric(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Создание&nbsp;простой&nbsp;системы&nbsp;с&nbsp;одним&nbsp;твердым&nbsp;телом&nbsp;и&nbsp;фиксированным&nbsp;шарниром&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler&nbsp;=&nbsp;DynamicMatrixAssembler()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body&nbsp;=&nbsp;RigidBody2D(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;inertia=SpatialInertia2D(mass=5.0,&nbsp;inertia=5.0,&nbsp;com=np.zeros(2)),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;gravity=np.array([0.0,&nbsp;-10.00]),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body.set_pose(Pose2(lin=[0.0,&nbsp;-1.0],&nbsp;ang=0.0))<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;joint&nbsp;=&nbsp;FixedRotationJoint2D(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body=body,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler.time_step&nbsp;=&nbsp;0.01&nbsp;&nbsp;#&nbsp;временной&nbsp;шаг<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;matrices&nbsp;=&nbsp;assembler.assemble()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;A_ext,&nbsp;b_ext,&nbsp;variables&nbsp;=&nbsp;assembler.assemble_extended_system(matrices)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;x&nbsp;=&nbsp;linalg.solve(A_ext,&nbsp;b_ext)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;q_ddot,&nbsp;holonomic_lambdas,&nbsp;nonholonomic_lambdas&nbsp;=&nbsp;assembler.sort_results(x)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler2&nbsp;=&nbsp;DynamicMatrixAssembler()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body2&nbsp;=&nbsp;RigidBody2D(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;inertia=SpatialInertia2D(mass=5.0,&nbsp;inertia=5.0,&nbsp;com=np.zeros(2)),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;gravity=np.array([-10.0,&nbsp;0.00]),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=assembler2)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body2.set_pose(Pose2(lin=[-1.0,&nbsp;0.0],&nbsp;ang=0.0))<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;joint2&nbsp;=&nbsp;FixedRotationJoint2D(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body=body2,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=assembler2)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler2.time_step&nbsp;=&nbsp;0.01&nbsp;&nbsp;#&nbsp;временной&nbsp;шаг<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;matrices&nbsp;=&nbsp;assembler2.assemble()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;A_ext2,&nbsp;b_ext2,&nbsp;variables2&nbsp;=&nbsp;assembler2.assemble_extended_system(matrices)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;x&nbsp;=&nbsp;linalg.solve(A_ext2,&nbsp;b_ext2)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;q_ddot,&nbsp;holonomic_lambdas,&nbsp;nonholonomic_lambdas&nbsp;=&nbsp;assembler2.sort_results(x)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(A_ext,&nbsp;A_ext2).all()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(b_ext,&nbsp;b_ext2).all()<br>
<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;test_simple_pendulum(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Создание&nbsp;простой&nbsp;системы&nbsp;с&nbsp;одним&nbsp;твердым&nbsp;телом&nbsp;и&nbsp;фиксированным&nbsp;шарниром&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler&nbsp;=&nbsp;DynamicMatrixAssembler()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body&nbsp;=&nbsp;RigidBody2D(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;inertia=SpatialInertia2D(mass=5.0,&nbsp;inertia=5.0,&nbsp;com=np.zeros(2)),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;gravity=np.array([0.0,&nbsp;-10.00]),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body.set_pose(Pose2(lin=np.array([1.0,&nbsp;0.0]),&nbsp;ang=0.0))&nbsp;#&nbsp;это&nbsp;установка&nbsp;позиции&nbsp;(хотя&nbsp;может&nbsp;показаться,&nbsp;что&nbsp;это&nbsp;скорость.&nbsp;но&nbsp;это&nbsp;позиция)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;joint&nbsp;=&nbsp;FixedRotationJoint2D(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body=body,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;coords_of_joint=np.array([0.0,&nbsp;0.0]),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler.time_step&nbsp;=&nbsp;0.01&nbsp;&nbsp;#&nbsp;временной&nbsp;шаг<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;left_side&nbsp;=&nbsp;False<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;right_side&nbsp;=&nbsp;False<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;for&nbsp;step&nbsp;in&nbsp;range(500):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;matrices&nbsp;=&nbsp;assembler.assemble()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;A_ext,&nbsp;b_ext,&nbsp;variables&nbsp;=&nbsp;assembler.assemble_extended_system(matrices)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;x&nbsp;=&nbsp;linalg.solve(A_ext,&nbsp;b_ext)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;q_ddot,&nbsp;holonomic_lambdas,&nbsp;nonholonomic_lambdas&nbsp;=&nbsp;assembler.sort_results(x)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;q_dot,&nbsp;q&nbsp;=&nbsp;assembler.integrate_with_constraint_projection(q_ddot,&nbsp;matrices)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;pose&nbsp;=&nbsp;body.pose()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(f&quot;Pose:&nbsp;lin&nbsp;=&nbsp;{pose.lin},&nbsp;{np.linalg.norm(pose.lin)}&quot;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;pose.lin[0]&nbsp;&lt;&nbsp;0.0:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;left_side&nbsp;=&nbsp;True<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;pose.lin[0]&nbsp;&gt;&nbsp;0.0:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;right_side&nbsp;=&nbsp;True<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(np.linalg.norm(pose.lin),&nbsp;1.0,&nbsp;atol=1e-3)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;eps&nbsp;=&nbsp;1e-15<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;pose&nbsp;=&nbsp;body.pose()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;left_side&nbsp;and&nbsp;right_side<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;test_simple_pendulum_noncentral(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Создание&nbsp;простой&nbsp;системы&nbsp;с&nbsp;одним&nbsp;твердым&nbsp;телом&nbsp;и&nbsp;фиксированным&nbsp;шарниром&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler&nbsp;=&nbsp;DynamicMatrixAssembler()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body&nbsp;=&nbsp;RigidBody2D(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;inertia=SpatialInertia2D(mass=5.0,&nbsp;inertia=5.0,&nbsp;com=np.array([0.25,&nbsp;0.0])),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;gravity=np.array([0.0,&nbsp;-10.00]),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body.set_pose(Pose2(lin=np.array([0.75,&nbsp;0.0]),&nbsp;ang=0.0))<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(assembler.collect_variables(&quot;position&quot;))<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;joint&nbsp;=&nbsp;FixedRotationJoint2D(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body=body,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;coords_of_joint=np.array([0.0,&nbsp;0.0]),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler.time_step&nbsp;=&nbsp;0.01&nbsp;&nbsp;#&nbsp;временной&nbsp;шаг<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;matrices&nbsp;=&nbsp;assembler.assemble()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;A_ext,&nbsp;b_ext,&nbsp;variables&nbsp;=&nbsp;assembler.assemble_extended_system(matrices)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;x&nbsp;=&nbsp;linalg.solve(A_ext,&nbsp;b_ext)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;A_ext:&nbsp;\n&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(A_ext)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;b_ext:&nbsp;\n&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(b_ext)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print&nbsp;(&quot;variables:&nbsp;\n&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(variables)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;Result:&nbsp;\n&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(x)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;diagnosis&nbsp;=&nbsp;assembler.matrix_diagnosis(A_ext)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;Matrix&nbsp;Diagnosis:&nbsp;&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;for&nbsp;key,&nbsp;value&nbsp;in&nbsp;diagnosis.items():<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(f&quot;&nbsp;&nbsp;{key}:&nbsp;{value}&quot;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;eqs&nbsp;=&nbsp;assembler.system_to_human_readable(A_ext,&nbsp;b_ext,&nbsp;variables)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;Equations:&nbsp;&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(eqs)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(assembler.collect_variables(&quot;velocity&quot;))<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(assembler.collect_variables(&quot;position&quot;))<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;q_ddot,&nbsp;holonomic_lambdas,&nbsp;nonholonomic_lambdas&nbsp;=&nbsp;assembler.sort_results(x)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;q_dot,&nbsp;q&nbsp;=&nbsp;assembler.integrate_with_constraint_projection(q_ddot,&nbsp;matrices)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;np.isclose(q_ddot[2],&nbsp;-5.0)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;test_double_pendulum(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Создание&nbsp;простой&nbsp;системы&nbsp;с&nbsp;двумя&nbsp;твердыми&nbsp;телами&nbsp;и&nbsp;фиксированными&nbsp;шарнирами&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler&nbsp;=&nbsp;DynamicMatrixAssembler()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body1&nbsp;=&nbsp;RigidBody2D(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;inertia=SpatialInertia2D(mass=6.0,&nbsp;inertia=7.0,&nbsp;com=np.array([0.0,&nbsp;0.0])),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;gravity=np.array([0.0,&nbsp;-9.81]),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=assembler,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;name=&quot;body1&quot;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body1.set_pose(Pose2(lin=np.array([5.0,&nbsp;0.0]),&nbsp;ang=0.0))<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;joint1&nbsp;=&nbsp;FixedRotationJoint2D(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body=body1,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body2&nbsp;=&nbsp;RigidBody2D(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;inertia=SpatialInertia2D(mass=8.0,&nbsp;inertia=9.0,&nbsp;com=np.zeros(2)),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;gravity=np.array([0.0,&nbsp;-9.81]),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=assembler,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;name=&quot;body2&quot;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body2.set_pose(Pose2(lin=np.array([6.0,&nbsp;0.0]),&nbsp;ang=0.0))<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;joint2&nbsp;=&nbsp;RevoluteJoint2D(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;bodyA=body1,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;bodyB=body2,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;coords_of_joint=np.array([1.0,&nbsp;0.0]),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler.time_step&nbsp;=&nbsp;0.01&nbsp;&nbsp;#&nbsp;временной&nbsp;шаг<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;for&nbsp;step&nbsp;in&nbsp;range(500):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;matrices&nbsp;=&nbsp;assembler.assemble()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;A_ext,&nbsp;b_ext,&nbsp;variables&nbsp;=&nbsp;assembler.assemble_extended_system(matrices)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;x&nbsp;=&nbsp;linalg.solve(A_ext,&nbsp;b_ext)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;eqs&nbsp;=&nbsp;assembler.system_to_human_readable(A_ext,&nbsp;b_ext,&nbsp;variables)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;A_ext:&nbsp;\n&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(A_ext)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;b_ext:&nbsp;\n&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(b_ext)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print&nbsp;(&quot;variables:&nbsp;\n&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(variables)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;Result:&nbsp;\n&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(x)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;diagnosis&nbsp;=&nbsp;assembler.matrix_diagnosis(A_ext)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;Matrix&nbsp;Diagnosis:&nbsp;&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;for&nbsp;key,&nbsp;value&nbsp;in&nbsp;diagnosis.items():<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(f&quot;&nbsp;&nbsp;{key}:&nbsp;{value}&quot;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(&quot;Equations:&nbsp;&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(eqs)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#assert&nbsp;False<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;q_ddot,&nbsp;holonomic_lambdas,&nbsp;nonholonomic_lambdas&nbsp;=&nbsp;assembler.sort_results(x)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;q_dot,&nbsp;q&nbsp;=&nbsp;assembler.integrate_with_constraint_projection(q_ddot,&nbsp;matrices)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(f&quot;Step&nbsp;{step}:&nbsp;position1&nbsp;=&nbsp;{q[0:2]},&nbsp;position2&nbsp;=&nbsp;{q[3:5]},&nbsp;norm1&nbsp;=&nbsp;{np.linalg.norm(q[0:2])},&nbsp;norm2&nbsp;=&nbsp;{np.linalg.norm(q[0:2]&nbsp;-&nbsp;q[3:5])}&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;eps&nbsp;=&nbsp;1e-15<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#assert&nbsp;1-eps&nbsp;&lt;&nbsp;np.linalg.norm((q[0:2]))&nbsp;&lt;&nbsp;1+eps<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#assert&nbsp;1-eps&nbsp;&lt;&nbsp;np.linalg.norm((q[0:2]&nbsp;-&nbsp;q[3:5]))&nbsp;&lt;&nbsp;1+eps<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;test_double_pendulum_bottom_position(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Создание&nbsp;простой&nbsp;системы&nbsp;с&nbsp;двумя&nbsp;твердыми&nbsp;телами&nbsp;и&nbsp;фиксированными&nbsp;шарнирами&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler&nbsp;=&nbsp;DynamicMatrixAssembler()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body1&nbsp;=&nbsp;RigidBody2D(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;inertia=SpatialInertia2D(mass=6.0,&nbsp;inertia=7.0,&nbsp;com=np.zeros(2)),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;gravity=np.array([0.0,&nbsp;-9.81]),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=assembler,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;name=&quot;body1&quot;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body1.set_pose(Pose2(lin=np.array([0.0,&nbsp;-2.0]),&nbsp;ang=0.0))<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;joint1&nbsp;=&nbsp;FixedRotationJoint2D(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body=body1,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body2&nbsp;=&nbsp;RigidBody2D(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;inertia=SpatialInertia2D(mass=8.0,&nbsp;inertia=9.0,&nbsp;com=np.zeros(2)),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;gravity=np.array([0.0,&nbsp;-9.81]),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=assembler,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;name=&quot;body2&quot;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body2.set_pose(Pose2(lin=np.array([0.0,&nbsp;-4.0]),&nbsp;ang=0.0))<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;joint2&nbsp;=&nbsp;RevoluteJoint2D(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;bodyA=body1,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;bodyB=body2,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;coords_of_joint=np.array([0.0,&nbsp;-2.0]),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler.time_step&nbsp;=&nbsp;0.01&nbsp;&nbsp;#&nbsp;временной&nbsp;шаг<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;for&nbsp;step&nbsp;in&nbsp;range(500):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;matrices&nbsp;=&nbsp;assembler.assemble()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;A_ext,&nbsp;b_ext,&nbsp;variables&nbsp;=&nbsp;assembler.assemble_extended_system(matrices)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;x&nbsp;=&nbsp;linalg.solve(A_ext,&nbsp;b_ext)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;eqs&nbsp;=&nbsp;assembler.system_to_human_readable(A_ext,&nbsp;b_ext,&nbsp;variables)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;q_ddot,&nbsp;holonomic_lambdas,&nbsp;nonholonomic_lambdas&nbsp;=&nbsp;assembler.sort_results(x)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;q_dot,&nbsp;q&nbsp;=&nbsp;assembler.integrate_with_constraint_projection(q_ddot,&nbsp;matrices)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(f&quot;Step&nbsp;{step}:&nbsp;position1&nbsp;=&nbsp;{q[0:2]},&nbsp;position2&nbsp;=&nbsp;{q[3:5]},&nbsp;norm1&nbsp;=&nbsp;{np.linalg.norm(q[0:2])},&nbsp;norm2&nbsp;=&nbsp;{np.linalg.norm(q[0:2]&nbsp;-&nbsp;q[3:5])}&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;eps&nbsp;=&nbsp;1e-15<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assert&nbsp;-eps&nbsp;&lt;&nbsp;np.linalg.norm((q[0]))&nbsp;&lt;&nbsp;+eps<br>
<!-- END SCAT CODE -->
</body>
</html>
