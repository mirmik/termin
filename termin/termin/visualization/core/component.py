"""
Component re-exports.

The actual Component class comes from C++ (_entity_native).
PythonComponent and InputComponent are pure Python base classes.
"""

from termin.entity import Component, ComponentRegistry
from termin.visualization.core.python_component import PythonComponent, InputComponent
from termin.editor.inspect_field import InspectField

__all__ = ["Component", "PythonComponent", "InputComponent", "InspectField"]
