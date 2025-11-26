<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/picking.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
<br>
def hash_int(i):<br>
&#9;&quot;&quot;&quot;A simple integer hash function.&quot;&quot;&quot;<br>
&#9;i = ((i &gt;&gt; 16) ^ i) * 0x45d9f3b<br>
&#9;i = ((i &gt;&gt; 16) ^ i) * 0x45d9f3b<br>
&#9;i = (i &gt;&gt; 16) ^ i<br>
&#9;return i<br>
<br>
id_by_rgb_cache = {}<br>
<br>
def id_to_rgb(in_pid: int):<br>
&#9;&quot;&quot;&quot;pack int id (1..16M) into RGB [0,1]. 0 = 'ничего не попали'.&quot;&quot;&quot;<br>
&#9;pid = hash_int(in_pid) # для пестроты картинки<br>
<br>
&#9;r = (pid &amp; 0x000000FF) / 255.0<br>
&#9;g = ((pid &amp; 0x0000FF00) &gt;&gt; 8) / 255.0<br>
&#9;b = ((pid &amp; 0x00FF0000) &gt;&gt; 16) / 255.0<br>
&#9;#print(&quot;Converted id&quot;, pid, &quot;to color:&quot;, (r, g, b))  # --- DEBUG ---<br>
<br>
&#9;id_by_rgb_cache[(r, g, b)] = in_pid<br>
&#9;return (r, g, b)<br>
<br>
def rgb_to_id(r: float, g: float, b: float) -&gt; int:<br>
&#9;# ri = int(r * 255 + 0.5)<br>
&#9;# gi = int(g * 255 + 0.5)<br>
&#9;# bi = int(b * 255 + 0.5)<br>
&#9;# #print(&quot;Converted color&quot;, (r, g, b), &quot;to id:&quot;, ri | (gi &lt;&lt; 8) | (bi &lt;&lt; 16))  # --- DEBUG ---<br>
&#9;# return ri | (gi &lt;&lt; 8) | (bi &lt;&lt; 16)<br>
&#9;key = (r, g, b)<br>
&#9;if key in id_by_rgb_cache:<br>
&#9;&#9;return id_by_rgb_cache[key]<br>
&#9;else:<br>
&#9;&#9;return 0<br>
<!-- END SCAT CODE -->
</body>
</html>
