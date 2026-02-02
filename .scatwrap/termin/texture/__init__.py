<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/texture/__init__.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;Texture&nbsp;module&nbsp;for&nbsp;texture&nbsp;data&nbsp;handling.&quot;&quot;&quot;<br>
<br>
#&nbsp;Setup&nbsp;DLL&nbsp;paths&nbsp;before&nbsp;importing&nbsp;native&nbsp;extensions<br>
from&nbsp;termin&nbsp;import&nbsp;_dll_setup&nbsp;&nbsp;#&nbsp;noqa:&nbsp;F401<br>
<br>
from&nbsp;termin.texture._texture_native&nbsp;import&nbsp;(<br>
&nbsp;&nbsp;&nbsp;&nbsp;TcTexture,<br>
&nbsp;&nbsp;&nbsp;&nbsp;TcTexture,<br>
&nbsp;&nbsp;&nbsp;&nbsp;tc_texture_count,<br>
&nbsp;&nbsp;&nbsp;&nbsp;tc_texture_get_all_info,<br>
)<br>
<br>
__all__&nbsp;=&nbsp;[&quot;TcTexture&quot;,&nbsp;&quot;TcTexture&quot;,&nbsp;&quot;tc_texture_count&quot;,&nbsp;&quot;tc_texture_get_all_info&quot;]<br>
<!-- END SCAT CODE -->
</body>
</html>
