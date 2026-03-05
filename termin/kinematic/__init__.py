"""
Модуль кинематики и трансформаций.

Содержит классы для работы с:
- Трансформациями (Transform, Transform3)
- Кинематическими преобразованиями (Rotator3, Actuator3)
- Кинематическими цепями (KinematicChain3)
"""

import os as _os
_sdk_dir = _os.path.join(_os.sep, "opt", "termin", "lib", "python", "termin", "kinematic")
if _os.path.isdir(_sdk_dir) and _sdk_dir not in __path__:
    __path__.append(_sdk_dir)

from .transform import Transform, Transform3
from .general_transform import GeneralTransform3
from .kinematic import (
    KinematicTransform3,
    KinematicTransform3OneScrew,
    Rotator3,
    Actuator3
)
from .kinchain import KinematicChain3
from .conditions import SymCondition, ConditionCollection

__all__ = [
    'Transform',
    'Transform3',
    'GeneralTransform3',
    'KinematicTransform3',
    'KinematicTransform3OneScrew',
    'Rotator3',
    'Actuator3',
    'KinematicChain3',
    'SymCondition',
    'ConditionCollection'
]
