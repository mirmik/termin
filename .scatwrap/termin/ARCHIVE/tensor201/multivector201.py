<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/ARCHIVE/tensor201/multivector201.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
#!/usr/bin/env python3<br>
<br>
import torch<br>
<br>
geomproduct_left_operator_template = torch.tensor([<br>
&#9;[<br>
&#9;&#9;[1, 0, 0, 0, 0, 0, 0, 0],<br>
&#9;&#9;[0, 1, 0, 0, 0, 0, 0, 0],<br>
&#9;&#9;[0, 0, 1, 0, 0, 0, 0, 0],<br>
&#9;&#9;[0, 0, 0, 1, 0, 0, 0, 0],<br>
&#9;&#9;[0, 0, 0, 0, 1, 0, 0, 0],<br>
&#9;&#9;[0, 0, 0, 0, 0, 1, 0, 0],<br>
&#9;&#9;[0, 0, 0, -2, 0, 0, 1, 0],<br>
&#9;&#9;[0, 0, 0, 0, 0, 0, 0, 1],<br>
&#9;]<br>
])<br>
geomproduct_left_operator_sign = geomproduct_left_operator_template.sign()<br>
geomproduct_left_operator_indexes = geomproduct_left_operator_template.abs()<br>
<br>
<br>
def multivector(e=0, e1=0, e2=0, e3=0, e23=0, e31=0, e12=0, e321=0):<br>
&#9;return torch.tensor([e, e1, e2, e3, e23, e31, e12, e321])<br>
<br>
<br>
def vector(x, y, z=0):<br>
&#9;return multivector(e1=x, e2=y, e3=z)<br>
<br>
<br>
def realbivector(x, y):<br>
&#9;return multivector(e23=x, e31=y)<br>
<br>
<br>
def dualbivector(x, y):<br>
&#9;return multivector(e31=x, e32=y)<br>
<br>
<br>
def bivector(rx, ry, dx, dy):<br>
&#9;return realbivector(rx, ry) + dualbivector(dx, dy)<br>
<br>
<br>
def scalar(s):<br>
&#9;return multivector(e=s)<br>
<br>
<br>
def pseudoscalar(p):<br>
&#9;return multivector(e321=p)<br>
<br>
<br>
def geomproduct_left_operator(m):<br>
&#9;return m[geomproduct_left_operator_indexes] * geomproduct_left_operator_sign<br>
<br>
<br>
def geomprod(a, b):<br>
&#9;return geomproduct_left_operator(a) @ b<br>
<br>
<br>
#print(geomprod(vector(1, 4, 3), vector(1, 2, 3)))<br>
<br>
<br>
A = torch.tensor(<br>
&#9;[<br>
&#9;&#9;[<br>
&#9;&#9;&#9;[1, 0, 2],<br>
&#9;&#9;&#9;[0, 1, 0],<br>
&#9;&#9;&#9;[0, 0, 1]<br>
&#9;&#9;],<br>
&#9;&#9;[<br>
&#9;&#9;&#9;[1, 0, 0],<br>
&#9;&#9;&#9;[0, 0, 0],<br>
&#9;&#9;&#9;[0, 0, 0]<br>
&#9;&#9;],<br>
<br>
&#9;&#9;[<br>
&#9;&#9;&#9;[1, 0, 0],<br>
&#9;&#9;&#9;[0, 0, 0],<br>
&#9;&#9;&#9;[0, 0, 0]<br>
&#9;&#9;]<br>
&#9;],<br>
)<br>
<br>
print(A.shape)<br>
<br>
a = torch.tensor([<br>
&#9;[1, 1, 1],<br>
&#9;[0, 1, 0]<br>
])<br>
b = torch.tensor([<br>
&#9;[1, 1, 1],<br>
&#9;[10, 10, 10]<br>
]).permute(1, 0)<br>
<br>
print(&quot;a@A&quot;)<br>
print(a@A)<br>
print(&quot;A@b&quot;)<br>
print(A@b)<br>
print(&quot;a@A@b&quot;)<br>
print((a@A@b).permute(2, 1, 0))<br>
print((a@A@b).shape)<br>
<!-- END SCAT CODE -->
</body>
</html>
