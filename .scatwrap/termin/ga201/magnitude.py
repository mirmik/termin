<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/ga201/magnitude.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
<br>
<br>
<br>
class&nbsp;Magnitude:<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(self,&nbsp;v,&nbsp;w):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.v&nbsp;=&nbsp;v<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.w&nbsp;=&nbsp;w<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__str__(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;str((self.v,&nbsp;self.w))<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;unitize(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;Magnitude(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.v&nbsp;/&nbsp;self.w,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;1<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;to_float(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;self.v&nbsp;/&nbsp;self.w<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__abs__(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;Magnitude(abs(self.v),&nbsp;abs(self.w))<br>
<!-- END SCAT CODE -->
</body>
</html>
