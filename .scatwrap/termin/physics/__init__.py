<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/physics/__init__.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;Модуль&nbsp;физической&nbsp;симуляции&nbsp;для&nbsp;динамики&nbsp;твёрдых&nbsp;тел.&quot;&quot;&quot;<br>
<br>
#&nbsp;Setup&nbsp;DLL&nbsp;paths&nbsp;before&nbsp;importing&nbsp;native&nbsp;extensions<br>
from&nbsp;termin&nbsp;import&nbsp;_dll_setup&nbsp;&nbsp;#&nbsp;noqa:&nbsp;F401<br>
<br>
from&nbsp;termin.physics._physics_native&nbsp;import&nbsp;(<br>
&nbsp;&nbsp;&nbsp;&nbsp;RigidBody,<br>
&nbsp;&nbsp;&nbsp;&nbsp;PhysicsWorld,<br>
&nbsp;&nbsp;&nbsp;&nbsp;Contact,<br>
)<br>
from&nbsp;termin.physics.rigid_body_component&nbsp;import&nbsp;RigidBodyComponent<br>
from&nbsp;termin.physics.physics_world_component&nbsp;import&nbsp;PhysicsWorldComponent<br>
<br>
#&nbsp;FEM&nbsp;physics<br>
from&nbsp;termin.physics.fem_physics_world_component&nbsp;import&nbsp;FEMPhysicsWorldComponent<br>
from&nbsp;termin.physics.fem_rigid_body_component&nbsp;import&nbsp;FEMRigidBodyComponent<br>
from&nbsp;termin.physics.fem_fixed_joint_component&nbsp;import&nbsp;FEMFixedJointComponent<br>
from&nbsp;termin.physics.fem_revolute_joint_component&nbsp;import&nbsp;FEMRevoluteJointComponent<br>
<br>
__all__&nbsp;=&nbsp;[<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;C++&nbsp;physics<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;RigidBody&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;PhysicsWorld&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;Contact&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;RigidBodyComponent&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;PhysicsWorldComponent&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;FEM&nbsp;physics<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;FEMPhysicsWorldComponent&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;FEMRigidBodyComponent&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;FEMFixedJointComponent&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;FEMRevoluteJointComponent&quot;,<br>
]<br>
<!-- END SCAT CODE -->
</body>
</html>
