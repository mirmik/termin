"""Lighting primitives shared by rendering pipelines."""

from termin_nanobind.runtime import preload_sdk_libs

# _lighting_native wraps header-only lighting primitives and links only
# against SDK support libraries needed by the binding layer.
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
