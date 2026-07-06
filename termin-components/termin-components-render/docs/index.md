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

Standalone camera math types (`Camera`, `CameraProjection`) are exported from
`termin.render_components`. The legacy `termin._native.render` compatibility
surface has been removed.

## MeshRenderer

`MeshRenderer` no longer owns mesh data and does not accept `mesh`,
`set_mesh`, or `set_mesh_by_name` through Python. Attach `MeshComponent` to the
same entity and keep mesh offsets on that component; `MeshRenderer` is
responsible for material, shadow participation, and material overrides.

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
in the `shadow` phase when this flag is enabled. Object picking uses the
engine-owned `pick` phase and pass contract; `id` remains ordinary
resource/pass terminology, not a built-in line renderer phase alias.

## WorldTextComponent

`WorldTextComponent` draws stable world-space labels through the existing
`termin-graphics` Text3D renderer. It is a C++ drawable component exported as
`termin.render_components.WorldTextComponent`, with inspectable fields for
`text`, `font_path`, `local_offset`, `plane_normal`, `text_up`, `color`,
`size`, `anchor`, `orientation`, `phase_mark`, and render-state flags.

`orientation="billboard"` faces the text toward the active camera.
`orientation="fixed"` builds the text plane from `plane_normal` and `text_up`:
`plane_normal` is the plane normal, while `text_up` defines where the top of
the glyphs points after being projected into that plane.

The component uses direct tgfx2 rendering in the selected material phase
(`transparent` by default) and exports the `termin-engine-text3d` built-in
shader into runtime packages, so `termin play` and standalone builds do not
depend on editor-only shader compilation for 3D labels.
