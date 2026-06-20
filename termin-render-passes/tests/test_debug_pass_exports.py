from termin.render_passes import ImmediateDepthPass, UnifiedGizmoPass
from termin.render_passes.builtins import FRAME_PASS_SPECS


def test_debug_passes_are_public_render_passes() -> None:
    assert ImmediateDepthPass.__module__ == "termin.render_passes.immediate_depth"
    assert UnifiedGizmoPass.__module__ == "termin.render_passes.unified_gizmo"


def test_debug_passes_are_default_frame_pass_specs() -> None:
    assert ("termin.render_passes", "ImmediateDepthPass") in FRAME_PASS_SPECS
    assert ("termin.render_passes", "UnifiedGizmoPass") in FRAME_PASS_SPECS
