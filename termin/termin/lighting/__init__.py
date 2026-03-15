"""Lighting primitives shared by rendering pipelines."""

# Setup DLL paths before importing native extensions
from termin import _dll_setup  # noqa: F401

_dll_setup.extend_package_path(__path__, "lighting")

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
