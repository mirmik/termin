"""
Unified gizmo system for editor.

Provides a framework for interactive 3D widgets (gizmos) that:
- Draw themselves using immediate mode rendering
- Declare colliders for picking
- Receive events when interacted with

Core classes:
- Gizmo: Base class for all gizmos
- GizmoCollider: Collider geometry + drag constraint
- GizmoManager: Manages all gizmos, handles raycast and events
- TransformGizmo: Standard translate/rotate gizmo
"""

from termin.editor.gizmo.base import (
    Gizmo,
    GizmoCollider,
    DragConstraint,
    AxisConstraint,
    PlaneConstraint,
    AngleConstraint,
    RadiusConstraint,
    NoDrag,
    ColliderGeometry,
    SphereGeometry,
    CylinderGeometry,
    TorusGeometry,
    QuadGeometry,
)

from termin.editor.gizmo.manager import (
    GizmoManager,
    GizmoHit,
)

from termin.editor.gizmo.transform_gizmo import (
    TransformGizmo,
    TransformElement,
)

__all__ = [
    # Base
    "Gizmo",
    "GizmoCollider",
    "DragConstraint",
    "AxisConstraint",
    "PlaneConstraint",
    "AngleConstraint",
    "RadiusConstraint",
    "NoDrag",
    "ColliderGeometry",
    "SphereGeometry",
    "CylinderGeometry",
    "TorusGeometry",
    "QuadGeometry",
    # Manager
    "GizmoManager",
    "GizmoHit",
    # Transform
    "TransformGizmo",
    "TransformElement",
]
