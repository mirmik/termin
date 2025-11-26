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
    &quot;&quot;&quot;A simple integer hash function.&quot;&quot;&quot;<br>
    i = ((i &gt;&gt; 16) ^ i) * 0x45d9f3b<br>
    i = ((i &gt;&gt; 16) ^ i) * 0x45d9f3b<br>
    i = (i &gt;&gt; 16) ^ i<br>
    return i<br>
<br>
id_by_rgb_cache = {}<br>
<br>
def id_to_rgb(in_pid: int):<br>
    &quot;&quot;&quot;pack int id (1..16M) into RGB [0,1]. 0 = 'ничего не попали'.&quot;&quot;&quot;<br>
    pid = hash_int(in_pid) # для пестроты картинки<br>
<br>
    r = (pid &amp; 0x000000FF) / 255.0<br>
    g = ((pid &amp; 0x0000FF00) &gt;&gt; 8) / 255.0<br>
    b = ((pid &amp; 0x00FF0000) &gt;&gt; 16) / 255.0<br>
    #print(&quot;Converted id&quot;, pid, &quot;to color:&quot;, (r, g, b))  # --- DEBUG ---<br>
<br>
    id_by_rgb_cache[(r, g, b)] = in_pid<br>
    return (r, g, b)<br>
<br>
def rgb_to_id(r: float, g: float, b: float) -&gt; int:<br>
    # ri = int(r * 255 + 0.5)<br>
    # gi = int(g * 255 + 0.5)<br>
    # bi = int(b * 255 + 0.5)<br>
    # #print(&quot;Converted color&quot;, (r, g, b), &quot;to id:&quot;, ri | (gi &lt;&lt; 8) | (bi &lt;&lt; 16))  # --- DEBUG ---<br>
    # return ri | (gi &lt;&lt; 8) | (bi &lt;&lt; 16)<br>
    key = (r, g, b)<br>
    if key in id_by_rgb_cache:<br>
        return id_by_rgb_cache[key]<br>
    else:<br>
        return 0<br>
<!-- END SCAT CODE -->
</body>
</html>
