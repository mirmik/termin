<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/render/immediate.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;<br>
ImmediateRenderer&nbsp;-&nbsp;immediate&nbsp;mode&nbsp;rendering&nbsp;for&nbsp;debug&nbsp;visualization,&nbsp;gizmos,&nbsp;etc.<br>
<br>
Implemented&nbsp;in&nbsp;C++&nbsp;for&nbsp;performance.&nbsp;This&nbsp;module&nbsp;re-exports&nbsp;from&nbsp;native.<br>
&quot;&quot;&quot;<br>
<br>
from&nbsp;termin._native.render&nbsp;import&nbsp;ImmediateRenderer&nbsp;as&nbsp;_ImmediateRenderer<br>
<br>
<br>
class&nbsp;ImmediateRenderer(_ImmediateRenderer):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;Singleton&nbsp;wrapper&nbsp;around&nbsp;native&nbsp;ImmediateRenderer.<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;Позволяет&nbsp;вызывать&nbsp;из&nbsp;любого&nbsp;компонента:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;from&nbsp;termin.visualization.render.immediate&nbsp;import&nbsp;ImmediateRenderer<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;ImmediateRenderer.instance().line(start,&nbsp;end,&nbsp;color)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;_instance:&nbsp;&quot;ImmediateRenderer&nbsp;|&nbsp;None&quot;&nbsp;=&nbsp;None<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;super().__init__()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;ImmediateRenderer._instance&nbsp;=&nbsp;self<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;@classmethod<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;instance(cls)&nbsp;-&gt;&nbsp;&quot;ImmediateRenderer&quot;:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Получить&nbsp;глобальный&nbsp;экземпляр&nbsp;(создаёт&nbsp;если&nbsp;не&nbsp;существует).&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;cls._instance&nbsp;is&nbsp;None:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;cls._instance&nbsp;=&nbsp;cls()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;cls._instance<br>
<br>
<br>
__all__&nbsp;=&nbsp;[&quot;ImmediateRenderer&quot;]<br>
<!-- END SCAT CODE -->
</body>
</html>
