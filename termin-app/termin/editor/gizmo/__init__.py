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

# Import from C++ native module
from termin._native.editor import (
    Gizmo,
    GizmoCollider,
    GizmoHit,
    GizmoManager,
    TransformGizmo,
    TransformElement,
)

# Python constraint and geometry types (for custom Python gizmos)
from termin.editor.gizmo.base import (
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

__all__ = [
    # Base (from C++)
    "Gizmo",
    "GizmoCollider",
    "GizmoHit",
    # Manager (from C++)
    "GizmoManager",
    # Transform (from C++)
    "TransformGizmo",
    "TransformElement",
    # Python constraint types (for custom gizmos)
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
]
