<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/renderpass.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
from dataclasses import dataclass, field<br>
from termin.visualization.material import Material<br>
<br>
<br>
@dataclass<br>
class RenderState:<br>
&#9;&quot;&quot;&quot;<br>
&#9;Полное состояние, никаких &quot;None&quot;.<br>
&#9;Это &quot;каким хочешь видеть рендер сейчас&quot;.<br>
&#9;&quot;&quot;&quot;<br>
&#9;polygon_mode: str = &quot;fill&quot;     # fill / line<br>
&#9;cull: bool = True<br>
&#9;depth_test: bool = True<br>
&#9;depth_write: bool = True<br>
&#9;blend: bool = False<br>
&#9;blend_src: str = &quot;src_alpha&quot;<br>
&#9;blend_dst: str = &quot;one_minus_src_alpha&quot;<br>
<br>
<br>
@dataclass<br>
class RenderPass:<br>
&#9;material: Material<br>
&#9;state: RenderState = field(default_factory=RenderState)<br>
&#9;phase: str = &quot;main&quot;<br>
&#9;name: str = &quot;unnamed_pass&quot;<br>
<!-- END SCAT CODE -->
</body>
</html>
