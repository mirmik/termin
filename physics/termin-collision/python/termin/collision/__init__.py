"""
Unified collision detection system.

Provides:
- BVH for broad-phase collision detection
- CollisionWorld for managing colliders and detecting contacts
- ContactPatch for solver-neutral contact geometry

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

from termin_nanobind.runtime import preload_sdk_libs

preload_sdk_libs("termin_collision")

from ._collision_native import (
    ContactFeaturePair,
    ContactCandidate,
    ContactPatch,
    RayHit,
    ColliderPair,
    BroadPhaseMode,
    CollisionDiagnostic,
    CollisionDiagnosticCode,
    BVH,
    CollisionWorld,
)

__all__ = [
    'ContactFeaturePair',
    'ContactCandidate',
    'ContactPatch',
    'RayHit',
    'ColliderPair',
    'BroadPhaseMode',
    'CollisionDiagnostic',
    'CollisionDiagnosticCode',
    'BVH',
    'CollisionWorld',
]
