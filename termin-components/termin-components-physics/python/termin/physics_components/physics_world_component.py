"""Canonical import for the native game physics world component."""

from termin_nanobind.runtime import preload_sdk_libs

preload_sdk_libs("nanobind", "termin_components_physics")

from ._components_physics_native import PhysicsWorldComponent

__all__ = ["PhysicsWorldComponent"]
