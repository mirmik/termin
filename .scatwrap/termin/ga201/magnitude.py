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
class Magnitude:<br>
&#9;def __init__(self, v, w):<br>
&#9;&#9;self.v = v<br>
&#9;&#9;self.w = w<br>
<br>
&#9;def __str__(self):<br>
&#9;&#9;return str((self.v, self.w))<br>
<br>
&#9;def unitize(self):<br>
&#9;&#9;return Magnitude(<br>
&#9;&#9;&#9;self.v / self.w,<br>
&#9;&#9;&#9;1<br>
&#9;&#9;)<br>
<br>
&#9;def to_float(self):<br>
&#9;&#9;return self.v / self.w<br>
<br>
&#9;def __abs__(self):<br>
&#9;&#9;return Magnitude(abs(self.v), abs(self.w))<br>
<!-- END SCAT CODE -->
</body>
</html>
