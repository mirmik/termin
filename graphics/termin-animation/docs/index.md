# termin-animation

`termin-animation` содержит animation clip/runtime API и Python bindings.

Связанные документы:

- [Module Map](../../../docs/modules.md#termin-animation)
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

`TcAnimationClip.set_tracks()` is the flat import adapter and atomically
publishes path-discriminated owned tracks. Runtime LINEAR/STEP translation and
scale values are `tc_vec3`; rotations are normalized `tc_quat` values. Cubic
vec3 keys own typed `in/value/out` triples, while cubic rotation keys keep
ordinary `tc_vec4` derivative tangents around a normalized quaternion value.
The source node index, interpolation metadata, vec3 scale and full glTF tensor
shape remain available through the flat `tracks` inspection adapter.

LINEAR and STEP translation/rotation/scale tracks return a discriminated typed
sample. Degenerate or non-finite rotation values are rejected during
publication without replacing the prior clip. Valid non-unit rotation values
are normalized during the same transaction; cubic tangents are never treated
as quaternions.
CUBICSPLINE and morph-weight tracks remain round-trippable but sampling them is
an explicit error until those player paths are implemented. The legacy
name-grouped channel API remains available only for existing assets. Its
dedicated translation and rotation fields use `tc_vec3` and `tc_quat` without
changing their packed ABI layout; channel replacement and sampling are
transactional as well.
