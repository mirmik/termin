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

import os as _os
_sdk_dir = _os.path.join(_os.sep, "opt", "termin", "lib", "python", "termin", "colliders")
if _os.path.isdir(_sdk_dir) and _sdk_dir not in __path__:
    __path__.append(_sdk_dir)

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
