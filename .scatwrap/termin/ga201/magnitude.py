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
    def __init__(self, v, w):<br>
        self.v = v<br>
        self.w = w<br>
<br>
    def __str__(self):<br>
        return str((self.v, self.w))<br>
<br>
    def unitize(self):<br>
        return Magnitude(<br>
            self.v / self.w,<br>
            1<br>
        )<br>
<br>
    def to_float(self):<br>
        return self.v / self.w<br>
<br>
    def __abs__(self):<br>
        return Magnitude(abs(self.v), abs(self.w))<br>
<!-- END SCAT CODE -->
</body>
</html>
