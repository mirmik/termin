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
