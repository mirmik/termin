"""Lighting setup utilities for rendering passes."""

from termin.visualization.render.lighting.setup import LightBudget, LightSetup
from termin.visualization.render.lighting.shading import blinn_phong_specular, fresnel_schlick, lambert_diffuse
from termin.visualization.render.lighting.upload import MAX_LIGHTS, upload_lights_to_shader, upload_ambient_to_shader

__all__ = [
    "LightBudget",
    "LightSetup",
    "MAX_LIGHTS",
    "upload_lights_to_shader",
    "upload_ambient_to_shader",
    "blinn_phong_specular",
    "fresnel_schlick",
    "lambert_diffuse",
]
