"""
Termin - библиотека для кинематики, динамики и мультифизического моделирования.

Основные модули:
- geombase - базовые геометрические классы (Pose3, Screw2, Screw3)
- kinematics - трансформации и кинематические цепи
- fem - метод конечных элементов для мультифизики
"""

# Setup DLL paths before importing native extensions
from termin import _dll_setup  # noqa: F401

# Базовая геометрия
from .geombase import Pose3, Screw2, Screw3

__version__ = '0.1.0'

__all__ = [
    # Geombase
    'Pose3',
    'Screw2',
    'Screw3',
]
