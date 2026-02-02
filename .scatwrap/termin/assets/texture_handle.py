<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/assets/texture_handle.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;TextureHandle&nbsp;-&nbsp;re-export&nbsp;from&nbsp;C++.&quot;&quot;&quot;<br>
from&nbsp;termin._native.assets&nbsp;import&nbsp;TextureHandle<br>
<br>
#&nbsp;Singleton&nbsp;for&nbsp;white&nbsp;texture&nbsp;handle<br>
_white_texture_handle:&nbsp;TextureHandle&nbsp;|&nbsp;None&nbsp;=&nbsp;None<br>
<br>
#&nbsp;Singleton&nbsp;for&nbsp;normal&nbsp;texture&nbsp;handle<br>
_normal_texture_handle:&nbsp;TextureHandle&nbsp;|&nbsp;None&nbsp;=&nbsp;None<br>
<br>
<br>
def&nbsp;get_white_texture_handle()&nbsp;-&gt;&nbsp;TextureHandle:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Return&nbsp;a&nbsp;TextureHandle&nbsp;for&nbsp;the&nbsp;white&nbsp;1x1&nbsp;texture&nbsp;singleton.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;global&nbsp;_white_texture_handle<br>
&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;_white_texture_handle&nbsp;is&nbsp;None:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;from&nbsp;termin.visualization.render.texture&nbsp;import&nbsp;get_white_texture<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;white_tex&nbsp;=&nbsp;get_white_texture()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;_white_texture_handle&nbsp;=&nbsp;white_tex._handle<br>
&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;_white_texture_handle<br>
<br>
<br>
def&nbsp;get_normal_texture_handle()&nbsp;-&gt;&nbsp;TextureHandle:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Return&nbsp;a&nbsp;TextureHandle&nbsp;for&nbsp;the&nbsp;flat&nbsp;normal&nbsp;1x1&nbsp;texture&nbsp;singleton.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;global&nbsp;_normal_texture_handle<br>
&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;_normal_texture_handle&nbsp;is&nbsp;None:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;from&nbsp;termin.visualization.render.texture&nbsp;import&nbsp;get_normal_texture<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;normal_tex&nbsp;=&nbsp;get_normal_texture()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;_normal_texture_handle&nbsp;=&nbsp;normal_tex._handle<br>
&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;_normal_texture_handle<br>
<br>
<br>
__all__&nbsp;=&nbsp;[&quot;TextureHandle&quot;,&nbsp;&quot;get_white_texture_handle&quot;,&nbsp;&quot;get_normal_texture_handle&quot;]<br>
<!-- END SCAT CODE -->
</body>
</html>
