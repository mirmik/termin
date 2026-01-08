"""
Базовые геометрические классы (Geometric Base).

Содержит фундаментальные классы для представления геометрии:
- Pose2 - позы (положение + ориентация) в 2D пространстве
- Pose3 - позы (положение + ориентация) в 3D пространстве
- GeneralPose3 - позы с масштабированием
- Screw, Screw2, Screw3 - винтовые преобразования

Использует скомпилированный C++ модуль для Pose3, GeneralPose3 и связанных типов.
"""

# Setup DLL paths before importing native extensions
from termin import _dll_setup  # noqa: F401

# Import C++ native implementations
from ._geom_native import (
    Vec3,
    Vec4,
    Quat,
    Mat44,
    Pose3,
    GeneralPose3,
    GeneralTransform3,
    Screw3,
    AABB,
)

from .pose2 import Pose2
from .screw import Screw, Screw2
from .transform_aabb import TransformAABB
from termin.colliders._colliders_native import Ray3

__all__ = [
    'Vec3',
    'Vec4',
    'Quat',
    'Mat44',
    'Pose2',
    'Pose3',
    'GeneralPose3',
    'GeneralTransform3',
    'Screw',
    'Screw2',
    'Screw3',
    'AABB',
    'TransformAABB',
    'Ray3',
]
