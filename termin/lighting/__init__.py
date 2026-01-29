"""Lighting primitives shared by rendering pipelines."""

# Setup DLL paths before importing native extensions
from termin import _dll_setup  # noqa: F401

from termin.lighting._lighting_native import (
    AttenuationCoefficients,
    Light,
    LightComponent,
    LightSample,
    LightShadowParams,
    LightType,
    ShadowSettings,
    light_type_from_value,
)

__all__ = [
    "AttenuationCoefficients",
    "Light",
    "LightComponent",
    "LightSample",
    "LightShadowParams",
    "LightType",
    "ShadowSettings",
    "light_type_from_value",
]
