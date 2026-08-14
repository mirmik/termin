"""
Unified gizmo system for editor.

Provides a framework for interactive 3D widgets (gizmos) that:
- Draw themselves using immediate mode rendering
- Declare colliders for picking
- Receive events when interacted with

Core classes:
- Gizmo: Base class for all gizmos
- GizmoCollider: Collider geometry + drag constraint
- GizmoVisualItem3D: retained overlay adapter owns picking and pointer routing
- TransformGizmo: Standard translate/rotate gizmo
"""

# Import from editor-private C++ native module
from termin.editor._editor_native import (
    Gizmo,
    GizmoCollider,
    TransformGizmo,
    TransformElement,
)

# Python constraint and geometry types (for custom Python gizmos)
from termin.editor_core.gizmo.base import (
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
