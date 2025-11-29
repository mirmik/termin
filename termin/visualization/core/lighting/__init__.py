"""Lighting primitives shared by rendering pipelines."""

from termin.visualization.core.lighting.attenuation import AttenuationCoefficients
from termin.visualization.core.lighting.light import Light, LightSample, LightShadowParams, LightType

__all__ = [
    "AttenuationCoefficients",
    "Light",
    "LightSample",
    "LightShadowParams",
    "LightType",
]
