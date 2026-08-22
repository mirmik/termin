# termin-animation

`termin-animation` содержит animation clip/runtime API и Python bindings.

Связанные документы:

- [Module Map](../../../docs/modules.md#termin-animation)
- [termin-skeleton](../../termin-skeleton/docs/index.md)
- [canonical naming](../../../docs/architecture/2026-03-15-canonical-naming.md)

## Основные области

- Public headers в `include/`.
- Implementation в `src/`.
- Python package в `python/termin/animation`.

## Публичный API

The `termin-animation` distribution contains only the portable
`termin.animation` domain package. Entity playback and the
`termin.animation_components` wrapper are shipped by the Termin-owned
`termin-components-animation` distribution.

## Bulk track contract

`TcAnimationClip.set_tracks()` atomically replaces a clip with owned flat
tracks identified by source node index, path, interpolation, component count,
times, and values. The format keeps vec3 scale and the glTF CUBICSPLINE
`in/value/out` tensor shape. LINEAR and STEP translation/rotation/scale tracks
are sampled by the runtime. Rotation samples use checked quaternion loads from
the flat payload, normalize non-unit keys, follow the shortest path, and publish
only a finite unit quaternion. Degenerate or non-finite rotation keys are logged
sampling errors and leave the caller's output unchanged.
CUBICSPLINE and morph-weight tracks remain round-trippable but sampling them is
an explicit error until those player paths are implemented. The legacy
name-grouped channel API remains available only for existing assets. Its
dedicated translation and rotation fields use `tc_vec3` and `tc_quat` without
changing their packed ABI layout; channel sampling is transactional as well.
