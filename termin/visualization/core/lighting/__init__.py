"""Lighting primitives shared by rendering pipelines."""

try:
    from termin.visualization.core.lighting._lighting_native import (
        AttenuationCoefficients,
        Light,
        LightSample,
        LightShadowParams,
        LightType,
    )
except ImportError:
    from termin.visualization.core.lighting.attenuation import AttenuationCoefficients
    from termin.visualization.core.lighting.light import (
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
