<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/barrier.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
#/usr/bin/env&nbsp;python3<br>
<br>
import&nbsp;math<br>
<br>
def&nbsp;shotki_barrier(b,&nbsp;l):<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;func(x):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;x&nbsp;&gt;=&nbsp;l:&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;0<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;b/x&nbsp;+&nbsp;b*x/(l**2)&nbsp;-&nbsp;2*b/l<br>
&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;func<br>
<br>
def&nbsp;alpha_function(l,&nbsp;k):<br>
&nbsp;&nbsp;&nbsp;&nbsp;l2&nbsp;=&nbsp;l&nbsp;*&nbsp;k<br>
&nbsp;&nbsp;&nbsp;&nbsp;a&nbsp;=&nbsp;1/(k-1)/l<br>
&nbsp;&nbsp;&nbsp;&nbsp;b&nbsp;=&nbsp;-&nbsp;1/(k-1)<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;func(x):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;x&nbsp;&gt;&nbsp;l:&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;0<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;elif&nbsp;x&nbsp;&lt;&nbsp;l2:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;1<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;else:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;a*x+b<br>
&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;func<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
<!-- END SCAT CODE -->
</body>
</html>
