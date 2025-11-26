<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/barrier.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
#/usr/bin/env python3<br>
<br>
import math<br>
<br>
def shotki_barrier(b, l):<br>
&#9;def func(x):<br>
&#9;&#9;if x &gt;= l: <br>
&#9;&#9;&#9;return 0<br>
&#9;&#9;return b/x + b*x/(l**2) - 2*b/l<br>
&#9;return func<br>
<br>
def alpha_function(l, k):<br>
&#9;l2 = l * k<br>
&#9;a = 1/(k-1)/l<br>
&#9;b = - 1/(k-1)<br>
&#9;def func(x):<br>
&#9;&#9;if x &gt; l: <br>
&#9;&#9;&#9;return 0<br>
&#9;&#9;elif x &lt; l2:<br>
&#9;&#9;&#9;return 1<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;return a*x+b<br>
&#9;return func<br>
<br>
&#9;&#9;<br>
<!-- END SCAT CODE -->
</body>
</html>
