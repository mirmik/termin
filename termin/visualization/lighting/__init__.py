"""Примитивы света, модели затухания и вспомогательные функции освещения."""

from .attenuation import AttenuationCoefficients
from .light import Light, LightSample, LightShadowParams, LightType
from .shading import blinn_phong_specular, lambert_diffuse, fresnel_schlick
from .setup import LightBudget, LightSetup

__all__ = [
    "AttenuationCoefficients",
    "Light",
    "LightSample",
    "LightShadowParams",
    "LightType",
    "LightBudget",
    "LightSetup",
    "lambert_diffuse",
    "blinn_phong_specular",
    "fresnel_schlick",
]
