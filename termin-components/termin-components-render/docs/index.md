# termin-components-render

Render component package for attaching rendering data to entities/scenes.

Связанные документы:

- [termin-components](../../docs/index.md)
- [termin-render](../../../termin-render/docs/index.md)
- [termin-graphics](../../../termin-graphics/docs/index.md)

## Основные области

- Build and packaging metadata in `CMakeLists.txt` / `setup.py`.
- Component implementation/headers under this package.

## Публичный API

Component-level render API is installed through this package and participates in the canonical `termin.render_components` namespace.

## LineRenderer

`LineRenderer` is implemented in C++ and re-exported from `termin.render_components`.
By default it draws through the tgfx2 GPU line path instead of baking a
`tc_mesh`: `LineRenderMode.WorldBillboard` expands camera-facing thick line
quads in `termin-graphics` and uses round caps/joins. `LineRenderMode.ScreenSpace`
uses the same renderer family for pixel-width lines. `LineRenderMode.WorldTube`
draws a world-space GPU-expanded tube; `tube_sides` defaults to `6`.
In the editor inspector, `render_mode` is exposed as an enum dropdown with
these modes instead of a raw integer field.

The old CPU mesh path is still available as `LineRenderMode.WorldMesh`, and
the legacy `raw_lines` flag remains supported for compatibility. Those modes
continue to expose a mesh through `get_mesh()`.

`cast_shadow` is opt-in for all line modes. Direct GPU modes only participate
in the `shadow` phase when this flag is enabled; other auxiliary geometry
phases such as depth, normal, and id remain mesh-only.

## WorldTextComponent

`WorldTextComponent` draws stable world-space labels through the existing
`termin-graphics` Text3D renderer. It is a C++ drawable component exported as
`termin.render_components.WorldTextComponent`, with inspectable fields for
`text`, `font_path`, `local_offset`, `color`, `size`, `anchor`, `phase_mark`,
and render-state flags.

The component uses direct tgfx2 rendering in the selected material phase
(`transparent` by default) and exports the `termin-engine-text3d` built-in
shader into runtime packages, so `termin play` and standalone builds do not
depend on editor-only shader compilation for 3D labels.
