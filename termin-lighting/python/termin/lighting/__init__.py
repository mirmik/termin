"""Lighting primitives shared by rendering pipelines."""

from termin_nanobind.runtime import preload_sdk_libs

preload_sdk_libs("entity_lib")

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
