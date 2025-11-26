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
    def wrapper(cls):<br>
        cls._serializable_fields = fields<br>
        COMPONENT_REGISTRY[cls.__name__] = cls<br>
        return cls<br>
    return wrapper<br>
<!-- END SCAT CODE -->
</body>
</html>
