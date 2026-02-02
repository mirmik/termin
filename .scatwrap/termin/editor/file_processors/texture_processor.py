<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/editor/file_processors/texture_processor.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;Texture&nbsp;file&nbsp;pre-loader&nbsp;for&nbsp;image&nbsp;files.&quot;&quot;&quot;<br>
<br>
from&nbsp;__future__&nbsp;import&nbsp;annotations<br>
<br>
from&nbsp;typing&nbsp;import&nbsp;Set<br>
<br>
from&nbsp;termin.editor.project_file_watcher&nbsp;import&nbsp;FilePreLoader,&nbsp;PreLoadResult<br>
<br>
<br>
class&nbsp;TexturePreLoader(FilePreLoader):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Pre-loads&nbsp;texture&nbsp;files&nbsp;-&nbsp;reads&nbsp;content&nbsp;and&nbsp;UUID&nbsp;from&nbsp;spec.&quot;&quot;&quot;<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;@property<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;priority(self)&nbsp;-&gt;&nbsp;int:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;10&nbsp;&nbsp;#&nbsp;Textures&nbsp;have&nbsp;no&nbsp;dependencies<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;@property<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;extensions(self)&nbsp;-&gt;&nbsp;Set[str]:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;{&quot;.png&quot;,&nbsp;&quot;.jpg&quot;,&nbsp;&quot;.jpeg&quot;,&nbsp;&quot;.tga&quot;,&nbsp;&quot;.bmp&quot;}<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;@property<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;resource_type(self)&nbsp;-&gt;&nbsp;str:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;&quot;texture&quot;<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;preload(self,&nbsp;path:&nbsp;str)&nbsp;-&gt;&nbsp;PreLoadResult&nbsp;|&nbsp;None:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Pre-load&nbsp;texture&nbsp;file:&nbsp;only&nbsp;read&nbsp;UUID&nbsp;from&nbsp;spec&nbsp;(lazy&nbsp;loading).<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Read&nbsp;spec&nbsp;file&nbsp;(may&nbsp;contain&nbsp;uuid,&nbsp;flip_x,&nbsp;flip_y,&nbsp;transpose)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;spec_data&nbsp;=&nbsp;self.read_spec_file(path)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;uuid&nbsp;=&nbsp;spec_data.get(&quot;uuid&quot;)&nbsp;if&nbsp;spec_data&nbsp;else&nbsp;None<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;PreLoadResult(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;resource_type=self.resource_type,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;path=path,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;content=None,&nbsp;&nbsp;#&nbsp;Lazy&nbsp;loading&nbsp;-&nbsp;don't&nbsp;read&nbsp;content<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;uuid=uuid,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;spec_data=spec_data,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;)<br>
<br>
<br>
#&nbsp;Backward&nbsp;compatibility&nbsp;alias<br>
TextureFileProcessor&nbsp;=&nbsp;TexturePreLoader<br>
<!-- END SCAT CODE -->
</body>
</html>
