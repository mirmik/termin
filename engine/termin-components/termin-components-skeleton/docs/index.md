# termin-components-skeleton

Skeleton component package for attaching skeleton state/controllers to entities.

Связанные документы:

- [termin-components](../../docs/index.md)
- [termin-skeleton](../../../termin-skeleton/docs/index.md)

## Основные области

- Build metadata in `CMakeLists.txt`.
- Component implementation/headers under this package.
- Python wrapper and component specs under `python/`.

## Публичный API

This distribution ships both the native Entity adapter and its
`termin.skeleton_components` Python wrapper. It depends on the portable
`termin-skeleton` domain package.

`SkeletonController::update_skeleton_instance` fills retained scratch storage
with current bone world matrices on every call. It then computes skin matrices
in the requested renderer root space. Retaining capacity removes repeated
temporary allocation; the matrices themselves are freshly computed, including
when time moves backwards or one controller serves multiple renderer roots.
