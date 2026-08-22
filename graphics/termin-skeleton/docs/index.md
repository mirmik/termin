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

`TcSkeleton` is a strong RAII owner of a generation handle. A strong reference
keeps the registry slot alive, and `tc_skeleton_destroy()` refuses to remove a
referenced resource. It does not pin the resource address: pool growth may move
every slot, so C++ consumers resolve the handle again for each operation. A
pointer returned by the C `tc_skeleton_get()` boundary is borrowed only until
the next skeleton-registry mutation and must never be cached.

`SkeletonInstance` follows that rule internally and owns its `TcSkeleton`
handle by value. Python accepts and returns `TcSkeleton | None`; the old raw
`tc_skeleton_struct`, `TcSkeleton.get()`, and controller `skeleton_data`
surfaces are intentionally absent. The returned Python resource is an owning
copy rather than a view into either the instance or the registry pool.

Every instance observes `tc_resource_header.version`. A successful payload
replacement causes the next pose or matrix operation to resize all runtime
storage and reset every local override to the replacement bind pose before
recomputing derived matrices. This reset is deliberate: bone identity, order,
and bind transforms form one published payload. A failed transactional
replacement leaves the version unchanged, so the current runtime overrides are
preserved.

The Entity adapter in `SkeletonController` keeps its cached instance at a
stable address and rebinds it in place when the resource identity changes.
Its positional `bone_entities` mapping is versioned by the skeleton bone-name
order. Bind/inverse-bind changes with the same name order are accepted live;
count, name, or order changes fail closed and require `set_bone_entities()` to
publish the new mapping before rendering resumes.

The C `tc_bone` transform fields use `tc_mat44`, `tc_vec3`, and `tc_quat` while
retaining the historical 280-byte layout and field offsets. In contrast,
`tc_skeleton_bone_desc` now owns typed transform values and the old mutable C
symbols were removed, so binaries built against the previous skeleton API must
be rebuilt together with the SDK.
