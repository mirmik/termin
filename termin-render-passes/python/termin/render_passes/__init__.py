"""Concrete render passes."""

from termin_nanobind.runtime import preload_sdk_libs

preload_sdk_libs("nanobind", "termin_render", "termin_render_passes")

from termin.render_passes._render_passes_native import (
    BloomPass,
    ColorPass,
    DebugTrianglePass,
    GrayscalePass,
    IdPass,
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
    tc_picking_cache_clear,
    tc_picking_id_to_rgb,
    tc_picking_rgb_to_id,
)

__all__ = [
    "BloomPass",
    "ColorPass",
    "DebugTrianglePass",
    "GrayscalePass",
    "IdPass",
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
    "tc_picking_cache_clear",
    "tc_picking_id_to_rgb",
    "tc_picking_rgb_to_id",
]
