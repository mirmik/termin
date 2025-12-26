"""
Модуль коллайдеров для обнаружения столкновений и вычисления расстояний.

Содержит:
- Базовый класс Collider
- Примитивные коллайдеры: SphereCollider, BoxCollider, CapsuleCollider
- AttachedCollider - коллайдер, прикрепленный к Pose3
- ColliderHit, RayHit - результаты запросов
"""

# Setup DLL paths before importing native extensions
from termin import _dll_setup  # noqa: F401

from ._colliders_native import (
    Collider,
    SphereCollider,
    BoxCollider,
    CapsuleCollider,
    AttachedCollider,
    UnionCollider,
    ColliderHit,
    RayHit,
    ColliderType,
    Ray3,
    # Ground contact helpers
    SphereGroundContact,
    BoxGroundContact,
    # Geometry primitives
    Sphere,
    Box,
    Capsule,
)

__all__ = [
    'Collider',
    'SphereCollider',
    'BoxCollider',
    'CapsuleCollider',
    'AttachedCollider',
    'UnionCollider',
    'ColliderHit',
    'RayHit',
    'ColliderType',
    'Ray3',
    'SphereGroundContact',
    'BoxGroundContact',
    'Sphere',
    'Box',
    'Capsule',
]
