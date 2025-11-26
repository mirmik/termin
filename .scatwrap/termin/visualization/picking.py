<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/picking.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
<br>
def&nbsp;hash_int(i):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;A&nbsp;simple&nbsp;integer&nbsp;hash&nbsp;function.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;i&nbsp;=&nbsp;((i&nbsp;&gt;&gt;&nbsp;16)&nbsp;^&nbsp;i)&nbsp;*&nbsp;0x45d9f3b<br>
&nbsp;&nbsp;&nbsp;&nbsp;i&nbsp;=&nbsp;((i&nbsp;&gt;&gt;&nbsp;16)&nbsp;^&nbsp;i)&nbsp;*&nbsp;0x45d9f3b<br>
&nbsp;&nbsp;&nbsp;&nbsp;i&nbsp;=&nbsp;(i&nbsp;&gt;&gt;&nbsp;16)&nbsp;^&nbsp;i<br>
&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;i<br>
<br>
id_by_rgb_cache&nbsp;=&nbsp;{}<br>
<br>
def&nbsp;id_to_rgb(in_pid:&nbsp;int):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;pack&nbsp;int&nbsp;id&nbsp;(1..16M)&nbsp;into&nbsp;RGB&nbsp;[0,1].&nbsp;0&nbsp;=&nbsp;'ничего&nbsp;не&nbsp;попали'.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;pid&nbsp;=&nbsp;hash_int(in_pid)&nbsp;#&nbsp;для&nbsp;пестроты&nbsp;картинки<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;r&nbsp;=&nbsp;(pid&nbsp;&amp;&nbsp;0x000000FF)&nbsp;/&nbsp;255.0<br>
&nbsp;&nbsp;&nbsp;&nbsp;g&nbsp;=&nbsp;((pid&nbsp;&amp;&nbsp;0x0000FF00)&nbsp;&gt;&gt;&nbsp;8)&nbsp;/&nbsp;255.0<br>
&nbsp;&nbsp;&nbsp;&nbsp;b&nbsp;=&nbsp;((pid&nbsp;&amp;&nbsp;0x00FF0000)&nbsp;&gt;&gt;&nbsp;16)&nbsp;/&nbsp;255.0<br>
&nbsp;&nbsp;&nbsp;&nbsp;#print(&quot;Converted&nbsp;id&quot;,&nbsp;pid,&nbsp;&quot;to&nbsp;color:&quot;,&nbsp;(r,&nbsp;g,&nbsp;b))&nbsp;&nbsp;#&nbsp;---&nbsp;DEBUG&nbsp;---<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;id_by_rgb_cache[(r,&nbsp;g,&nbsp;b)]&nbsp;=&nbsp;in_pid<br>
&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;(r,&nbsp;g,&nbsp;b)<br>
<br>
def&nbsp;rgb_to_id(r:&nbsp;float,&nbsp;g:&nbsp;float,&nbsp;b:&nbsp;float)&nbsp;-&gt;&nbsp;int:<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;ri&nbsp;=&nbsp;int(r&nbsp;*&nbsp;255&nbsp;+&nbsp;0.5)<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;gi&nbsp;=&nbsp;int(g&nbsp;*&nbsp;255&nbsp;+&nbsp;0.5)<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;bi&nbsp;=&nbsp;int(b&nbsp;*&nbsp;255&nbsp;+&nbsp;0.5)<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;#print(&quot;Converted&nbsp;color&quot;,&nbsp;(r,&nbsp;g,&nbsp;b),&nbsp;&quot;to&nbsp;id:&quot;,&nbsp;ri&nbsp;|&nbsp;(gi&nbsp;&lt;&lt;&nbsp;8)&nbsp;|&nbsp;(bi&nbsp;&lt;&lt;&nbsp;16))&nbsp;&nbsp;#&nbsp;---&nbsp;DEBUG&nbsp;---<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;return&nbsp;ri&nbsp;|&nbsp;(gi&nbsp;&lt;&lt;&nbsp;8)&nbsp;|&nbsp;(bi&nbsp;&lt;&lt;&nbsp;16)<br>
&nbsp;&nbsp;&nbsp;&nbsp;key&nbsp;=&nbsp;(r,&nbsp;g,&nbsp;b)<br>
&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;key&nbsp;in&nbsp;id_by_rgb_cache:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;id_by_rgb_cache[key]<br>
&nbsp;&nbsp;&nbsp;&nbsp;else:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;0<br>
<!-- END SCAT CODE -->
</body>
</html>
