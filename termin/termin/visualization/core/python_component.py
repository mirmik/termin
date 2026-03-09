# Forwarding to termin.scene (canonical location in termin-scene)
from termin.scene.python_component import PythonComponent, InputComponent

__all__ = ["PythonComponent", "InputComponent"]

# Register PythonComponent base class (can't use __init_subclass__ for itself)
from termin.inspect import InspectRegistry
from termin.scene import ComponentRegistry

InspectRegistry.instance().register_python_fields("PythonComponent", PythonComponent.inspect_fields)
ComponentRegistry.instance().register_python("PythonComponent", PythonComponent)
