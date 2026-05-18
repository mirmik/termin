"""
Component re-exports.

The actual Component class comes from termin.scene.
PythonComponent and InputComponent are pure Python base classes.
"""

from termin.scene import Component, ComponentRegistry
from termin.visualization.core.python_component import PythonComponent, InputComponent
from termin.inspect import InspectField

__all__ = ["Component", "PythonComponent", "InputComponent", "InspectField"]
