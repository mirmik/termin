"""Canonical animation component API."""

from termin import _dll_setup  # noqa: F401

# Make native modules accessible via termin.animation_components path
# (the .so files live under visualization/animation/ in the SDK)
_dll_setup.extend_package_path(__path__, "visualization", "animation")

from termin.animation_components._components_animation_native import AnimationPlayer

__all__ = ["AnimationPlayer"]
