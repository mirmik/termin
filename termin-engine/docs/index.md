# termin-engine

`termin-engine` содержит engine-level orchestration поверх scene/render/input/domain modules.

Связанные документы:

- [Module Map](../../docs/modules.md#termin-engine)
- [termin-scene](../../termin-scene/docs/index.md)
- [termin-render](../../termin-render/docs/index.md)

## Основные области

- Public headers в `include/`.
- Engine implementation в `src/`.
- Python bindings в `bindings/`.
- Python package в `python/termin/engine`.

## Публичный API

Python package: `termin.engine` через пакет `termin-engine`.

Модуль связывает нижележащие подсистемы, но не является application/editor слоем. Application policy живет в `termin-app`.

