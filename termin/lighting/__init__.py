"""Lighting primitives shared by rendering pipelines."""

# Setup DLL paths before importing native extensions
from termin import _dll_setup  # noqa: F401

import os as _os
_sdk_dir = _os.path.join(_os.sep, "opt", "termin", "lib", "python", "termin", "lighting")
if _os.path.isdir(_sdk_dir) and _sdk_dir not in __path__:
    __path__.append(_sdk_dir)

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
