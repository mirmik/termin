<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/ARCHIVE/ga201_hide.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
#!/usr/bin/env&nbsp;python3<br>
<br>
import&nbsp;numpy<br>
<br>
class&nbsp;multivector:<br>
&nbsp;&nbsp;&nbsp;&nbsp;grade_dims&nbsp;=&nbsp;[1,&nbsp;3,&nbsp;3,&nbsp;1]<br>
&nbsp;&nbsp;&nbsp;&nbsp;exterior_dim&nbsp;=&nbsp;sum(grade_dims)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(self,&nbsp;array):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;len(array)&nbsp;!=&nbsp;self.exterior_dim:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;raise&nbsp;Exception(&quot;wrong&nbsp;dimension&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.array&nbsp;=&nbsp;array<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__add__(self,&nbsp;other):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;multivector(self.array&nbsp;+&nbsp;other.array)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__sub__(self,&nbsp;other):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;multivector(self.array&nbsp;-&nbsp;other.array)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;expand(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;A&nbsp;=&nbsp;self.array<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;A[0],&nbsp;A[1],&nbsp;A[2],&nbsp;A[3],&nbsp;A[4],&nbsp;A[5],&nbsp;A[6],&nbsp;A[7]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;to_left_prod_operator(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;a,&nbsp;a1,&nbsp;a2,&nbsp;a3,&nbsp;a12,&nbsp;a31,&nbsp;a23,&nbsp;a321&nbsp;=&nbsp;self.expand()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;numpy.array([<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#e&nbsp;&nbsp;&nbsp;&nbsp;#e1&nbsp;&nbsp;&nbsp;#e2&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#e3&nbsp;&nbsp;&nbsp;#e12&nbsp;&nbsp;#e31&nbsp;&nbsp;&nbsp;#e23&nbsp;&nbsp;&nbsp;#e321<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[&nbsp;&nbsp;&nbsp;a,&nbsp;&nbsp;&nbsp;&nbsp;a1,&nbsp;&nbsp;&nbsp;&nbsp;a2,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;0,&nbsp;&nbsp;-a12,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;0,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;0,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;0],&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[&nbsp;&nbsp;a1,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;a,&nbsp;&nbsp;&nbsp;a12,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;0,&nbsp;&nbsp;&nbsp;-a2,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;0,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;0,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;0],&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[&nbsp;&nbsp;a2,&nbsp;&nbsp;-a12,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;a,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;0,&nbsp;&nbsp;&nbsp;&nbsp;a1,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;0,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;0,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;0],&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[&nbsp;&nbsp;a3,&nbsp;&nbsp;&nbsp;a31,&nbsp;&nbsp;-a23,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;a,&nbsp;&nbsp;a321,&nbsp;&nbsp;&nbsp;-a1,&nbsp;&nbsp;&nbsp;&nbsp;a2,&nbsp;&nbsp;&nbsp;a12],&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[&nbsp;a12,&nbsp;&nbsp;&nbsp;-a2,&nbsp;&nbsp;&nbsp;&nbsp;a1,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;0,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;a,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;0,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;0,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;0],&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[&nbsp;a31,&nbsp;&nbsp;&nbsp;&nbsp;a3,&nbsp;-a321,&nbsp;&nbsp;&nbsp;&nbsp;-a1,&nbsp;&nbsp;&nbsp;a23,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;a,&nbsp;&nbsp;-a12,&nbsp;&nbsp;&nbsp;-a2],&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[&nbsp;a23,&nbsp;-a321,&nbsp;&nbsp;&nbsp;-a3,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;a2,&nbsp;&nbsp;-a31,&nbsp;&nbsp;&nbsp;a12,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;a,&nbsp;&nbsp;&nbsp;-a1],&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[a321,&nbsp;&nbsp;-a23,&nbsp;&nbsp;-a31,&nbsp;&nbsp;&nbsp;-a12,&nbsp;&nbsp;&nbsp;-a3,&nbsp;&nbsp;&nbsp;-a2,&nbsp;&nbsp;&nbsp;-a1,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;a]])<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__str__(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;str(self.array)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
<br>
if&nbsp;__name__&nbsp;==&nbsp;&quot;__main__&quot;:<br>
&nbsp;&nbsp;&nbsp;&nbsp;a&nbsp;=&nbsp;multivector(numpy.array([1,&nbsp;2,&nbsp;3,&nbsp;4,&nbsp;5,&nbsp;6,&nbsp;7,&nbsp;8]))<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;print(a.to_left_prod_operator()&nbsp;@&nbsp;a.array)<br>
&nbsp;&nbsp;&nbsp;&nbsp;print(a.expand())<br>
<!-- END SCAT CODE -->
</body>
</html>
