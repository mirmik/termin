<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>examples/project/Scripts/tween_test.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;<br>
TweenTest.py&nbsp;component.<br>
&quot;&quot;&quot;<br>
<br>
from&nbsp;__future__&nbsp;import&nbsp;annotations<br>
<br>
from&nbsp;termin.visualization.core.component&nbsp;import&nbsp;PythonComponent<br>
from&nbsp;termin.visualization.core.scene&nbsp;import&nbsp;get_current_scene<br>
from&nbsp;termin.geombase&nbsp;import&nbsp;Vec3<br>
from&nbsp;termin.tween.ease&nbsp;import&nbsp;Ease<br>
<br>
<br>
class&nbsp;TweenTest(PythonComponent):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;Custom&nbsp;component.<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;Attributes:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;speed:&nbsp;Movement&nbsp;speed.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(self,&nbsp;speed:&nbsp;float&nbsp;=&nbsp;1.0):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;super().__init__()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.speed&nbsp;=&nbsp;speed<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.tween_manager&nbsp;=&nbsp;None&nbsp;&nbsp;#&nbsp;Placeholder&nbsp;for&nbsp;a&nbsp;tween&nbsp;manager<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;start(self)&nbsp;-&gt;&nbsp;None:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Called&nbsp;when&nbsp;the&nbsp;component&nbsp;is&nbsp;first&nbsp;activated.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;scene&nbsp;=&nbsp;get_current_scene()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.tween_manager&nbsp;=&nbsp;scene.find_component_by_name(&quot;TweenManagerComponent&quot;)&nbsp;if&nbsp;scene&nbsp;else&nbsp;None<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;self.tween_manager&nbsp;is&nbsp;None:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;target&nbsp;=&nbsp;self.entity.transform.local_pose().lin&nbsp;+&nbsp;Vec3(0,&nbsp;0,&nbsp;5)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.tween_manager.move(self.entity.transform,&nbsp;target,&nbsp;5.0,&nbsp;ease=Ease.IN_OUT_QUAD)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;update(self,&nbsp;dt:&nbsp;float)&nbsp;-&gt;&nbsp;None:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;pass<br>
<!-- END SCAT CODE -->
</body>
</html>
