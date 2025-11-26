<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/picking.py</title>
</head>
<body>
<pre><code>

def hash_int(i):
    &quot;&quot;&quot;A simple integer hash function.&quot;&quot;&quot;
    i = ((i &gt;&gt; 16) ^ i) * 0x45d9f3b
    i = ((i &gt;&gt; 16) ^ i) * 0x45d9f3b
    i = (i &gt;&gt; 16) ^ i
    return i

id_by_rgb_cache = {}

def id_to_rgb(in_pid: int):
    &quot;&quot;&quot;pack int id (1..16M) into RGB [0,1]. 0 = 'ничего не попали'.&quot;&quot;&quot;
    pid = hash_int(in_pid) # для пестроты картинки

    r = (pid &amp; 0x000000FF) / 255.0
    g = ((pid &amp; 0x0000FF00) &gt;&gt; 8) / 255.0
    b = ((pid &amp; 0x00FF0000) &gt;&gt; 16) / 255.0
    #print(&quot;Converted id&quot;, pid, &quot;to color:&quot;, (r, g, b))  # --- DEBUG ---

    id_by_rgb_cache[(r, g, b)] = in_pid
    return (r, g, b)

def rgb_to_id(r: float, g: float, b: float) -&gt; int:
    # ri = int(r * 255 + 0.5)
    # gi = int(g * 255 + 0.5)
    # bi = int(b * 255 + 0.5)
    # #print(&quot;Converted color&quot;, (r, g, b), &quot;to id:&quot;, ri | (gi &lt;&lt; 8) | (bi &lt;&lt; 16))  # --- DEBUG ---
    # return ri | (gi &lt;&lt; 8) | (bi &lt;&lt; 16)
    key = (r, g, b)
    if key in id_by_rgb_cache:
        return id_by_rgb_cache[key]
    else:
        return 0

</code></pre>
</body>
</html>
