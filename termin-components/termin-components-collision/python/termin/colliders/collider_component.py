# Re-export ColliderComponent from extracted collision-components module
from termin_nanobind.runtime import preload_sdk_libs

preload_sdk_libs("nanobind", "termin_components_collision")

from termin.colliders._components_collision_native import ColliderComponent

__all__ = ["ColliderComponent"]
