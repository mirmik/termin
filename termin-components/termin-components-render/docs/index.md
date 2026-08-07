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
The accepted production contract is one world-space tube with width in world
units. Tube geometry is view-independent; material/pass composition and
mono/multiview projection belong to the common material pipeline and its
pass-owned `VertexOutputAdapter`.

The previous public modes (`WorldBillboard`, `ScreenSpace`, `WorldMesh` and
`RawLines`) and the duplicate `raw_lines` switch have been removed.
Camera-facing and screen-space renderers remain low-level unlit debug/overlay
utilities in `termin-graphics`, not material-bearing scene modes. See the
[architecture council protocol](../../../docs/architecture-council/2026-08-07-line-renderer-contract.md).

`cast_shadow` is opt-in. Object picking uses the
engine-owned `pick` phase and pass contract; `id` remains ordinary
resource/pass terminology, not a built-in line renderer phase alias.

## XR ray interaction

`XrRayInteractorComponent` runs after an `XrTrackedPoseComponent`. Aim pose is
preferred when the runtime exposes it; grip pose is also an explicit supported
source for runtimes where the aim action is unavailable. It finds the nearest enabled component publishing the
renderer-independent `world_pointer_surface` capability, maintains
hover/select/capture state, and sends normalized world-pointer events. The
select action produces DOWN/UP; tracking or projection loss produces CANCEL.

A `LineRenderer` on the same tracked-pose entity is the explicit ray visualization. Its
local segment follows the engine's +Y forward axis and is shortened to the
nearest surface hit. The interactor has no dependency on UI widget types or
collision shapes, so other world-pointer surfaces can participate without an
XR-specific protocol.

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
