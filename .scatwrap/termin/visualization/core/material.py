<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/core/material.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;Material&nbsp;and&nbsp;MaterialPhase&nbsp;-&nbsp;re-export&nbsp;from&nbsp;C++.<br>
<br>
TcMaterial&nbsp;is&nbsp;the&nbsp;C-based&nbsp;material&nbsp;system.<br>
Material&nbsp;and&nbsp;MaterialPhase&nbsp;are&nbsp;now&nbsp;aliases&nbsp;to&nbsp;TcMaterial/TcMaterialPhase.<br>
&quot;&quot;&quot;<br>
from&nbsp;termin._native.render&nbsp;import&nbsp;(<br>
&nbsp;&nbsp;&nbsp;&nbsp;TcMaterial,<br>
&nbsp;&nbsp;&nbsp;&nbsp;TcMaterialPhase,<br>
&nbsp;&nbsp;&nbsp;&nbsp;TcRenderState,<br>
)<br>
<br>
#&nbsp;Backwards&nbsp;compatibility&nbsp;aliases<br>
Material&nbsp;=&nbsp;TcMaterial<br>
MaterialPhase&nbsp;=&nbsp;TcMaterialPhase<br>
MaterialPhaseC&nbsp;=&nbsp;TcMaterialPhase<br>
<br>
__all__&nbsp;=&nbsp;[<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;TcMaterial&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;TcMaterialPhase&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;TcRenderState&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Aliases&nbsp;for&nbsp;backwards&nbsp;compatibility<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;Material&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;MaterialPhase&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;MaterialPhaseC&quot;,<br>
]<br>
<!-- END SCAT CODE -->
</body>
</html>
