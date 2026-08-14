"""Lightweight builtin component specs owned by termin-collision."""

from __future__ import annotations

COMPONENT_SPECS: tuple[tuple[str, str], ...] = (
    ("termin.colliders.collider_component", "ColliderComponent"),
    ("termin.colliders.teleport_component", "TeleportComponent"),
)

__all__ = ["COMPONENT_SPECS"]
