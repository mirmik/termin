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
    def func(x):<br>
        if x &gt;= l: <br>
            return 0<br>
        return b/x + b*x/(l**2) - 2*b/l<br>
    return func<br>
<br>
def alpha_function(l, k):<br>
    l2 = l * k<br>
    a = 1/(k-1)/l<br>
    b = - 1/(k-1)<br>
    def func(x):<br>
        if x &gt; l: <br>
            return 0<br>
        elif x &lt; l2:<br>
            return 1<br>
        else:<br>
            return a*x+b<br>
    return func<br>
<br>
        <br>
<!-- END SCAT CODE -->
</body>
</html>
