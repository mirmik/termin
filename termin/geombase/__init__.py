"""
Базовые геометрические классы (Geometric Base).

Содержит фундаментальные классы для представления геометрии:
- Pose2 - позы (положение + ориентация) в 2D пространстве
- Pose3 - позы (положение + ориентация) в 3D пространстве
- Screw, Screw2, Screw3 - винтовые преобразования

При наличии скомпилированного C++ модуля использует его для ускорения.
"""

# Try to import C++ native implementations
try:
    from ._geom_native import Vec3, Quat, Pose3 as Pose3Native, Screw3 as Screw3Native
    _HAS_NATIVE = True
except ImportError:
    _HAS_NATIVE = False

from .pose2 import Pose2
from .pose3 import Pose3
from .general_pose3 import GeneralPose3
from .screw import Screw, Screw2, Screw3
from .aabb import AABB, TransformAABB

__all__ = [
    'Pose2',
    'Pose3',
    'GeneralPose3',
    'Screw',
    'Screw2',
    'Screw3',
    'AABB',
    'TransformAABB',
]

if _HAS_NATIVE:
    __all__.extend(['Vec3', 'Quat', 'Pose3Native', 'Screw3Native'])
