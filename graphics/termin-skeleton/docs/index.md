# termin-skeleton

`termin-skeleton` содержит skeleton-domain API и Python bindings.

Связанные документы:

- [Module Map](../../../docs/modules.md#termin-skeleton)
- [canonical naming](../../../docs/architecture/2026-03-15-canonical-naming.md)

## Основные области

- Public headers в `include/`.
- Implementation в `src/`.
- Python package в `python/termin/skeleton`.

## Публичный API

The `termin-skeleton` distribution contains only the portable
`termin.skeleton` domain package. Entity synchronization and the
`termin.skeleton_components` wrapper are shipped by the Termin-owned
`termin-components-skeleton` distribution.

`TcSkeleton.set_bones()` is the canonical bulk publication boundary. It
validates the complete hierarchy and finite column-major inverse-bind/TRS payload,
allocates replacement bones and roots, then swaps them atomically. Invalid
parents, cycles, malformed rotations, or allocation failure preserve the old
skeleton and its version. Each Python descriptor carries `Mat44`, `Vec3`,
`Quat`, and `Vec3` values; file adapters convert packed column-major matrices
with `Mat44.from_column_major()` before publication.

Registry-owned bones and roots are immutable to consumers. The destructive
`alloc_bones()`/mutable-`get_bone()`/manual-`rebuild_roots()` path was removed;
there is no unchecked compatibility publication API.

The C `tc_bone` transform fields use `tc_mat44`, `tc_vec3`, and `tc_quat` while
retaining the historical 280-byte layout and field offsets. In contrast,
`tc_skeleton_bone_desc` now owns typed transform values and the old mutable C
symbols were removed, so binaries built against the previous skeleton API must
be rebuilt together with the SDK.
