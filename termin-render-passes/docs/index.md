# termin-render-passes

Concrete render pass implementations built on top of `termin-render`.

This module owns reusable pass classes such as presentation, fullscreen effects,
ground grid rendering, and diagnostic passes. Application/editor code should
consume these passes through the public C++ headers under `<termin/render/...>`
or Python package `termin.render_passes`, not compile pass sources from
`termin-app`.

`ColliderGizmoPass`, `ImmediateDepthPass`, and `UnifiedGizmoPass` live here as
debug/editor render passes. Their implementations use collision, immediate
rendering, or caller-provided gizmo draw sources privately; consumers should
depend on the pass API, not on app-side render sources.

Shadow camera helpers (`ShadowCameraParams`, `build_shadow_view_matrix`,
`build_shadow_projection_matrix`, `compute_light_space_matrix`,
`compute_frustum_corners`, `fit_shadow_frustum_to_camera`) are part of the
public `termin.render_passes` Python API. The legacy `termin._native.render`
surface has been removed; use the canonical package directly.

`UIWidgetPass` is one native C++ pass on desktop, Android, and OpenXR. It
collects the `scene_ui_document` component capability, applies component,
entity, layer, and optional internal-hierarchy filtering, then submits the
documents in stable `(priority, identity)` order to
`NativeDocumentPainter`. The pass owns painter GPU resources; UI components
and their document assets remain CPU-only.

If a document already carries host-published presentation metrics,
`UIWidgetPass` preserves them in the painter submission. Documents without a
platform source receive an explicit identity metric for the current render
extent. Android publishes density, normalized font scale, safe insets, and
surface extent through its Activity/bootstrap bridge before scene rendering.

For distinct framegraph resources the pass copies input scene color to the
output before opening the UI pass with load semantics. For an inplace alias it
opens the existing target with load semantics directly. The Python
`termin.render_passes.ui_widget` module is only a projection of this native
type and contains no render implementation.
