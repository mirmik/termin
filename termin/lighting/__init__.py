"""Lighting primitives shared by rendering pipelines."""

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
