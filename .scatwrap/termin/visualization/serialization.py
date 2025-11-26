<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/serialization.py</title>
</head>
<body>
<pre><code>
# serialization.py

COMPONENT_REGISTRY = {}

def serializable(fields):
    def wrapper(cls):
        cls._serializable_fields = fields
        COMPONENT_REGISTRY[cls.__name__] = cls
        return cls
    return wrapper
</code></pre>
</body>
</html>
