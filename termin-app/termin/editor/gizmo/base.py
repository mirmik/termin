"""Compatibility wrapper for Python gizmo helper types."""

from termin.editor_core.gizmo.base import (
    AngleConstraint,
    AxisConstraint,
    ColliderGeometry,
    CylinderGeometry,
    DragConstraint,
    GizmoCollider,
    NoDrag,
    PlaneConstraint,
    QuadGeometry,
    RadiusConstraint,
    SphereGeometry,
    TorusGeometry,
)

__all__ = [
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
    "GizmoCollider",
]
