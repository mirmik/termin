<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/core/picking.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
#&nbsp;picking.py&nbsp;-&nbsp;Entity&nbsp;picking&nbsp;utilities<br>
#&nbsp;Uses&nbsp;C&nbsp;API&nbsp;for&nbsp;id&lt;-&gt;rgb&nbsp;conversion&nbsp;to&nbsp;ensure&nbsp;consistency&nbsp;with&nbsp;C++&nbsp;rendering<br>
<br>
from&nbsp;termin._native&nbsp;import&nbsp;tc_picking_id_to_rgb,&nbsp;tc_picking_rgb_to_id,&nbsp;tc_picking_cache_clear<br>
<br>
def&nbsp;id_to_rgb(in_pid:&nbsp;int):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Convert&nbsp;entity&nbsp;pick&nbsp;ID&nbsp;to&nbsp;RGB&nbsp;tuple&nbsp;(0.0-1.0&nbsp;range).<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;Also&nbsp;caches&nbsp;the&nbsp;mapping&nbsp;for&nbsp;reverse&nbsp;lookup&nbsp;via&nbsp;rgb_to_id.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;r,&nbsp;g,&nbsp;b&nbsp;=&nbsp;tc_picking_id_to_rgb(in_pid)<br>
&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;(r&nbsp;/&nbsp;255.0,&nbsp;g&nbsp;/&nbsp;255.0,&nbsp;b&nbsp;/&nbsp;255.0)<br>
<br>
def&nbsp;rgb_to_id(r:&nbsp;float,&nbsp;g:&nbsp;float,&nbsp;b:&nbsp;float)&nbsp;-&gt;&nbsp;int:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Convert&nbsp;RGB&nbsp;color&nbsp;back&nbsp;to&nbsp;entity&nbsp;pick&nbsp;ID.<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;Returns&nbsp;0&nbsp;if&nbsp;not&nbsp;found&nbsp;in&nbsp;cache.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;r_int&nbsp;=&nbsp;int(round(r&nbsp;*&nbsp;255.0))<br>
&nbsp;&nbsp;&nbsp;&nbsp;g_int&nbsp;=&nbsp;int(round(g&nbsp;*&nbsp;255.0))<br>
&nbsp;&nbsp;&nbsp;&nbsp;b_int&nbsp;=&nbsp;int(round(b&nbsp;*&nbsp;255.0))<br>
&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;tc_picking_rgb_to_id(r_int,&nbsp;g_int,&nbsp;b_int)<br>
<br>
def&nbsp;clear_cache():<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Clear&nbsp;the&nbsp;picking&nbsp;cache.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;tc_picking_cache_clear()<br>
<!-- END SCAT CODE -->
</body>
</html>
