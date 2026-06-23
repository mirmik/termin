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
surface re-exports them without owning separate bindings.
