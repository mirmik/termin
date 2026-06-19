# termin-render-passes

Concrete render pass implementations built on top of `termin-render`.

This module owns reusable pass classes such as presentation, fullscreen effects,
ground grid rendering, and diagnostic passes. Application/editor code should
consume these passes through the public C++ headers under `<termin/render/...>`
or Python package `termin.render_passes`, not compile pass sources from
`termin-app`.

`ColliderGizmoPass` lives here as a debug/editor render pass. Its implementation
uses collision components privately; consumers should depend on the pass API, not
on app-side render sources.
