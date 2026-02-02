<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/ga201/line.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
import&nbsp;termin.ga201.point&nbsp;as&nbsp;point<br>
import&nbsp;termin.ga201.join&nbsp;as&nbsp;join<br>
<br>
<br>
class&nbsp;Line2:<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(self,&nbsp;x,&nbsp;y,&nbsp;z):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;n&nbsp;=&nbsp;(x*x&nbsp;+&nbsp;y*y)**0.5<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.x&nbsp;=&nbsp;x&nbsp;/&nbsp;n<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.y&nbsp;=&nbsp;y&nbsp;/&nbsp;n<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.z&nbsp;=&nbsp;z&nbsp;/&nbsp;n<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__str__(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;str((self.x,&nbsp;self.y,&nbsp;self.z))<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__repr__(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;str(self)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;bulk_norm(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;(self.x*self.x&nbsp;+&nbsp;self.y*self.y)**0.5<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;parameter_point(self,&nbsp;t):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;n&nbsp;=&nbsp;self.bulk_norm()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;dir_y&nbsp;=&nbsp;self.x&nbsp;/&nbsp;n<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;dir_x&nbsp;=&nbsp;-self.y&nbsp;/&nbsp;n<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;origin&nbsp;=&nbsp;point.origin()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;c&nbsp;=&nbsp;join.projection_point_line(origin,&nbsp;self).unitized()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;point.Point2(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;c.x&nbsp;+&nbsp;dir_x&nbsp;*&nbsp;t,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;c.y&nbsp;+&nbsp;dir_y&nbsp;*&nbsp;t<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;unitized(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;x,&nbsp;y&nbsp;=&nbsp;self.x,&nbsp;self.y<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;n&nbsp;=&nbsp;(x*x&nbsp;+&nbsp;y*y)**0.5<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;Line2(self.x/n,&nbsp;self.y/n,&nbsp;self.z/n)<br>
<!-- END SCAT CODE -->
</body>
</html>
