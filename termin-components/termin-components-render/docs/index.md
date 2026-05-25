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
By default it now draws through the tgfx2 GPU line path instead of baking a
`tc_mesh`: `LineRenderMode.WorldBillboard` expands camera-facing thick line
quads in `termin-graphics` and uses round caps/joins. `LineRenderMode.ScreenSpace`
uses the same renderer family for pixel-width lines.

The old CPU mesh path is still available as `LineRenderMode.WorldMesh`, and
the legacy `raw_lines` flag remains supported for compatibility. Those modes
continue to expose a mesh through `get_mesh()`.
