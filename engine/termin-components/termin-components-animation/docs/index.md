# termin-components-animation

Animation component package for entity-level animation playback/control.

Связанные документы:

- [termin-components](../../docs/index.md)
- [termin-animation](../../../termin-animation/docs/index.md)

## Основные области

- Build metadata in `CMakeLists.txt`.
- Component implementation/headers under this package.
- Python wrapper and component specs under `python/`.

## Публичный API

This distribution ships both the native Entity adapter and its
`termin.animation_components` Python wrapper. It depends on the portable
`termin-animation` domain and the skeleton Entity adapter.
