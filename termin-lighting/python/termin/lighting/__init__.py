"""Lighting primitives shared by rendering pipelines."""

from termin_nanobind.runtime import preload_sdk_libs

# _lighting_native has no extra C++ library dependencies beyond nanobind
# (Light/ShadowSettings/etc. are header-only struct types).
# This call only makes SDK discovery happen and registers Windows DLL
# directories; it is a no-op on Linux.
preload_sdk_libs()

from termin.lighting._lighting_native import (
    AttenuationCoefficients,
    Light,
    LightSample,
    LightShadowParams,
    LightType,
    ShadowSettings,
    light_type_from_value,
)

__all__ = [
    "AttenuationCoefficients",
    "Light",
    "LightSample",
    "LightShadowParams",
    "LightType",
    "ShadowSettings",
    "light_type_from_value",
]
