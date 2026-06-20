"""Builtin frame-pass specs owned by termin-render-passes."""

from __future__ import annotations

FRAME_PASS_SPECS: list[tuple[str, str]] = [
    ("termin.render_passes", "ColorPass"),
    ("termin.render_passes", "SkyBoxPass"),
    ("termin.render_passes", "ShadowPass"),
    ("termin.render_passes", "PresentToScreenPass"),
    ("termin.render_passes", "BlitPass"),
    ("termin.render_passes", "ResolvePass"),
    ("termin.render_passes", "IdPass"),
    ("termin.render_passes", "BloomPass"),
    ("termin.render_passes", "GrayscalePass"),
    ("termin.render_passes", "HighlightPass"),
    ("termin.render_passes", "TonemapPass"),
    ("termin.render_passes", "DebugTrianglePass"),
    ("termin.render_passes", "ColliderGizmoPass"),
    ("termin.render_passes", "ImmediateDepthPass"),
    ("termin.render_passes", "UnifiedGizmoPass"),
    ("termin.render_passes", "UIWidgetPass"),
]

__all__ = ["FRAME_PASS_SPECS"]
