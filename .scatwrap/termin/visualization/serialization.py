<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/serialization.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
# serialization.py<br>
<br>
COMPONENT_REGISTRY = {}<br>
<br>
def serializable(fields):<br>
&#9;def wrapper(cls):<br>
&#9;&#9;cls._serializable_fields = fields<br>
&#9;&#9;COMPONENT_REGISTRY[cls.__name__] = cls<br>
&#9;&#9;return cls<br>
&#9;return wrapper<br>
<!-- END SCAT CODE -->
</body>
</html>
