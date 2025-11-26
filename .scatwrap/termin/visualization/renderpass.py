<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/renderpass.py</title>
</head>
<body>
<pre><code>
from dataclasses import dataclass, field
from termin.visualization.material import Material


@dataclass
class RenderState:
    &quot;&quot;&quot;
    Полное состояние, никаких &quot;None&quot;.
    Это &quot;каким хочешь видеть рендер сейчас&quot;.
    &quot;&quot;&quot;
    polygon_mode: str = &quot;fill&quot;     # fill / line
    cull: bool = True
    depth_test: bool = True
    depth_write: bool = True
    blend: bool = False
    blend_src: str = &quot;src_alpha&quot;
    blend_dst: str = &quot;one_minus_src_alpha&quot;


@dataclass
class RenderPass:
    material: Material
    state: RenderState = field(default_factory=RenderState)
    phase: str = &quot;main&quot;
    name: str = &quot;unnamed_pass&quot;
</code></pre>
</body>
</html>
