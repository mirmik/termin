<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/render/renderpass.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
from&nbsp;dataclasses&nbsp;import&nbsp;dataclass,&nbsp;field<br>
from&nbsp;termin.visualization.core.material&nbsp;import&nbsp;Material<br>
<br>
<br>
@dataclass<br>
class&nbsp;RenderState:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;Полное&nbsp;состояние,&nbsp;никаких&nbsp;&quot;None&quot;.<br>
&nbsp;&nbsp;&nbsp;&nbsp;Это&nbsp;&quot;каким&nbsp;хочешь&nbsp;видеть&nbsp;рендер&nbsp;сейчас&quot;.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;polygon_mode:&nbsp;str&nbsp;=&nbsp;&quot;fill&quot;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;fill&nbsp;/&nbsp;line<br>
&nbsp;&nbsp;&nbsp;&nbsp;cull:&nbsp;bool&nbsp;=&nbsp;True<br>
&nbsp;&nbsp;&nbsp;&nbsp;depth_test:&nbsp;bool&nbsp;=&nbsp;True<br>
&nbsp;&nbsp;&nbsp;&nbsp;depth_write:&nbsp;bool&nbsp;=&nbsp;True<br>
&nbsp;&nbsp;&nbsp;&nbsp;blend:&nbsp;bool&nbsp;=&nbsp;False<br>
&nbsp;&nbsp;&nbsp;&nbsp;blend_src:&nbsp;str&nbsp;=&nbsp;&quot;src_alpha&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;blend_dst:&nbsp;str&nbsp;=&nbsp;&quot;one_minus_src_alpha&quot;<br>
<br>
<br>
@dataclass<br>
class&nbsp;RenderPass:<br>
&nbsp;&nbsp;&nbsp;&nbsp;material:&nbsp;Material<br>
&nbsp;&nbsp;&nbsp;&nbsp;state:&nbsp;RenderState&nbsp;=&nbsp;field(default_factory=RenderState)<br>
&nbsp;&nbsp;&nbsp;&nbsp;phase:&nbsp;str&nbsp;=&nbsp;&quot;main&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;name:&nbsp;str&nbsp;=&nbsp;&quot;unnamed_pass&quot;<br>
<!-- END SCAT CODE -->
</body>
</html>
