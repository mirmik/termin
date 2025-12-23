"""Lighting primitives shared by rendering pipelines."""

from termin.lighting._lighting_native import (
    AttenuationCoefficients,
    Light,
    LightSample,
    LightShadowParams,
    LightType,
)

__all__ = [
    "AttenuationCoefficients",
    "Light",
    "LightSample",
    "LightShadowParams",
    "LightType",
]
