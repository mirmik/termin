"""
Termin - библиотека для кинематики, динамики и мультифизического моделирования.

Основные модули:
- geombase - базовые геометрические классы (Pose3, Screw2, Screw3)
- kinematics - трансформации и кинематические цепи
- fem - метод конечных элементов для мультифизики
"""

# Add DLL search path on Windows (for entity_lib.dll, trent.dll, etc.)
import os
import sys
if sys.platform == "win32":
    _dll_dir = os.path.dirname(os.path.abspath(__file__))
    if hasattr(os, "add_dll_directory"):
        os.add_dll_directory(_dll_dir)
    # Also add to PATH for older Python versions
    os.environ["PATH"] = _dll_dir + os.pathsep + os.environ.get("PATH", "")

# Базовая геометрия
from .geombase import Pose3, Screw2, Screw3

__version__ = '0.1.0'

__all__ = [
    # Geombase
    'Pose3',
    'Screw2',
    'Screw3',
]
