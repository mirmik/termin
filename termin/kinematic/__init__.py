"""
Модуль кинематики и трансформаций.

Содержит классы для работы с:
- Трансформациями (Transform, Transform3)
- Кинематическими преобразованиями (Rotator3, Actuator3)
- Кинематическими цепями (KinematicChain3)
"""

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
