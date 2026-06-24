"""Lightweight builtin component specs owned by termin-components-physics."""

from __future__ import annotations

COMPONENT_SPECS: tuple[tuple[str, str], ...] = (
    ("termin.physics_components.physics_world_component", "PhysicsWorldComponent"),
    ("termin.physics_components.rigid_body_component", "RigidBodyComponent"),
)

__all__ = ["COMPONENT_SPECS"]
