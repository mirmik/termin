<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/kinematic/__init__.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;<br>
Модуль&nbsp;кинематики&nbsp;и&nbsp;трансформаций.<br>
<br>
Содержит&nbsp;классы&nbsp;для&nbsp;работы&nbsp;с:<br>
-&nbsp;Трансформациями&nbsp;(Transform,&nbsp;Transform3)<br>
-&nbsp;Кинематическими&nbsp;преобразованиями&nbsp;(Rotator3,&nbsp;Actuator3)<br>
-&nbsp;Кинематическими&nbsp;цепями&nbsp;(KinematicChain3)<br>
&quot;&quot;&quot;<br>
<br>
from&nbsp;.transform&nbsp;import&nbsp;Transform,&nbsp;Transform3<br>
from&nbsp;.general_transform&nbsp;import&nbsp;GeneralTransform3<br>
from&nbsp;.kinematic&nbsp;import&nbsp;(<br>
&nbsp;&nbsp;&nbsp;&nbsp;KinematicTransform3,<br>
&nbsp;&nbsp;&nbsp;&nbsp;KinematicTransform3OneScrew,<br>
&nbsp;&nbsp;&nbsp;&nbsp;Rotator3,<br>
&nbsp;&nbsp;&nbsp;&nbsp;Actuator3<br>
)<br>
from&nbsp;.kinchain&nbsp;import&nbsp;KinematicChain3<br>
from&nbsp;.conditions&nbsp;import&nbsp;SymCondition,&nbsp;ConditionCollection<br>
<br>
__all__&nbsp;=&nbsp;[<br>
&nbsp;&nbsp;&nbsp;&nbsp;'Transform',<br>
&nbsp;&nbsp;&nbsp;&nbsp;'Transform3',<br>
&nbsp;&nbsp;&nbsp;&nbsp;'GeneralTransform3',<br>
&nbsp;&nbsp;&nbsp;&nbsp;'KinematicTransform3',<br>
&nbsp;&nbsp;&nbsp;&nbsp;'KinematicTransform3OneScrew',<br>
&nbsp;&nbsp;&nbsp;&nbsp;'Rotator3',<br>
&nbsp;&nbsp;&nbsp;&nbsp;'Actuator3',<br>
&nbsp;&nbsp;&nbsp;&nbsp;'KinematicChain3',<br>
&nbsp;&nbsp;&nbsp;&nbsp;'SymCondition',<br>
&nbsp;&nbsp;&nbsp;&nbsp;'ConditionCollection'<br>
]<br>
<!-- END SCAT CODE -->
</body>
</html>
