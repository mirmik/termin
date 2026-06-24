"""Lightweight builtin component specs owned by termin-components-kinematic."""

from __future__ import annotations

COMPONENT_SPECS: tuple[tuple[str, str], ...] = (
    ("termin.kinematic.kinematic_components", "ActuatorComponent"),
    ("termin.kinematic.kinematic_components", "RotatorComponent"),
)

__all__ = ["COMPONENT_SPECS"]
