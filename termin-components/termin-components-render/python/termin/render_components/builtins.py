"""Builtin component and frame-pass specs owned by termin-render-components."""

from __future__ import annotations

COMPONENT_SPECS: list[tuple[str, str]] = [
    ("termin.render_components", "CameraComponent"),
    ("termin.render_components", "CameraController"),
    ("termin.render_components", "MeshRenderer"),
    ("termin.render_components", "SkinnedMeshRenderer"),
    ("termin.render_components", "LineRenderer"),
    ("termin.render_components", "WorldTextComponent"),
    ("termin.render_components", "LightComponent"),
    ("termin.render_components", "XrOriginComponent"),
    ("termin.render_components", "XrThumbstickLocomotionComponent"),
]

FRAME_PASS_SPECS: list[tuple[str, str]] = [
    ("termin.render_components", "DepthPass"),
    ("termin.render_components", "DepthOnlyPass"),
    ("termin.render_components", "DepthToColorPass"),
    ("termin.render_components", "ColorToDepthPass"),
    ("termin.render_components", "NormalPass"),
    ("termin.render_components", "MaterialPass"),
]

__all__ = ["COMPONENT_SPECS", "FRAME_PASS_SPECS"]
