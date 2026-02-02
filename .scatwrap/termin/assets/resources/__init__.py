<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/assets/resources/__init__.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;ResourceManager&nbsp;package.<br>
<br>
This&nbsp;module&nbsp;provides&nbsp;the&nbsp;ResourceManager&nbsp;singleton&nbsp;for&nbsp;managing&nbsp;all&nbsp;resources:<br>
materials,&nbsp;meshes,&nbsp;textures,&nbsp;shaders,&nbsp;components,&nbsp;pipelines,&nbsp;etc.<br>
<br>
Usage:<br>
&nbsp;&nbsp;&nbsp;&nbsp;from&nbsp;termin.assets.resources&nbsp;import&nbsp;ResourceManager<br>
&nbsp;&nbsp;&nbsp;&nbsp;rm&nbsp;=&nbsp;ResourceManager.instance()<br>
&quot;&quot;&quot;<br>
<br>
from&nbsp;._handle_accessors&nbsp;import&nbsp;HandleAccessors<br>
from&nbsp;._manager&nbsp;import&nbsp;ResourceManager<br>
<br>
__all__&nbsp;=&nbsp;[&quot;ResourceManager&quot;,&nbsp;&quot;HandleAccessors&quot;]<br>
<!-- END SCAT CODE -->
</body>
</html>
