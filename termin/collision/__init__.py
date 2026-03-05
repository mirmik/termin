"""
Unified collision detection system.

Provides:
- BVH for broad-phase collision detection
- CollisionWorld for managing colliders and detecting contacts
- ContactManifold for unified contact representation

Usage:
    from termin.collision import CollisionWorld
    from termin.colliders import SphereCollider, BoxCollider

    world = CollisionWorld()
    world.add(sphere)
    world.add(box)

    # After moving objects:
    world.update_pose(sphere)

    # Detect all contacts:
    manifolds = world.detect_contacts()

    # Raycast:
    hit = world.raycast_closest(ray)
"""

# Setup DLL paths before importing native extensions
from termin import _dll_setup  # noqa: F401

import os as _os
_sdk_dir = _os.path.join(_os.sep, "opt", "termin", "lib", "python", "termin", "collision")
if _os.path.isdir(_sdk_dir) and _sdk_dir not in __path__:
    __path__.append(_sdk_dir)

from ._collision_native import (
    ContactID,
    ContactPoint,
    ContactManifold,
    RayHit,
    ColliderPair,
    BVH,
    CollisionWorld,
)

__all__ = [
    'ContactID',
    'ContactPoint',
    'ContactManifold',
    'RayHit',
    'ColliderPair',
    'BVH',
    'CollisionWorld',
]
