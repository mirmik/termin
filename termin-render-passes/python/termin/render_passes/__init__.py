"""Concrete render passes."""

from termin_nanobind.runtime import preload_sdk_libs

preload_sdk_libs("nanobind", "termin_render", "termin_render_passes")

from termin.render_passes._render_passes_native import (
    BloomPass,
    ColorPass,
    DebugTrianglePass,
    GrayscalePass,
    PresentToScreenPass,
    ShadowMapArrayEntry,
    ShadowMapArrayResource,
    ShadowMapResult,
    ShadowPass,
    SkyBoxPass,
    TONEMAP_ACES,
    TONEMAP_NONE,
    TONEMAP_REINHARD,
    TonemapPass,
)

__all__ = [
    "BloomPass",
    "ColorPass",
    "DebugTrianglePass",
    "GrayscalePass",
    "PresentToScreenPass",
    "ShadowMapArrayEntry",
    "ShadowMapArrayResource",
    "ShadowMapResult",
    "ShadowPass",
    "SkyBoxPass",
    "TONEMAP_ACES",
    "TONEMAP_NONE",
    "TONEMAP_REINHARD",
    "TonemapPass",
]
