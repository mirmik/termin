from termin.render_passes import ImmediateDepthPass, UnifiedGizmoPass
from termin_render_pass_specs import FRAME_PASS_SPECS


def test_debug_passes_are_public_render_passes() -> None:
    assert ImmediateDepthPass.__module__ == "termin.render_passes.immediate_depth"
    assert UnifiedGizmoPass.__module__ == "termin.render_passes.unified_gizmo"


def test_debug_passes_are_default_frame_pass_specs() -> None:
    assert ("termin.render_passes", "ImmediateDepthPass") in FRAME_PASS_SPECS
    assert ("termin.render_passes", "UnifiedGizmoPass") in FRAME_PASS_SPECS


def test_unified_gizmo_pass_resolves_a_neutral_draw_source() -> None:
    draw_source = object()
    render_pass = UnifiedGizmoPass(draw_source=lambda: draw_source)

    assert render_pass._get_draw_source() is draw_source
