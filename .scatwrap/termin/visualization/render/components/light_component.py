<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/render/components/light_component.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
from&nbsp;__future__&nbsp;import&nbsp;annotations<br>
<br>
import&nbsp;numpy&nbsp;as&nbsp;np<br>
<br>
from&nbsp;termin.visualization.core.entity&nbsp;import&nbsp;Component<br>
from&nbsp;termin.visualization.core.lighting.light&nbsp;import&nbsp;LightType<br>
<br>
<br>
class&nbsp;LightComponent(Component):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;Простейший&nbsp;компонент&nbsp;источника&nbsp;света.<br>
&nbsp;&nbsp;&nbsp;&nbsp;Пока&nbsp;хранит&nbsp;только&nbsp;тип,&nbsp;цвет&nbsp;и&nbsp;интенсивность.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;light_type:&nbsp;LightType&nbsp;=&nbsp;LightType.DIRECTIONAL,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;color=(1.0,&nbsp;1.0,&nbsp;1.0),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;intensity:&nbsp;float&nbsp;=&nbsp;1.0,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;enabled:&nbsp;bool&nbsp;=&nbsp;True,<br>
&nbsp;&nbsp;&nbsp;&nbsp;):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;super().__init__(enabled=enabled)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.light_type&nbsp;=&nbsp;light_type<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.color&nbsp;=&nbsp;np.asarray(color,&nbsp;dtype=np.float32)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.intensity&nbsp;=&nbsp;float(intensity)<br>
<!-- END SCAT CODE -->
</body>
</html>
