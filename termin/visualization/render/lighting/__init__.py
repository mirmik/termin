"""Lighting setup utilities for rendering passes."""

from termin.visualization.render.lighting.setup import LightBudget, LightSetup
from termin.visualization.render.lighting.shading import blinn_phong_specular, fresnel_schlick, lambert_diffuse

__all__ = [
    "LightBudget",
    "LightSetup",
    "blinn_phong_specular",
    "fresnel_schlick",
    "lambert_diffuse",
]
