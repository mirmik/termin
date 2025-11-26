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
    &quot;&quot;&quot;<br>
    Полное состояние, никаких &quot;None&quot;.<br>
    Это &quot;каким хочешь видеть рендер сейчас&quot;.<br>
    &quot;&quot;&quot;<br>
    polygon_mode: str = &quot;fill&quot;     # fill / line<br>
    cull: bool = True<br>
    depth_test: bool = True<br>
    depth_write: bool = True<br>
    blend: bool = False<br>
    blend_src: str = &quot;src_alpha&quot;<br>
    blend_dst: str = &quot;one_minus_src_alpha&quot;<br>
<br>
<br>
@dataclass<br>
class RenderPass:<br>
    material: Material<br>
    state: RenderState = field(default_factory=RenderState)<br>
    phase: str = &quot;main&quot;<br>
    name: str = &quot;unnamed_pass&quot;<br>
<!-- END SCAT CODE -->
</body>
</html>
