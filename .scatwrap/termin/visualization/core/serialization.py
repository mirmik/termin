<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/core/serialization.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
#&nbsp;serialization.py<br>
<br>
COMPONENT_REGISTRY&nbsp;=&nbsp;{}<br>
<br>
def&nbsp;serializable(fields):<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;wrapper(cls):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;cls._serializable_fields&nbsp;=&nbsp;fields<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;COMPONENT_REGISTRY[cls.__name__]&nbsp;=&nbsp;cls<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;cls<br>
&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;wrapper<br>
<!-- END SCAT CODE -->
</body>
</html>
