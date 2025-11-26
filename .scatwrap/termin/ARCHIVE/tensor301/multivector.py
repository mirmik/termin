<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/ARCHIVE/tensor301/multivector.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
import torch<br>
<br>
geomproduct_left_operator_indexes = [<br>
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],<br>
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],<br>
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],<br>
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],<br>
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],<br>
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],<br>
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],<br>
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],<br>
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],<br>
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],<br>
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],<br>
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],<br>
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],<br>
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],<br>
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],<br>
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],<br>
]<br>
<br>
<br>
def multivector(e=0, e1=0, e2=0, e3=0, e4=0, e23=0, e31=0, e12=0, e43=0, e42=0, e41=0, e321=0, e412=0, e431=0, e423=0, e1234=0):<br>
    return torch.tensor([e, e1, e2, e3, e4, e23, e31, e12, e43, e42, e41, e321, e412, e431, e423, e1234])<br>
<br>
<br>
def vector(x, y, z, w=0):<br>
    return multivector(e1=x, e2=y, e3=z, e4=w)<br>
<br>
<br>
def realbivector(x, y, z):<br>
    return multivector(e23=x, e31=y, e12=z)<br>
<br>
<br>
def dualbivector(x, y, z):<br>
    return multivector(e41=x, e42=y, e43=z)<br>
<br>
<br>
def bivector(rx, ry, rz, dx, dy, dz):<br>
    return realbivector(rx, ry, rz) + dualbivector(dx, dy, dz)<br>
<br>
<br>
def scalar(s):<br>
    return multivector(e=s)<br>
<br>
<br>
def pseudoscalar(p):<br>
    return multivector(e1234=p)<br>
<br>
<br>
def geomproduct_left_operator(m):<br>
<!-- END SCAT CODE -->
</body>
</html>
